from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from pandas import DataFrame

from kraken.classes.pack_lists import QueryList, ResultList
from kraken.classes.packs import Result
from kraken.connection.connector import create_connector
from kraken.support.progress import Progress
from kraken.support.readout import readout
from kraken.support.support import (
    _check_df_name_duplicates,
    calculate_runtime,
)
from kraken.support.support_checks import _enforce_type


def execute(
    alias: str,
    query: str,
    query_name: str | None = None,
    username: str | None = None,
    batch_size: int | None = None,
    clean_df: bool = True,
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
) -> DataFrame | list[DataFrame]:
    """
    Executes entered SQL against a given database alias and returns DataFrame of results, if applicable.
    For greater control or to reuse a connection to optimise numerous queries, first instantiate a
    `Connector` object and then use its `execute()` method:

    `connector = kraken.create_connector(alias='alias')`
    `connector.execute(query='query', *args)`

    Args:
        alias (str): Database alias to execute SQL against.
        query (str): SQL to execute. Supports single queries.
        query_name (str, optional): Query name for user feedback, else readouts will provide a SQL snippet.
        username (str, optional): If blank, Kraken will use the default username for the given alias. Otherwise,
            Kraken will fetch saved credentials for the given username/database alias pair. Defaults to None.
        batch_size (int): Downloads rows in batches. Use `batch_size=0` to fetch all data without batching.
        clean_df (bool): Checks DataFrame after pandas generation and applies cleaning, including converting
            float64 to Int64 if applicable (recommended).
        isolation_level (Literal["SERIALIZABLE", "REPEATABLE READ", "READ COMMITTED", "READ UNCOMMITTED", "AUTOCOMMIT"] | None):
            SQL Alchemy isolation level. Defaults to None. If errors are raised related to not being able to perform
            queries within transactions, (for example as typical with Synapse databases), try using "AUTOCOMMIT".
            This will override the ability to commit and rollback using the Connector, so this should be handled within SQL.
        kwargs: Forwards keyword arguments to create_connector, which in turn forwards them to SaConnector().create_engine.

    Returns:
        Results (DataFrame): Results of query (if data returned)
    """
    _enforce_type(
        alias,
        "alias",
        str,
        (
            "alias must be database alias. For more fine-tuned control, first instantiate a "
            + "Connector object with connector=kraken.create_connector() and then use connector.execute()"
        ),
    )

    df = None
    query_name = f"'{query_name}'" if query_name else None
    connector = create_connector(
        alias=alias, username=username, isolation_level=isolation_level, **kwargs
    )
    connector.connect(allow_feedback=False)
    df = connector.execute(
        query=query,
        query_name=query_name,
        close=True,
        commit=True,
        batch_size=batch_size,
        clean_df=clean_df,
    )

    return df


def create_db_sql_mapping(
    query_list: QueryList,
) -> dict[
    tuple[
        Path,
        str,
        str | None,
        str | None,
    ],
    QueryList,
]:
    mapping: dict[
        tuple[
            Path,
            str,
            str | None,
            str | None,
        ],
        QueryList,
    ] = defaultdict(QueryList)

    for query in query_list:
        mapping[
            (
                query.filepath,
                query.filename,
                query.db_alias,
                query.isolation_level,
            )
        ].append(query)

    return mapping


def execute_sql(
    query_list: QueryList,
    username: str | None = None,
    clean_df: bool = True,
    batch_size: int | None = None,
    concurrent: bool = False,
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
) -> ResultList:
    """
    Summary:
        Takes a QueryList of Query objects, as prepared and output by extract_sql(). Executes this list against the
        databases set within the Query objects. Returns a list of Results (class = ResultList).

    Args:
        query_list (list[Query]): List of QueryList of Query objects prepared by extract_sql()
        username (str, optional): Overriding username to fetch database credentials. Defaults to None. WARNING:
            Kraken will attempt to use this username to execute all queries.
        clean_df (bool): Checks each DataFrame after pandas generation and applies cleaning, including converting
            float64 to Int64 if applicable (recommended).
        batch_size (int): Downloads rows in batches. Use `batch_size=0` to fetch all data without batching.
        concurrent (bool): If True, executes all SQL files concurrently. Queries within each SQL file will still
            execute sequentially. Defaults to False.
        isolation_level (Literal["SERIALIZABLE", "REPEATABLE READ", "READ COMMITTED", "READ UNCOMMITTED", "AUTOCOMMIT"] | None):
            SQL Alchemy isolation level, overriding any and all --$Isolation_level flags in SQL files. Defaults to None.
            If errors are raised related to not being able to perform queries within transactions, (for example as typical
            with Synapse databases), try using "AUTOCOMMIT". This will override the ability to commit and rollback using
            the Connector, so this should be handled within SQL.

    Returns:
        ResultList: List of Results
    """
    readout.print(f"Executing {len(query_list)} SQL Queries...", end="")
    execution_start = datetime.now()
    db_sql_mapping = create_db_sql_mapping(query_list=query_list)

    result_list = __execute_all_queries(
        db_sql_mapping=db_sql_mapping,
        username=username,
        clean_df=clean_df,
        batch_size=batch_size,
        concurrent=concurrent,
        isolation_level=isolation_level,
    )

    # Check for Duplicates #
    _check_df_name_duplicates(result_list)

    # Print Final Readouts #
    readout.print(
        f"\nExecution Complete in {calculate_runtime(execution_start, datetime.now()).message}",
        end="",
    )

    if len(result_list) == 0:
        readout.print(" (no dataframes returned)")
    else:
        readout.print(f", returned {len(result_list)} dataframes:")
        for result in result_list:
            readout.print(
                f" - {result.df_name} ({len(result.df.columns)} columns, {len(result.df.index)} rows)"
            )

    readout.print("\n", end="")
    return result_list


def __execute_all_queries(
    db_sql_mapping: dict[
        tuple[
            Path,
            str,
            str | None,
            str | None,
        ],
        QueryList,
    ],
    username: str | None,
    clean_df: bool,
    batch_size: int | None,
    concurrent: bool = False,
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
) -> ResultList:
    result_list = ResultList()
    total_queries = sum(len(query_list) for query_list in db_sql_mapping.values())
    completed_queries = 0
    completed_queries_lock = Lock()
    concurrent_progress = None

    def _process_sql_file(
        file_key: tuple[
            Path,
            str,
            str | None,
            str | None,
        ],
        query_list: QueryList,
        concurrent: bool = False,
    ) -> list[Result]:
        (_, filename, db_alias, file_isolation_level) = file_key
        results = []

        text = (
            f"  Executing '{filename}'... \n"
            if concurrent
            else f"\n  Executing '{filename}'... "
        )
        readout.print(text, end="")

        if not db_alias:
            raise ValueError(
                f"As per earlier warning during extraction, no database comment flag detected in '{filename}', and no default database set. Consider running kraken.set_kraken_defaults() to set a default fallback database, and/or add a --$Database = xxx flag in your SQL file."
            )

        max_df_name_length = max(len(query.df_name) for query in query_list) + 3
        start = datetime.now()
        connector = create_connector(
            alias=db_alias,
            username=username,
            isolation_level=isolation_level or file_isolation_level,  # type: ignore
        )
        if not concurrent:
            readout.print(
                f"connected to '{connector.alias}' ({calculate_runtime(start=start).message})"
            )

        for query in query_list:
            connector.kwargs["arraysize"] = query.arraysize
            df = connector.execute(
                query=query.sql,
                query_name=f"'{query.df_name}'".ljust(max_df_name_length),
                close=False,
                clean_df=clean_df,
                batch_size=batch_size,
                header_indent="  - ",
                progress=False if concurrent else True,
            )

            if isinstance(df, DataFrame):
                df_list = [df]
            elif isinstance(df, list):
                df_list = df
            else:
                continue

            for i, df in enumerate(df_list, start=1):
                df_name = query.df_name
                if i > 1:
                    df_name = f"{df_name}_{i:02d}"

                results.append(
                    Result(
                        df=df,
                        df_name=df_name,
                        filename=query.filename,
                        filepath=query.filepath,
                        db_alias=query.db_alias,
                        platform=query.platform,
                        sql=query.sql,
                        query_pack=query,
                    )
                )

            if concurrent_progress:
                with completed_queries_lock:
                    nonlocal completed_queries
                    completed_queries += 1
                    concurrent_progress.update_header(
                        suffix=f"{completed_queries}/{total_queries} Queries"
                    )
                    concurrent_progress.update()

        connector.close_connection()
        return results

    if concurrent:
        readout.print("\n", end="")
        with Progress(
            header="  - Executing Files Concurrently",
            auto_update=True,
            suffix=f"0/{total_queries} Queries",
            auto_update_interval=0.5,
        ) as concurrent_progress:
            with ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(
                        _process_sql_file, file_key, query_list, concurrent
                    ): file_key
                    for file_key, query_list in db_sql_mapping.items()
                }
                for future in as_completed(futures):
                    result_list.extend(future.result())

        concurrent_progress.finish()

    else:
        for file_key, query_list in db_sql_mapping.items():
            result_list.extend(_process_sql_file(file_key, query_list, concurrent))

    return result_list
