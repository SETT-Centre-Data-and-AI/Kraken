from pathlib import Path

from kraken.classes.pack_lists import QueryList
from kraken.classes.packs import Query, SQLFile
from kraken.credentials.credential_manager import CredentialManager
from kraken.parsing.parsing import Parser
from kraken.ribosome.support import (
    _check_filepaths_type,
    _check_variables_type,
    _fetch_split_sql_behaviour,
)
from kraken.support.readout import readout
from kraken.support.support import (
    _check_df_name_duplicates,
    _count_instructions,
    _extract_instruction,
    _load_filepaths,
    _prepare_sql_snippet,
    decode,
)


### Extract SQL from files ###
def extract_sql(
    filepaths: str | Path | list[str] | list[Path] = "",
    variables: dict[str, str] = {},
    username: str | None = None,
    parsing_feedback: bool = False,
    encoding: str = "utf-8",
) -> QueryList:
    """
    Summary:
        Takes paths, or list of paths, to files or directories. Searches paths and directories for SQL
        files, and generates a list of filepaths to each SQL file. Outputs list of parsed queries
        (class: Query), ready for execution.

    Args:
        filepaths (str | list[str]): Path or list of paths to SQL files or directories of SQL files.
            If left blank, Kraken will search in the current directory. Defaults to "".
        variables (dict): Dictionary of DEFINE/SET variables to override in the SQL execution
        username (str): If entered, Kraken can use a specific username to later execute these queries.
            Otherwise, it will later attempt to fetch a default username from credentials. Defaults to None.
        parsing_feedback (bool): If True, Kraken will print a summary report of the parsed queries.
            Defaults to False.
        encoding (str): Encoding of SQL files. Defaults to "utf-8".

    Returns:
        list[Query]: list of queries (class = Query)
    """

    # Assertions
    _check_filepaths_type(filepaths=filepaths)
    _check_variables_type(variables)
    variables = variables or {}

    # Load SQL Files
    readout.print("Extracting SQL Files...")
    filepaths = _load_filepaths(filepaths, ".sql")
    sql_file_list = _create_sql_file_list(
        filepaths=filepaths, username=username, encoding=encoding
    )
    readout.print(f"  {len(sql_file_list)} files loaded")

    # Prepare Queries
    readout.print(f"\nParsing {len(sql_file_list)} SQL Files...")
    query_list = QueryList()
    for sql_file in sql_file_list:
        readout.print(f"  Parsing '{sql_file.filename}'... ", end="")
        queries = _create_queries(sql_file, variables=variables)
        plurality = "query" if len(queries) == 1 else "queries"
        query_list.extend(queries)

        readout.print(
            f"prepared to target database '{sql_file.db_alias}' with"
            f" {len(queries)} {plurality}:"
        )

        # Print Query Snippets
        if sql_file.variables:
            readout.print(f"   - Variables Used: {sql_file.variables}")

        for query in queries:
            sql_snippet = _prepare_sql_snippet(query.sql)
            readout.print(
                f"   - Query: '{query.df_name}' /// SQL Snippet: {sql_snippet}"
            )

        readout.print("\n", end="")

    if not query_list:
        readout.warn("WARNING: No queries extracted from SQL files")

    # Check Queries for Duplicate df_names
    _check_df_name_duplicates(query_list)

    if parsing_feedback:
        for sql_file in sql_file_list:
            if sql_file.parsing_report:
                readout.print(f"\nParsing Report for '{sql_file.filename}':")
                readout.print(sql_file.parsing_report)

    return query_list


### Helper: Create SQL Files List from filepaths ###
def _create_sql_file_list(
    filepaths: list[Path], username: str | None = None, encoding: str = "utf-8"
) -> list[SQLFile]:
    sql_file_list = []
    for filepath in filepaths:
        split_flag_warning_files = []
        with open(filepath, encoding=encoding) as file:
            filename = str(filepath.name).split(".")[0]
            raw_sql = file.read()
            db_alias = _extract_instruction(raw_sql, "database") or decode(
                "DATABASE", "KRAKEN_DEFAULT"
            )
            isolation_level = _extract_instruction(
                raw_sql, "isolation_level"
            ) or _extract_instruction(raw_sql, "isolationlevel")
            split_queries = _fetch_split_sql_behaviour(raw_sql, filepath)

            if db_alias is None:
                readout.warn(
                    f"  -> WARNING: No database comment flag detected in '{filename}',"
                    " and no default database set. Consider running"
                    " kraken.set_kraken_defaults()."
                )

            credential_manager = CredentialManager()
            credentials = credential_manager.fetch_credentials(
                alias=db_alias,  # type: ignore
                username=username,
            )

            sql_file = SQLFile(
                filepath=filepath,
                filename=filename,
                db_alias=db_alias,
                platform=credentials.platform,
                raw_sql=raw_sql,
                variables={},
                split_queries=split_queries,
                isolation_level=isolation_level,  # type: ignore
            )
            sql_file_list.append(sql_file)

            if not split_queries and _count_instructions(raw_sql, "DATAFRAME") > 1:
                split_flag_warning_files.append(filepath)

            if split_flag_warning_files:
                readout.warn(
                    f"  -> WARNING: --$Split=False in file '{filename}', but multiple --$Dataframe flags found."
                    "\n     Multiple --$DataFrame flags cannot be used without splitting queries, "
                    "and Kraken will generate a DataFrame name based on the first flag on execution. "
                    "To specifically name DataFrames, consider omitting --$Split=False."
                )

    return sql_file_list


### Helper: Create Query from SQLFile ###
def _create_queries(sql_file: SQLFile, variables: dict[str, str] = {}) -> list[Query]:
    variables = variables or {}
    query_list = []
    split_queries = []

    parser = Parser(platform=sql_file.platform)
    parser.parse_sql(
        input_sql=sql_file.raw_sql,
        user_variables=variables,
        split_queries=sql_file.split_queries,
    )
    sql_file.parsing_report = parser.summary_report
    queries = [query.sql for query in parser.queries]
    active_variables = parser.final_variables

    split_queries.extend(queries)
    sql_file.variables = active_variables

    # Creation of queries
    for i, query in enumerate(split_queries):
        backup_df_name = (
            sql_file.filename if i == 0 else f"{sql_file.filename}_{i + 1:02d}"
        )
        df_name = _extract_instruction(query, "dataframe") or backup_df_name
        try:
            arraysize_raw = _extract_instruction(query, "arraysize")
            arraysize = int(arraysize_raw) if arraysize_raw else None
        except ValueError as e:
            arraysize = None
            raise ValueError(f"arraysize parameter should be an integer: {e}") from e
        query_list.append(
            Query(
                filepath=sql_file.filepath,
                filename=sql_file.filename,
                db_alias=sql_file.db_alias,
                platform=sql_file.platform,
                df_name=df_name,
                arraysize=arraysize,
                sql=query,
                parsing_report=parser.summary_report,
                isolation_level=sql_file.isolation_level,
            )
        )

    return query_list
