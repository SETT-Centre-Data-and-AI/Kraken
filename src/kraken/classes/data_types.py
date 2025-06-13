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
