from typing import Literal, overload

import pandas as pd
from IPython.display import display
from pandas import DataFrame
from pandas.api.types import is_numeric_dtype

from kraken.classes.data_types import StatsPack
from kraken.exceptions import DuplicateColumnError
from kraken.support.readout import readout
from kraken.support.support import list_as_bullets


def check_df_integers(df: DataFrame) -> DataFrame:
    """Checks DataFrame for float64 dtypes, and converts them to Int64 (allowing NULLs) if no decimals detected.

    Args:
        df (DataFrame): Input DataFrame

    Returns:
        DataFrame: Returns clean DataFrame
    """
    df_original_columns = df.columns
    if df.columns.has_duplicates:
        df.columns = pd.io.common.dedup_names(df.columns, is_potential_multiindex=False)
    for column in df.columns:
        if df[column].isna().all():
            continue
        if df[column].isna().any():
            df[column] = df[column].convert_dtypes(
                infer_objects=False,
                convert_string=False,
                convert_integer=True,
                convert_boolean=False,
                convert_floating=False,
            )
    df.columns = df_original_columns
    return df


@overload
def examine(
    df: DataFrame,
    df_name: str = ...,
    unique_ceiling: int = ...,
    show_results: bool = ...,
    return_results: Literal[False] = False,
) -> None: ...


@overload
def examine(
    df: DataFrame,
    df_name: str = ...,
    unique_ceiling: int = ...,
    show_results: bool = ...,
    return_results: bool = ...,
) -> StatsPack | None: ...


def examine(
    df: DataFrame,
    df_name: str = "df",
    unique_ceiling: int = 10,
    show_results: bool = True,
    return_results: bool = False,
) -> StatsPack | None:
    """Performs high-level analysis of data in a dataframe and outputs results.

    Args:
        df (DataFrame): Pandas DataFrame
        df_name (str, optional): Name of the originating dataframe. Defaults to "df".
        unique_ceiling (int, optional): Ceiling below which a distinct number of values in a column will be included in 'category calculations'. Defaults to 10.
        show_results (bool, optional): Display results in python/notebook readouts. Defaults to True.
        return_results (bool, optional): Returns results as StatsPack. Defaults to False, returning None.

    Returns:
        StatsPack: Tuple including df name, stats dataframe, and category coverage dataframe.
    """

    rows = df.shape[0]
    columns = df.shape[1]
    rounding = 3
    if rows == 0:
        raise ValueError("Empty DataFrame cannot be examined.")

    if show_results:
        print(f"DataFrame: {df_name}\n{'-' * (len(df_name) + 11)}")
        print(f"Shape: {rows} rows, {columns} columns")

    duplicate_columns = df.columns[df.columns.duplicated()].unique().tolist()
    if duplicate_columns:
        raise DuplicateColumnError(
            f"Cannot examine DataFrame with duplicate columns: {list_as_bullets(duplicate_columns)}"
        )

    # Initialise empty lists
    stats_list = []
    categories_list = []

    # Calculate statistics
    for column in df.columns:
        dtype = df[column].dtype

        numeric = (
            False
            if df[column].dtype == "bool"
            else True
            if is_numeric_dtype(df[column])
            else False
        )
        if df[column].dtype == "object":
            max_length = df[column].dropna().astype(str).str.len().max()
            max_length = int(max_length) if pd.notna(max_length) else None
        else:
            max_length = None
        rows = df.shape[0]
        non_null_count = df[column].count()
        null_count = df.shape[0] - non_null_count
        cardinality = df[column].nunique()

        # Numeric Calcs
        q1 = df[column].quantile(0.25) if numeric else None
        q3 = df[column].quantile(0.75) if numeric else None
        iqr = q3 - q1 if numeric else None  # type: ignore

        # Append statistics
        stats_list.append(
            {
                "column_name": column,
                "dtype": dtype,
                "max_length": max_length,
                "non_null_count": non_null_count,
                "null_count": null_count,
                "unique_count": cardinality,
                "nullity_%": round((null_count / rows) * 100, 2),
                "density_%": round((non_null_count / rows) * 100, 2),
                "cardinality_%": round((cardinality / rows) * 100, 2),
                "standard_deviation": (
                    round(df[column].astype("float").std(), rounding)
                    if numeric
                    else None
                ),
                "skewness": (
                    round(df[column].astype("float").skew(), rounding)  # type: ignore
                    if numeric
                    else None
                ),
                "kurtosis": (
                    round(df[column].astype("float").kurtosis(), rounding)  # type: ignore
                    if numeric
                    else None
                ),
                "z_outliers": (
                    round(
                        df[
                            (df[column] - df[column].mean()).abs()
                            > 3 * df[column].std()
                        ].shape[0],
                        rounding,
                    )
                    if numeric
                    else None
                ),
                "iqr_outliers": (
                    round(
                        df[
                            (df[column] < q1 - 1.5 * iqr)  # type: ignore
                            | (df[column] > q3 + 1.5 * iqr)  # type: ignore
                        ].shape[0],
                        rounding,
                    )
                    if numeric
                    else None
                ),
            }
        )

        # Calculate category coverages
        if 1 <= cardinality <= unique_ceiling:
            value_counts = df[column].value_counts(dropna=False)

            sorted_category_list = sorted(
                [
                    {
                        "column_name": column,
                        "unique_value": value,
                        "count": count,
                        "coverage_percentage": round((count / rows) * 100, 2),
                    }
                    for value, count in value_counts.items()
                ],
                key=lambda x: x["coverage_percentage"],  # type: ignore
                reverse=True,
            )

            categories_list.extend(sorted_category_list)

    # Prepare DataFrames & Stats Pack
    stats_df = check_df_integers(DataFrame(stats_list))
    categories_df = check_df_integers(DataFrame(categories_list))
    stats_pack = StatsPack(df_name=df_name, stats=stats_df, categories=categories_df)

    # Show Results
    if show_results:
        print("\nData Analysis")
        display(stats_df)
        print(f"\nCategories (<={unique_ceiling} unique values)")
        display(categories_df)

    if return_results:
        return stats_pack
    return None


def date_converter_df(
    df: DataFrame, columns: str | list | None = None, readouts: bool = True
) -> DataFrame:
    """Checks DataFrame for missed date columns identified as type 'object' by pandas, and converts those found in place.

    Args:
        df (DataFrame): DataFrame
        columns (str | list, optional): Specific columns to check. Defaults to None, checking all columns.
        readouts (bool, optional): Print changes. Defaults to True.

    Returns:
        DataFrame: Result
    """
    date_formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d-%b-%Y",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d/%b/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]

    if not columns:
        columns = list(df.columns)
    elif isinstance(columns, str):
        columns = [columns]

    for col in columns:
        if col is None or isinstance(df[col], DataFrame) or df[col].dtype != "object":
            pass
        else:
            for format in date_formats:
                try:
                    df[col] = pd.to_datetime(df[col], format=format)
                    if readouts:
                        readout.warn(
                            f"Note: column '{col}' converted to datetime64[ns]"
                        )
                    break
                except ValueError:
                    pass
    return df


def check_duplicates(
    df: DataFrame, columns: str | list[str] | None = None
) -> DataFrame:
    """Check whether data is unique in a column or over a set of columns.
    Can be used to determine applicability as a unique identifier or primary key.
    Returns duplicates over the given column set, if found.

    Args:
        df (DataFrame): Input DataFrame to check.
        columns (str | list[str], optional): Column or column set to check for duplicates. Defaults to None, checking the first column.

    Raises:
        ValueError: If a given column does not exist in the DataFrame.

    Returns:
        DataFrame: DataFrame of duplicates, if found
    """

    # Check Arguments
    if columns is None:
        columns = [df.columns[0]]
    elif isinstance(columns, str):
        columns = [columns]

    for column in columns:
        if column not in df.columns:
            df_columns = {"\n - ".join(df.columns)}
            raise ValueError(
                f"Entered column '{column}' not found in DataFrame. Available:\n - {df_columns}"
            )

    # Check for Duplicates
    is_unique = not df.duplicated(subset=columns).any()
    duplicates = (
        df[df.duplicated(subset=columns, keep=False)].sort_values(columns).copy()
    )
    if is_unique:
        readout.print(f"\033[92mNo Duplicates Over: {columns}\033[0m")
    else:
        readout.warn(f"WARNING: {len(duplicates)} Duplicates Over {columns}")

    return duplicates
