import copy
import sys

from kraken.support.support import _prepare_sql_snippet

SPLIT = "Split"
ZONE = "Zone"
WRAPPER = "Wrapper"
COMMENT = "Comment"

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class Region:
    def __init__(
        self, start: int, stop: int, type: str, start_token: str, stop_token: str
    ) -> None:
        self.start: int = start
        self.stop: int = stop
        self.type: str = type
        self.start_token: str = start_token
        self.stop_token: str = stop_token

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(start={repr(self.start)}, stop={repr(self.stop)}, type={repr(self.type)}, start_token={repr(self.start_token)}, stop_token={repr(self.stop_token)})"

    def copy(self) -> Self:
        return copy.deepcopy(self)


class Event:
    def __init__(self, index: int, type: str, timing: str, token: str) -> None:
        self.index: int = index
        self.type: str = type
        self.timing: str = timing
        self.token: str = token

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(index={repr(self.index)}, type={repr(self.type)}, timing={repr(self.timing)}, token={repr(self.token)})"


class Replacement:
    def __init__(self, start: int, end: int, replacement: str):
        self.start: int = start
        self.end: int = end
        self.replacement: str = replacement

    def __repr__(self) -> str:
        return f'Replacement(start={self.start}, end={self.end}, replacement="{self.replacement}")'


class ScannedQuery:
    def __init__(
        self,
        sql: str,
        start_index: int,
        end_index: int,
        zones: list[Region] | None = None,
    ) -> None:
        self.sql: str = sql
        self.start_index: int = start_index
        self.end_index: int = end_index
        self.zones: list[Region] | None = zones
        self.sql_zone_suppressed: str = self.__suppress_zones()
        self.contains_sql: bool = self.__check_contains_sql()

    def __suppress_zones(self) -> str:
        if not self.zones:
            return self.sql

        suppressed_query = self.sql
        for zone in sorted(self.zones, key=lambda z: z.start, reverse=True):
            if zone.type == ZONE:
                suppressed_query = (
                    suppressed_query[: zone.start]
                    + suppressed_query[zone.stop + len(zone.stop_token) :]
                )
        return suppressed_query

    def __check_contains_sql(self) -> bool:
        if not self.sql.strip() or not self.sql_zone_suppressed.strip():
            return False
        else:
            return True

    def __repr__(self) -> str:
        repr_message = (
            f"{self.__class__.__name__}(sql='{(_prepare_sql_snippet(self.sql, max_characters=30))}', "
            + f"start_index={self.start_index}, end_index={self.end_index}, zones={len(self.zones)})"  # type: ignore[arg-type]
        )
        return repr_message
