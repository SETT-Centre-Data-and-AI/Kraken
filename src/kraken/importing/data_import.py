from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from kraken.classes.pack_lists import ResultList
from kraken.classes.packs import Result
from kraken.support.readout import readout
from kraken.support.support import _check_filetype, _load_filepaths, calculate_runtime


def extract_spreadsheets(
    filepaths: str | list[str] | Path | list[Path], clean_df: bool = True, **kwargs: Any
) -> ResultList:
    """Imports CSV, XLS, XLSX and Parquet files into a ResultList. Outputs results in
    order of user directory/file input. Raises errors if a filepath does not point to
    a supported file or a valid directory, or if no supported files are detected. Raises warnings
    if any given directory filepath returns no files.

    Args:
        filepaths (str | list[str]): Path or list of paths to spreadsheet files or
            directories of spreadsheet files
        clean_df (bool): Uses pandas' numpy_nullable reader backend by default for
            CSV/Excel, avoiding float intermediates for nullable signed integers.
            False leaves backend selection to pandas. Explicit dtype/backend options
            are honored. Parquet retains its stored schema regardless of this flag.
        kwargs: Forwarded to the relevant pandas reader. CSV/Excel default to
            keep_default_na=False and na_values=[""], preserving literal NA strings
            but treating blanks as missing. Override these defaults as needed.
            Use dtype for identifiers or unsigned integers, converters for exact
            decimals, and parse_dates for CSV timestamps. These formats do not
            retain a full column schema.
            Options must be valid for every requested format when mixing file types.

    Returns:
        ResultList: Imported dataframes with filename, dataframe name and path metadata.
    """
    start = datetime.now()
    supported_extensions = ["csv", "xlsx", "xls", "parquet"]
    reader_kwargs = {"keep_default_na": False, "na_values": [""], **kwargs}
    if clean_df:
        reader_kwargs.setdefault("dtype_backend", "numpy_nullable")
    parse_dates = reader_kwargs.get("parse_dates")
    declared_dtypes = reader_kwargs.get("dtype")
    inferred_date_columns: list[str | int] = []
    if "dtype_backend" in reader_kwargs and isinstance(parse_dates, list):
        date_dtypes: dict[str | int, Any]
        if declared_dtypes is None:
            date_dtypes = {}
        elif isinstance(declared_dtypes, dict):
            date_dtypes = declared_dtypes.copy()
        else:
            date_dtypes = defaultdict(lambda: declared_dtypes)
        for column in parse_dates:
            if isinstance(column, (str, int)) and column not in date_dtypes:
                date_dtypes[column] = object
                inferred_date_columns.append(column)
        reader_kwargs["dtype"] = date_dtypes

    # Load Filepaths
    filepaths = _load_filepaths(filepaths, supported_extensions)
    spreadsheet_packs = ResultList()
    df_name_list = []
    df_name_duplicates = set()
    df_name_duplicate_count = 0

    readout.print("Loading dataframes from spreadsheets...")
    # Load spreadsheets
    for filepath in filepaths:
        # Load csv dataframes
        if _check_filetype(filepath, "csv"):
            filename = Path(filepath).name
            df_name = Path(filepath).stem
            readout.print(f" - From csv '{filename}'...", end="")
            df = pd.read_csv(filepath, **reader_kwargs)
            _restore_parsed_dates(df, inferred_date_columns)
            spreadsheet_packs.append(
                Result(
                    filename=filename,
                    df_name=df_name,
                    df=df,
                    filepath=filepath,
                    db_alias="",
                    platform="",
                    sql="",
                )
            )
            df_name_list.append(df_name)
            readout.print(f" loaded dataframe '{df_name}'")

        # Load xlsx dataframes
        if _check_filetype(filepath, ["xlsx", "xls"]):
            filename = Path(filepath).name
            readout.print(f" - From xlsx '{filename}'...")
            with pd.ExcelFile(filepath) as file:
                for sheet_name in file.sheet_names:
                    df_name = str(sheet_name)
                    df = file.parse(df_name, **reader_kwargs)
                    _restore_parsed_dates(df, inferred_date_columns)
                    spreadsheet_packs.append(
                        Result(
                            filename=filename,
                            df_name=df_name,
                            df=df,
                            filepath=filepath,
                            db_alias="",
                            platform="",
                            sql="",
                        )
                    )
                    df_name_list.append(df_name)
                    readout.print(f"   - loaded dataframe '{df_name}'")

        if _check_filetype(filepath, "parquet"):
            filename = Path(filepath).name
            df_name = Path(filepath).stem
            readout.print(f" - From parquet '{filename}'...", end="")
            df = pd.read_parquet(filepath, **kwargs)
            spreadsheet_packs.append(
                Result(
                    filename=filename,
                    df_name=df_name,
                    df=df,
                    filepath=filepath,
                    db_alias="",
                    platform="",
                    sql="",
                )
            )
            df_name_list.append(df_name)
            readout.print(f" loaded dataframe '{df_name}'")

    stop = datetime.now()
    readout.print(
        f"{len(spreadsheet_packs)} dataframes loaded from {len(filepaths)} files in {calculate_runtime(start, stop).message}"
    )

    # Check for df name duplicates
    for df_name in df_name_list:
        df_name_count = df_name_list.count(df_name)
        if df_name_count != 1:
            df_name_duplicate_count += df_name_count - 1
            df_name_duplicates.add(df_name)

    if df_name_duplicates:
        s = "" if len(df_name_duplicates) == 1 else "s"
        readout.print(
            f"\nWARNING: {len(df_name_duplicates)} duplicate dataframe name{s}:"
        )
        for duplicate in df_name_duplicates:
            readout.warn(f"' -> '{duplicate}")

    readout.print("")
    return spreadsheet_packs


def _restore_parsed_dates(df: pd.DataFrame, columns: list[str | int]) -> None:
    for position, name in enumerate(df.columns):
        if name in columns or position in columns:
            df.isetitem(position, df.iloc[:, position].infer_objects().array)
