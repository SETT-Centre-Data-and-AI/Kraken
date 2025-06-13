import re

from kraken.parsing.support_classes import SPLIT, ZONE, Event, Region


class Scanner:
    """Instantiated by a Parser, the Scanner's role is to parse SQL
    as per platform settings and return a series of SQL queries. The
    Scanner performs a double-pass, first identifying zones like strings,
    comments or objects (within which splitting and identification of
    split points or other zones is blocked until the zone is exited),
    and then scans for split points.

    All queries are saved to `queries` (even if empty), but flagged as to whether
    or not they contain anything other than comments.
    """

    def __init__(
        self,
        sql: str,
        comment_tokens: list[tuple],
        wrapper_tokens: list[tuple],
        split_tokens: list[tuple],
        feedback: bool = False,
        comment_only_mode: bool = True,
    ):
        # Scanner
        self.sql: str = sql
        self.zone_suppressed_sql: str | None = None
        self.feedback: bool = feedback
        self.comment_only_mode: bool = comment_only_mode
        self.__reset_scanner()

        # Tokens
        self.comment_tokens: list[tuple] = comment_tokens
        self.wrapper_tokens: list[tuple] = wrapper_tokens
        self.all_zonal_tokens: list[tuple] = self.comment_tokens + self.wrapper_tokens
        self.split_tokens: list[tuple] = split_tokens

        # Mapping
        self.events: list[Event] = []
        self.regions: list[Region] = []

    def __say(self, *values: object, sep: str = " ", end: str = "\n") -> None:
        if self.feedback:
            print(*values, sep=sep, end=end)

    def __reset_scanner(self) -> None:
        # Scan Settings
        self.i: int = 0
        self.char: str | None = None
        self.zone_active: bool = False
        self.zone_deactivation_token: str | None = None
        self.split_active: bool = False
        self.split_deactivation_token: str | None = None

    def __next(self, step: int = 1) -> None:
        self.i += step

    def __save_event(
        self, index: int, type: str, timing: str, token: str, save_twice: bool = False
    ) -> None:
        self.events.append(Event(index, type, timing, token))
        if save_twice:
            self.events.append(Event(index, type, timing, token))

    def __sort_events(self) -> None:
        if self.events:
            self.events = sorted(self.events, key=lambda x: x.index, reverse=False)
        return None

    def __sort_regions(self) -> None:
        if self.regions:
            self.regions = sorted(self.regions, key=lambda x: x.start, reverse=False)
        return None

    def __return_regions(self, region_type: str) -> list[Region]:
        regions = [region for region in self.regions if region.type == region_type]
        return sorted(regions, key=lambda x: x.start, reverse=False)

    def __return_events(self, event_type: str) -> list[Event]:
        events = [event for event in self.events if event.type == event_type]
        return sorted(events, key=lambda x: x.index, reverse=False)

    def __compile_ranges(self, event_type: str) -> None:
        self.__sort_events()
        events = self.__return_events(event_type=event_type)

        for i in range(0, len(events) - 1, 2):
            start_event = events[i]
            stop_event = events[i + 1]
            start_index, start_type, start_token = (
                start_event.index,
                start_event.type,
                start_event.token,
            )
            stop_index, _, stop_token = (
                stop_event.index,
                start_event.type,
                stop_event.token,
            )
            self.regions.append(
                Region(
                    start=start_index,
                    stop=stop_index,
                    type=start_type,
                    start_token=start_token,
                    stop_token=stop_token,
                )
            )
        self.__sort_regions()

    def __handle_zone_start(self) -> bool | None:
        token_list = (
            self.comment_tokens if self.comment_only_mode else self.all_zonal_tokens
        )
        for tokens in token_list:
            start, stop = tokens
            if self.sql[self.i : self.i + len(start)] == start:
                self.zone_active = True
                self.zone_deactivation_token = stop
                self.__save_event(index=self.i, type=ZONE, timing="Start", token=start)
                self.__next(len(start))
                return True
        return None

    def __handle_zone_stop(self) -> bool | None:
        stop = self.zone_deactivation_token
        if self.sql[self.i : self.i + len(stop)] == stop:  # type: ignore[arg-type]
            self.zone_active = False
            self.zone_deactivation_token = None
            self.__save_event(
                index=self.i + len(stop) - 1, type=ZONE, timing="Stop", token=stop
            )
            self.__next(len(stop))
            return True
        return None

    def __handle_split_start(self) -> bool | None:
        for start_token, stop_token in self.split_tokens:
            match = re.match(f"^{start_token}", self.sql[self.i :])
            if match:
                matched_token = match.group()

                if stop_token:
                    self.split_active = True
                    self.split_deactivation_token = stop_token
                    self.__save_event(
                        index=self.i,
                        type=SPLIT,
                        timing="Start",
                        token=matched_token,
                        save_twice=False,
                    )
                    self.__next(len(matched_token))  # Include in current query
                    return True

                else:
                    self.split_active = False
                    self.split_deactivation_token = None
                    self.__save_event(
                        index=self.i,
                        type=SPLIT,
                        timing="Instant",
                        token=matched_token,
                        save_twice=True,
                    )
                    self.__next(len(matched_token))  # Skip over token
                    return True
        return None

    def __handle_split_stop(self) -> bool | None:
        stop_token = self.split_deactivation_token
        match = re.match(f"^{stop_token}", self.sql[self.i :])
        if match:
            matched_token = match.group()
            self.split_active = False
            self.split_deactivation_token = None
            self.__save_event(
                index=self.i, type=SPLIT, timing="Stop", token=matched_token
            )
            self.__next(len(matched_token))  # Skip over token
            return True
        return None

    def __handle_zone(self) -> bool | None:
        if not self.zone_active:
            return self.__handle_zone_start()

        else:
            return self.__handle_zone_stop()

    def __handle_split(self) -> bool | None:
        if self.zone_active:
            return False

        if not self.split_active:
            return self.__handle_split_start()

        else:
            return self.__handle_split_stop()

    def __suppress_sql_zones(self) -> None:
        sql = self.sql
        if self.regions:
            zones = self.__return_regions(region_type=ZONE)
            for zone in sorted(zones, key=lambda x: x.start, reverse=True):
                zone_text = sql[zone.start : zone.stop + 1]
                suppressed_zone = "".join(
                    char if char == "\n" else " " for char in zone_text
                )
                sql = sql[: zone.start] + suppressed_zone + sql[zone.stop + 1 :]

        self.zone_suppressed_sql = sql

    def __scan_for_zones(self) -> None:
        self.__reset_scanner()
        sql = self.sql

        while self.i < len(sql):
            self.char = sql[self.i]

            if self.__handle_zone():
                continue

            self.__next(1)

        self.__compile_ranges(event_type=ZONE)
        self.__suppress_sql_zones()
        self.__reset_scanner()

    def __scan_for_splits(self) -> None:
        self.__reset_scanner()
        sql = self.zone_suppressed_sql

        while self.i < len(sql):  # type: ignore[arg-type]
            self.char = sql[self.i]  # type: ignore[index]

            if self.__handle_zone():
                continue

            if self.__handle_split():
                continue

            self.__next(1)

        self.__compile_ranges(event_type=SPLIT)
        self.__reset_scanner()

    def scan_sql(self) -> None:
        self.__reset_scanner()
        self.__scan_for_zones()

        if not self.comment_only_mode:
            self.__scan_for_splits()

        self.__say("Scanned SQL Regions:")
        if not self.regions:
            self.__say(" -> no zones found")
        else:
            self.__sort_regions()
            for region in self.regions:
                self.__say(f" -> {repr(region)}")


def create_scanner(
    sql: str,
    comment_tokens: list[tuple],
    wrapper_tokens: list[tuple],
    split_tokens: list[tuple],
    feedback: bool = False,
    comment_only_mode: bool = False,
) -> Scanner:
    return Scanner(
        sql=sql,
        comment_tokens=comment_tokens,
        wrapper_tokens=wrapper_tokens,
        split_tokens=split_tokens,
        feedback=feedback,
        comment_only_mode=comment_only_mode,
    )
