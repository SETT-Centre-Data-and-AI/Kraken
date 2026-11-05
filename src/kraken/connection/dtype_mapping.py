"""Metadata-driven dtype resolution for DB-API result sets.

`cursor.description` supplies a driver-specific `type_code` (plus precision and scale)
for every column. This module maps those codes to a small set of column kinds, and
converts fetched object columns to pandas dtypes without a float intermediate.

Metadata only selects the *target* kind. Values are always validated against it, and
any column that cannot be represented exactly falls back to value-based inference.
"""

from __future__ import annotations

import datetime
import decimal
from collections.abc import Sequence
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

ColumnKind = Literal["int", "uint", "bool", "float", "integral_decimal", "datetime"]

_INT64_MIN = -(2**63)
_INT64_MAX = 2**63
_UINT64_MAX = 2**64
_EXACT_FLOAT_INTEGER_LIMIT = 2**53
_HAS_EXTENDED_FLOAT = np.finfo(np.longdouble).nmant > np.finfo(np.float64).nmant

_DUCKDB_KINDS: dict[str, ColumnKind] = {
    **dict.fromkeys(
        ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT"),
        "int",
    ),
    **dict.fromkeys(
        ("UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT", "UHUGEINT"),
        "uint",
    ),
    "BOOLEAN": "bool",
    "FLOAT": "float",
    "DOUBLE": "float",
    "TIMESTAMP": "datetime",
    "TIMESTAMP_S": "datetime",
    "TIMESTAMP_MS": "datetime",
}

# psycopg2 reports PostgreSQL type OIDs
_POSTGRES_KINDS: dict[int, ColumnKind] = {
    **dict.fromkeys((20, 21, 23), "int"),
    16: "bool",
    **dict.fromkeys((700, 701), "float"),
    1114: "datetime",
}
_POSTGRES_NUMERIC = 1700

# pymysql reports MySQL protocol field types. Unsigned flags are not exposed, so
# integer columns are range-checked against the values.
_MYSQL_KINDS: dict[int, ColumnKind] = {
    **dict.fromkeys((1, 2, 3, 8, 9), "int"),
    **dict.fromkeys((4, 5), "float"),
    **dict.fromkeys((7, 12), "datetime"),
}
_MYSQL_DECIMAL = (0, 246)

_ORACLE_KINDS: dict[str, ColumnKind] = {
    "DB_TYPE_BINARY_INTEGER": "int",
    "DB_TYPE_BOOLEAN": "bool",
    **dict.fromkeys(("DB_TYPE_BINARY_FLOAT", "DB_TYPE_BINARY_DOUBLE"), "float"),
    **dict.fromkeys(("DB_TYPE_DATE", "DB_TYPE_TIMESTAMP"), "datetime"),
}

# pyodbc reports the Python type that values will be returned as
_PYTHON_TYPE_KINDS: dict[type, ColumnKind] = {
    int: "int",
    bool: "bool",
    float: "float",
    datetime.datetime: "datetime",
}


def _is_integral_scale(precision: Any, scale: Any) -> bool:
    return scale == 0 and isinstance(precision, int) and precision > 0


def resolve_column_kind(
    type_code: Any,
    precision: Any = None,
    scale: Any = None,
    driver: str | None = None,
) -> ColumnKind | None:
    """Map a DB-API `type_code` to a column kind, or None if it cannot be resolved.

    Args:
        type_code: Second element of a `cursor.description` entry.
        precision: Fifth element of a `cursor.description` entry.
        scale: Sixth element of a `cursor.description` entry.
        driver: Top-level module name of the DB-API driver. Needed for integer
            type codes, which are ambiguous between drivers.
    """
    if type_code is None:
        return None

    if isinstance(type_code, type):
        if type_code is decimal.Decimal:
            return "integral_decimal" if _is_integral_scale(precision, scale) else None
        return _PYTHON_TYPE_KINDS.get(type_code)

    if isinstance(type_code, int) and not isinstance(type_code, bool):
        if driver == "psycopg2":
            if type_code == _POSTGRES_NUMERIC:
                return (
                    "integral_decimal" if _is_integral_scale(precision, scale) else None
                )
            return _POSTGRES_KINDS.get(type_code)
        if driver == "pymysql":
            if type_code in _MYSQL_DECIMAL:
                return (
                    "integral_decimal" if _is_integral_scale(precision, scale) else None
                )
            return _MYSQL_KINDS.get(type_code)
        return None

    name = str(type_code)
    type_module = type(type_code).__module__
    if type_module.startswith(("_duckdb", "duckdb")):
        name = name.upper()
        if name.startswith("DECIMAL(") and name.endswith(",0)"):
            return "integral_decimal"
        return _DUCKDB_KINDS.get(name)
    if type_module.startswith("oracledb"):
        name = getattr(type_code, "name", name)
        if name == "DB_TYPE_NUMBER":
            return "integral_decimal" if _is_integral_scale(precision, scale) else None
        return _ORACLE_KINDS.get(name)
    return None


def _integer_column(
    column: pd.Series[Any], values: np.ndarray, unsigned: bool = False
) -> pd.Series[Any] | None:
    if values.size == 0:
        return column.astype("UInt64" if unsigned else "Int64")
    minimum, maximum = int(values.min()), int(values.max())
    if (not unsigned or minimum < 0) and _INT64_MIN <= minimum and maximum < _INT64_MAX:
        return column.astype("Int64")
    if 0 <= minimum and maximum < _UINT64_MAX:
        return column.astype("UInt64")
    return None


def _integral_values(values: np.ndarray) -> list[int] | None:
    integers: list[int] = []
    for value in values:
        if isinstance(value, decimal.Decimal):
            if not value.is_finite() or value != value.to_integral_value():
                return None
            integers.append(int(value))
        elif isinstance(value, (bool, np.bool_)):
            return None
        elif isinstance(value, (int, np.integer)):
            integers.append(int(value))
        elif isinstance(value, (float, np.floating)):
            floating_value: Any = value
            if (
                not np.isfinite(floating_value)
                or floating_value != np.floor(floating_value)
                or abs(floating_value) > _EXACT_FLOAT_INTEGER_LIMIT
                or (floating_value == 0 and np.signbit(floating_value))
            ):
                return None
            integers.append(int(value))
        else:
            return None
    return integers


def _exact_integers_column(
    column: pd.Series[Any], raw: np.ndarray, present: np.ndarray, integers: list[int]
) -> pd.Series[Any] | None:
    exact = np.full(len(raw), None, dtype=object)
    exact[present] = integers
    return _integer_column(
        pd.Series(exact, index=column.index, dtype=object),
        np.asarray(integers, dtype=object),
    )


def _floats_are_exact(values: np.ndarray, scalar_type: str) -> bool:
    """Check numeric values before selecting a float64 representation."""
    if scalar_type == "floating":
        if _HAS_EXTENDED_FLOAT:
            return bool(np.equal(values, values.astype("float64")).all())
        return True
    if scalar_type == "integer":
        if (
            abs(int(values.min())) <= _EXACT_FLOAT_INTEGER_LIMIT
            and abs(int(values.max())) <= _EXACT_FLOAT_INTEGER_LIMIT
        ):
            return True
    elif scalar_type == "mixed-integer-float" and not _HAS_EXTENDED_FLOAT:
        values = values[
            (values < -_EXACT_FLOAT_INTEGER_LIMIT)
            | (values > _EXACT_FLOAT_INTEGER_LIMIT)
        ]
    return all(
        int(float(value)) == int(value)
        if isinstance(value, (int, np.integer))
        else not _HAS_EXTENDED_FLOAT or value == np.longdouble(float(value))
        for value in values
    )


def _datetime_column(column: pd.Series[Any]) -> pd.Series[Any] | None:
    try:
        return pd.Series(pd.DatetimeIndex(column), index=column.index)
    except (ValueError, TypeError, OverflowError):
        for value in column:
            if isinstance(value, datetime.datetime):
                if value.tzinfo is not None or (
                    isinstance(value, pd.Timestamp) and value.nanosecond
                ):
                    return None
            elif isinstance(value, np.datetime64) and pd.Timestamp(value).nanosecond:
                return None
        return column.astype("datetime64[us]")


def analyse_column(
    column: pd.Series[Any], kind: ColumnKind | None = None
) -> pd.Series[Any] | None:
    """Select a lossless dtype using one null mask and scalar classification.

    Metadata is a preference, not permission to narrow values. None means that
    the original object column should be retained.
    """
    raw = column.to_numpy()
    present = np.asarray(pd.notna(raw))
    values = raw[present]
    scalar_type = pd.api.types.infer_dtype(values, skipna=False)

    try:
        if values.size == 0:
            dtype = (
                {
                    "int": "Int64",
                    "uint": "UInt64",
                    "integral_decimal": "Int64",
                    "bool": "boolean",
                    "datetime": "datetime64[us]",
                }.get(kind)
                if kind
                else None
            )
            if kind == "float":
                return pd.Series(np.nan, index=column.index, dtype="float64")
            return (
                pd.Series(index=column.index, dtype=cast(Any, dtype)) if dtype else None
            )

        if scalar_type == "integer":
            if kind == "float" and _floats_are_exact(values, scalar_type):
                floats = np.full(len(raw), np.nan)
                floats[present] = values
                return pd.Series(floats, index=column.index)
            return _integer_column(column, values, unsigned=kind == "uint")

        if scalar_type == "boolean":
            return column.astype("boolean")

        if scalar_type in ("decimal", "mixed-integer"):
            if kind == "integral_decimal":
                integers = _integral_values(values)
                if integers is not None:
                    return _exact_integers_column(column, raw, present, integers)
            return None

        if scalar_type in ("floating", "mixed-integer-float"):
            if scalar_type == "mixed-integer-float" and kind != "float":
                integers = _integral_values(values)
                if integers is not None:
                    return _exact_integers_column(column, raw, present, integers)
                return None
            exact = _floats_are_exact(values, scalar_type)
            if scalar_type == "mixed-integer-float":
                if not exact:
                    integers = _integral_values(values)
                    if integers is not None:
                        return _exact_integers_column(column, raw, present, integers)
                    return None
            elif not exact:
                return None

            floats = np.full(len(raw), np.nan)
            floats[present] = values
            if kind != "float":
                observed = floats[present]
                if (
                    np.isfinite(observed).all()
                    and np.abs(observed).max() <= _EXACT_FLOAT_INTEGER_LIMIT
                    and (observed == np.floor(observed)).all()
                    and not ((observed == 0) & np.signbit(observed)).any()
                ):
                    return pd.Series(floats, index=column.index).astype("Int64")
            return pd.Series(floats, index=column.index)

        if scalar_type in ("datetime", "datetime64"):
            return _datetime_column(column)
    except (ValueError, TypeError, OverflowError):
        return None
    return None


def convert_column_by_kind(
    column: pd.Series[Any], kind: ColumnKind
) -> pd.Series[Any] | None:
    """Analyse a column with a preferred metadata kind."""
    return analyse_column(column, kind)


def infer_column(column: pd.Series[Any]) -> pd.Series[Any] | None:
    """Analyse a column without metadata, retaining incompatible objects."""
    return analyse_column(column)


def resolve_column_kinds(
    description: Sequence[Sequence[Any]] | None, driver: str | None
) -> list[ColumnKind | None]:
    """Resolve the column kind of every entry in a `cursor.description`."""
    if not description:
        return []
    kinds: list[ColumnKind | None] = []
    for entry in description:
        entry = tuple(entry) + (None,) * (7 - len(entry))
        kinds.append(resolve_column_kind(entry[1], entry[4], entry[5], driver))
    return kinds
