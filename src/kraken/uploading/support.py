import math
from typing import Literal, overload

import numpy as np
from pandas import DataFrame, notnull
from pandas.api.types import is_object_dtype, is_string_dtype
from sqlalchemy.types import FLOAT, VARCHAR

from kraken.exceptions import VarcharLengthError

TABLE_EXISTS_OPTIONS: tuple[str, str, str] = ("append", "replace", "drop")
HEADER_CASE_OPTIONS: tuple[str, str] = ("upper", "lower")


def _truncate_cols(df: DataFrame, max_header_length: int | None = None) -> DataFrame:
    if not df.empty:
        if not max_header_length:
            max_header_length = int(df.columns.str.len().max())
        renamed_cols = dict(zip(df.columns, [col[:max_header_length] for col in df]))  # type: ignore[index]
        return df.rename(columns=renamed_cols)
    return df


def _force_dtypes_string(df: DataFrame) -> DataFrame:
    """
     - Take DataFrame, and forces all values within any 'object' dtype column to be treated as a string
     - Does not translate 'None' or 'nan' stored as text to Nulls

    Note:
        string vs string[pyarrow]: https://pandas.pydata.org/docs/user_guide/pyarrow.html

    Args:
        df (DataFrame): Input dataframe

    Returns:
        DataFrame: DataFrame with all values in 'object' dtype columns converted to strings
    """

    for column in df:
        if is_object_dtype(df[column]) or is_string_dtype(df[column]):
            df[column] = df[column].apply(lambda x: np.nan if x is None else x)
            df[column] = df[column].apply(lambda x: str(x) if notnull(x) else x)
    return df


def _convert_dtypes(
    df: DataFrame, varchar_length: int | None = None
) -> dict[str, FLOAT | VARCHAR]:
    """
     - Creates map to convert datatype 'object' to 'varchar' upon upload to avoid uploading large CLOB data
     - if varchar_length is not entered, the column VARCHAR length will default to the current maximum string length in each column

    Args:
        df (DataFrame): Input dataframe
        varchar_length (int, optional): Column VARCHAR length to set upon upload. Defaults to None (in which case is set to the maximum string length in each column).

    Raises:
        Error (VarcharLengthError): if the varchar_length argument is too short for the longest string in an 'object' column

    Returns:
        dict: Dicionary of columns to remap to VARCHAR
    """

    float_remap = {c: FLOAT for c in df.columns[df.dtypes == "float"].tolist()}

    varchar_remap: dict[str, int | VARCHAR] = {}
    for c in df.columns[df.dtypes == "object"].tolist():
        # Convert bools in object columns to strings
        df[c] = df[c].replace({True: "True", False: "False"})

        # Set VARCHAR(length) if all values are null
        if math.isnan((df[c].str.len().max())):
            varchar_remap[c] = varchar_length if varchar_length else 1
            continue

        # Caculate max string length
        max_length = int(df[c].str.len().max())

        # Set VARCHAR(length) if overwrite provided
        if varchar_length:
            if varchar_length < max_length:
                raise VarcharLengthError(
                    f"Maximum string length in column '{c}' ({max_length}) exceeds set_varchar_length ({varchar_length})"
                )
            varchar_remap[c] = VARCHAR(varchar_length)

        # Set VARCHAR(length) automatically
        else:
            varchar_remap[c] = VARCHAR(max_length)

    return varchar_remap | float_remap  # type: ignore[return-value]


@overload
def _convert_headers(
    df: DataFrame,
    convert_header_case: str | None = ...,
    inplace: Literal[False] = False,
) -> DataFrame: ...


@overload
def _convert_headers(
    df: DataFrame,
    convert_header_case: str | None = ...,
    inplace: bool = ...,
) -> DataFrame | None: ...


def _convert_headers(
    df: DataFrame,
    convert_header_case: str | None = None,
    inplace: bool = False,
) -> DataFrame | None:
    if convert_header_case not in {None, "upper", "lower"}:
        raise ValueError("Argument 'convert_header_case' takes 'upper','lower' or None")
    if convert_header_case == "upper":
        return df.rename(mapper=lambda x: x.upper(), axis="columns", inplace=inplace)
    elif convert_header_case == "lower":
        return df.rename(mapper=lambda x: x.lower(), axis="columns", inplace=inplace)
    else:
        return df
