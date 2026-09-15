from dataclasses import dataclass
from datetime import timedelta

from pandas import DataFrame


@dataclass
class Runtime:
    message: str
    timedelta: timedelta


@dataclass
class VariableBinding:
    name: str
    value: str


@dataclass
class StatsPack:
    df_name: str
    stats: DataFrame
    categories: DataFrame

    def __repr__(self) -> str:
        return (
            f"StatsPack(df_name={self.df_name!r}, "
            f"stats=DataFrame(shape={self.stats.shape!r}), "
            f"categories=DataFrame(shape={self.categories.shape!r}))"
        )
