from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from kraken.classes.pack_lists import ResultList
from kraken.exporting.result_export import export_results
from kraken.ribosome.sql_execution import execute_sql
from kraken.ribosome.sql_extraction import extract_sql
from kraken.support.readout import readout
from kraken.support.support import calculate_runtime


def run(
    filepaths: str | Path | list[str] | list[Path] = "",
    variables: dict = {},
    username: str | None = None,
    clean_df: bool = True,
    export_directory: str | None = None,
    export_extension: str = "csv",
    export_filename: str = "",
    export_prefix: str = "",
    export_suffix: str = "",
    export_overwrite: bool = False,
    export_zip_filename: str | None = None,
    batch_size: int | None = None,
    parsing_feedback: bool = False,
    concurrent: bool = False,
    encoding: str = "utf-8",
    isolation_level: (
        Literal[
            "SERIALIZABLE",
            "REPEATABLE READ",
            "READ COMMITTED",
            "READ UNCOMMITTED",
            "AUTOCOMMIT",
        ]
        | None
    ) = None,
    **kwargs: Any,
) -> ResultList:
    """
    Summary:
    Takes a path (or list of paths) to SQL files or directories of SQL files, parses and executes SQL, and returns results:
        -   Extracts SQL from files in given filepaths
        -   Parses SQL
        -   Executes SQL against databases and returns ResultList of results
        -   If 'export_filepath' is entered, will export all results to desired location
        -   SQL Variables can be overwritten by inserting as a dictionary

    Args:
        -   filepaths (str | list[str], optional): filepath (or list of filepaths) to SQL files or directories of SQL files. If left blank, Kraken will search script's own directory. Defaults to "".
        -   variables (dict, optional): Dictionary of variables to overwrite in the SQL script. Defaults to {}.
        -   username (str, optional): If entered, downstream execution will attempt to use this username. If left blank, Kraken will use the default username saved for each given database alias in credential manager. Defaults to None.
        -   clean_df (bool): Checks each DataFrame after pandas generation and applies cleaning, including converting float64 to Int64 if applicable (recommended).
        -   export_directory (str, optional): Sets a directory to export results to. If left blank, Kraken ignores exporting. Enter "" to export to directory of execting script. Defaults to None.
        -   export_extension (str, optional): If exporting, Kraken will export as this extension if supported. Defaults to "csv".
        -   export_filename (str, optional): If exporting, Kraken will use this filename for the export file. If multiple files are being exported (CSVs for multiple dataframes, for example) then Kraken will use this as a prefix before the dataframe name. Defaults to "".
        -   export_prefix (str, optional): Prefix for the filename (or each filename). Defaults to "".
        -   export_suffix (str, optional): Suffix for the filename (or each filename). Defaults to "".
        -   export_overwrite (bool, optional): If exporting, determines behaviour of saving in the event of a filename conflict. If a file already exists, with either overwrite or amend the filename, appending with a number (_01, _02, etc). Defaults to False.
        -   export_zip_filename (str, optional): If exporting and provided, Kraken will zip files in memory before writing to this filename, rather than directly. Defaults to None (direct writing of files).
        -   batch_size (int): Downloads rows in batches. Use `batch_size=0` to fetch all data without batching.
        -   delimiter (str, optional): If exporting to a delimited file format (like CSV), this is used as the delimiter. Defaults to ",".
        -   parsing_feedback (bool): If True, Kraken will print a summary report of the parsed queries. Defaults to False.
        -   concurrent (bool): If True, executes all SQL files concurrently. Queries within each SQL file will still execute sequentially. Defaults to False.
        -   encoding (str): Encoding of SQL files. Defaults to "utf-8".
        -   isolation_level (Literal["SERIALIZABLE", "REPEATABLE READ", "READ COMMITTED", "READ UNCOMMITTED", "AUTOCOMMIT"] | None): SQL Alchemy isolation level, overriding any and all --$Isolation_level flags in SQL files. Defaults to None. If errors are raised related
            to not being able to perform queries within transactions, (for example as typical with Synapse databases), try using "AUTOCOMMIT". This will override the ability to
            commit and rollback using the Connector, so this should be handled within SQL.

    Raises:
        ValueError: Argument 'filepaths' can be left blank if run from a notebook, but from a python file this must be entered

    Returns:
        ResultList: Returns a list of results as a Kraken ResultList class.
    """

    start = datetime.now()

    queries = extract_sql(
        filepaths=filepaths,
        variables=variables,
        username=username,
        parsing_feedback=parsing_feedback,
        encoding=encoding,
    )
    results = execute_sql(
        query_list=queries,
        username=username,
        clean_df=clean_df,
        batch_size=batch_size,
        concurrent=concurrent,
        isolation_level=isolation_level,
    )
    if export_directory is not None:
        export_results(
            results=results,
            directory=export_directory,
            extension=export_extension,
            filename=export_filename,
            prefix=export_prefix,
            suffix=export_suffix,
            overwrite=export_overwrite,
            zip_filename=export_zip_filename,
            **kwargs,
        )
    readout.print(
        f"Full Run Completed in {calculate_runtime(start, datetime.now()).message}\n"
    )
    return results
