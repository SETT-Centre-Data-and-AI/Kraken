from enum import Enum
from typing import Any


class Colour(Enum):
    WARNING = ("\033[93m", "\x1b[0m")


class Readout:

    _instance = None  # Class variable to store the singleton instance
    ACTIVE = True

    def __new__(cls, *args: Any, **kwargs: Any) -> "Readout":
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def print(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        flush: bool = False,
    ) -> None:
        if Readout.ACTIVE:
            print(*values, sep=sep, end=end, flush=flush)

    def print_colour(
        self, text: object, colour: Colour, end: str | None = "\n"
    ) -> None:
        self.print(f"{colour.value[0]}{text}{colour.value[1]}", end=end)

    def warn(
        self, text: object, colour: Colour = Colour.WARNING, end: str | None = "\n"
    ) -> None:
        self.print_colour(text, colour, end=end)

    def set_active(self, active: bool) -> None:
        Readout.ACTIVE = active

    def activate(self) -> None:
        self.set_active(True)

    def suppress(self) -> None:
        self.set_active(False)


readout = Readout()
