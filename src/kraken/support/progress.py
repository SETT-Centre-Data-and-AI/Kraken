import os
import sys
import threading
import time
from datetime import datetime
from threading import Thread
from types import TracebackType
from typing import Literal

from IPython import get_ipython

from kraken.support.readout import readout

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class Progress:
    def __init__(
        self,
        header: str = "Executing",
        suffix: str = "",
        size: int = 7,
        marker: str = "|",
        complete_text: str = "Completed",
        in_progress_colour: tuple = ("\033[38;5;214m", "\033[0m"),
        complete_colour: tuple = ("\033[32m", "\033[0m"),
        format: str = "{header} ({timer}): {spinner} {suffix}",
        auto_update: bool = False,
        auto_update_interval: float = 0.5,
        active: bool = True,
    ):
        self.header: str = header
        self.suffix: str = suffix
        self.size: int = size
        self.marker: str = marker
        self.position: int = 0
        self.direction: int = 1
        self.last_bar_length = 0
        self.complete_text: str = complete_text
        self.in_progress_colour: tuple = in_progress_colour
        self.complete_colour: tuple = complete_colour
        self.start_time: datetime = datetime.now()
        self.format: str = format
        self.is_jupyter: bool = self.__is_jupyter()
        self.snapshots: list = self.__generate_snapshots()
        self.auto_update: bool = auto_update
        self.active: bool = active
        self.errored: bool = False
        self.__main_thread: Thread = threading.main_thread()
        self.__generate_bar()
        self.__headless_check()

        if self.auto_update:
            self.start_auto_update(interval=auto_update_interval)

    def __repr__(self) -> str:
        return self.bar

    def __enter__(self) -> Self:
        if self.auto_update:
            self.start_auto_update()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        self.stop_auto_update()
        if exc_type and (
            isinstance(exc_type, Exception) or issubclass(exc_type, Exception)
        ):
            self.errored = True
            self.__generate_bar(complete=False)
            self.show()
        return False

    def __is_jupyter(self) -> bool:
        return get_ipython() is not None

    def __headless_check(self) -> None:
        if not self.is_jupyter:
            try:
                os.get_terminal_size()
            except OSError:
                self.active = False

    def __wrap_in_colour(self, text: str, colour: tuple[str, str]) -> str:
        return f"{colour[0]}{text}{colour[1]}"

    def __get_elapsed_time(self) -> str:
        elapsed = datetime.now() - self.start_time
        minutes, seconds = divmod(elapsed.seconds, 60)
        return f"{minutes:02}:{seconds:02}"

    def __generate_snapshots(self) -> list:
        """Pre-generate all possible spinner positions."""
        snapshots = []
        for i in range(self.size):
            spinner = [" "] * self.size
            spinner[i] = self.marker
            spinner = f"[{''.join(spinner)}]"  # type: ignore[assignment]
            spinner = self.__wrap_in_colour(spinner, self.in_progress_colour)  # type: ignore
            snapshots.append(spinner)
        return snapshots

    def __generate_bar(self, complete: bool = False) -> None:
        if self.errored:
            spinner = self.__wrap_in_colour("Errored", ("\033[31m", "\033[0m"))
        elif complete:
            spinner = self.__wrap_in_colour(self.complete_text, self.complete_colour)
        else:
            spinner = self.snapshots[self.position]

        timer = self.__get_elapsed_time()
        self.bar = self.format.format(
            header=self.header, suffix=self.suffix, timer=timer, spinner=spinner
        )

    def __build_bar_with_scrubber(self) -> str:
        total_width = (
            self.last_bar_length if self.is_jupyter else os.get_terminal_size().columns
        )
        scrubber_length = max(0, total_width - len(self.bar))
        scrubber = " " * scrubber_length
        self.last_bar_length = len(self.bar)
        return f"\r{self.bar}{scrubber}"

    def __check_active(self) -> bool:
        return self.active and readout.ACTIVE

    def show(self) -> None:
        if not self.__check_active():
            return

        bar = self.__build_bar_with_scrubber()
        sys.stdout.write(bar)
        sys.stdout.flush()

    def reset_timer(self) -> None:
        self.start_time = datetime.now()

    def restart(self) -> None:
        self.position = 0
        self.__generate_bar()

    def update(self, show: bool = True) -> None:
        if not self.__check_active():
            return

        self.position += self.direction
        if self.position == 0 or self.position == self.size - 1:
            self.direction *= -1
        self.__generate_bar()
        if show:
            self.show()

    def update_header(
        self,
        header: str | None = None,
        suffix: str | None = None,
        show: bool = True,
        format: str | None = None,
    ) -> None:
        if not self.__check_active():
            return

        self.format = format if format else self.format
        self.header = header if header else self.header
        self.suffix = suffix if suffix else self.suffix
        if show:
            self.show()

    def finish(self, show: bool = True) -> None:
        if not self.__check_active():
            return

        self.__generate_bar(complete=True)
        self.stop_auto_update()
        if show:
            self.show()
            readout.print("\n", end="")

    def _simulate(self, iterations: int = 200, delay: float = 0.02) -> None:
        self.reset_timer()
        self.show()
        for _ in range(iterations):
            self.update()
            time.sleep(delay)
        self.finish()

    def start_auto_update(self, interval: float = 0.1) -> None:
        """
        Starts a background thread that updates the progress bar at regular intervals.

        Parameters:
        - interval (float): Time in seconds between updates.
        """
        if not self.__check_active():
            return

        if hasattr(self, "_auto_update_thread") and self._auto_update_thread.is_alive():  # type: ignore[has-type]
            return  # Auto-update is already running

        self._stop_event = threading.Event()
        self._auto_update_thread = threading.Thread(
            target=self._auto_update, args=(interval,), daemon=True
        )
        self._auto_update_thread.start()

    def _auto_update(self, interval: float) -> None:
        if not self.__check_active():
            return

        next_interval_time = time.time() + interval
        while self._check_still_alive():
            if next_interval_time <= time.time():
                self.update(show=True)
                next_interval_time = time.time() + interval
            time.sleep(0.01)

    def _check_still_alive(self) -> bool:
        return self.__main_thread.is_alive() and not self._stop_event.is_set()

    def stop_auto_update(self) -> None:
        """
        Stops the background auto-update thread if running.
        """
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
        if hasattr(self, "_auto_update_thread"):
            self._auto_update_thread.join()
