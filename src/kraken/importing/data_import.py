from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from kraken.analysis.data_manipulation import check_df_integers as clean_dataframe
from kraken.classes.pack_lists import ResultList
from kraken.classes.packs import Result
from kraken.support.readout import readout
from kraken.support.support import _check_filetype, _load_filepaths, calculate_runtime


def extract_spreadsheets(
    filepaths: str | list[str] | Path | list[Path], clean_df: bool = True, **kwargs: Any
) -> ResultList:
    """Takes paths, or list of paths, to spreadsheet files or directories of spreadsheet
    files and outputs a list of results with dataframes. Outputs list in order of user
    directory/file input. Raises errors if a filepath does not point to a spreadsheet
    file or a valid directory, or if no spreadsheet files are detected. Raises warnings
    if any given directory filepath returns no files.

    Args:
        filepaths (str | list[str]): Path or list of paths to spreadsheet files or
            directories of spreadsheet files
        clean_df (bool): Checks DataFrame after pandas generation and applies cleaning,
            including converting float64 to Int64 if applicable (recommended).

    Returns:
        list: List of results, consisting of tuples as: (filename, df name, dataframe, df, filepath)
    """
    start = datetime.now()
    supported_extensions = ["csv", "xlsx", "xls"]
    keep_default_na = False
    na_values = [""]

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
            df = pd.read_csv(
                filepath,
                keep_default_na=keep_default_na,
                na_values=na_values,
                **kwargs,
            )
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
                    df = file.parse(
                        df_name,
                        keep_default_na=keep_default_na,
                        na_values=na_values,
                        **kwargs,
                    )
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

    # Clean SpreadsheetPack DataFrames
    if clean_df:
        for pack in spreadsheet_packs:
            pack.df = clean_dataframe(pack.df)

    stop = datetime.now()
    readout.print(
        f"{len(spreadsheet_packs)} dataframes loaded from {len(filepaths)} files in {calculate_runtime(start,stop).message}"
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
