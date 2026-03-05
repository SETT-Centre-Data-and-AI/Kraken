from datetime import datetime
from typing import Any, Literal

from pandas import DataFrame

from kraken.classes.pack_lists import ResultList
from kraken.classes.packs import Result
from kraken.connection.connector import create_connector
from kraken.support.readout import readout
from kraken.support.support import calculate_runtime


def upload(
    alias: str,
    df: DataFrame,
    table: str,
    schema: str,
    alt_username: str | None = None,
    if_table_exists: Literal["append", "replace", "drop"] | None = None,
    header_case: Literal["upper", "lower"] | None = None,
    max_header_length: int | None = None,
    set_varchar_length: int | None = None,
    chunksize: int = 10_000,
    index: bool = False,
    feedback: bool = True,
    fast: bool = True,
    **kwargs: Any,
) -> None:
    """
    Summary:
        - Will connect to a database, and upload a dataframe.
        - **Note that upload always commits**
        For fine-grained commit/rollback control, generate INSERT statements manually, instantiate a Connector, and use Connector.execute().

    Args:
            - alias (str): Database alias to use for the upload.
            - df (DataFrame): Dataframe to upload.
            - table (str): Name of resulting table to be saved.
            - schema (str): Schema to write table dataframe to. A database can be appended here for services that support multiple databases (such as SQL Server), like: 'master.dbo'.
            - alt_username (str, optional): Alternative username for the database alias. Defaults to None, using the default username for the given alias.
            - if_table_exists (str, optional): Pandas sql upload behaviour if table already exists - including 'drop', 'append' or 'replace'. Defaults to None (failing).
            - header_case (bool, optional): Convert header case before upload. Accepts 'upper' or 'lower'.
            - max_header_length (int, optional): Truncates length of column and table names. Defaults to None, allowing any length.
            - set_varchar_length (int, optional): Sets maximum length of varchar columns. Defaults to None, in which case length is set to the maximum string length of each column.
            - chunksize (int, optional): Number of rows per bulk insertion. Defaults to 10000.
            - feedback (bool, optional): Allow upload progress bar feedback.
            - fast (bool, optional): If True, will attempt to execute upload by binding parameters in bulk or combining INSERT statements, significantly boosting upload speed.
                Note that on slow network speeds, `fast=True` may in fact result in a slower upload.

    Returns:
        - None
    """
    if not isinstance(alias, str):
        raise TypeError(
            "'alias' argument must be a database alias. To use an existing Connector, use connector=kraken.create_connector() and then connector.upload()"
        )

    # Prepare Connection
    connector = create_connector(alias, username=alt_username)
    connector.upload(
        df=df,
        table=table,
        schema=schema,
        if_table_exists=if_table_exists,
        header_case=header_case,
        max_header_length=max_header_length,
        set_varchar_length=set_varchar_length,
        chunksize=chunksize,
        index=index,
        feedback=feedback,
        fast=fast,
        **kwargs,
    )


def upload_results(
    alias: str,
    results: ResultList | Result,
    schema: str,
    alt_username: str | None = None,
    if_table_exists: Literal["append", "replace", "drop"] | None = None,
    header_case: Literal["upper", "lower"] | None = None,
    max_header_length: int | None = None,
    set_varchar_length: int | None = None,
    chunksize: int = 10_000,
    index: bool = False,
    feedback: bool = True,
    fast: bool = True,
    **kwargs: Any,
) -> None:
    """
    Summary:
        - Will connect to a database, and upload all dataframes within a Result or ResultList
            object, using the df_name as the table name for each.
        - For more fine-tuned control, instantiate a Connector (kraken.create_connector) and use
            that object's Connector.upload() function instead. This allows behaviour like commit,
            rollback, and connection closing to be manually controlled.

    Args:
            - alias (str): Database alias to use for the upload.
            - results (ResultList): ResultList with DataFrame objects to upload.
            - schema (str): Schema to write table dataframe to. A database can be appended here for services that support multiple databases (such as SQL Server), like: 'master.dbo'.
            - alt_username (str, optional): Alternative username for the database alias. Defaults to None, using the default username for the given alias.
            - if_table_exists (str, optional): Pandas sql upload behaviour if table already exists - including 'drop', 'append' or 'replace'. Defaults to None (failing).
            - header_case (bool, optional): Convert header case before upload. Accepts 'upper' or 'lower'.
            - max_header_length (int, optional): Truncates length of column and table names. Defaults to None, allowing any length.
            - set_varchar_length (int, optional): Sets maximum length of varchar columns. Defaults to None, in which case length is set to the maximum string length of each column.
            - chunksize (int, optional): Number of rows per bulk insertion. Defaults to 10000.
            - feedback (bool, optional): Allow upload progress bar feedback.
            - fast (bool, optional): If True, will attempt to execute upload by binding parameters in bulk or combining INSERT statements, significantly boosting upload speed.
                Note that on slow network speeds, `fast=True` may in fact result in a slower upload.

    Returns:
        - None
    """
    # Check Types
    if isinstance(results, DataFrame):
        raise TypeError(
            "'results' arugument must be a Result or ResultList class type, "
            + "and not a lone dataframe as a table name cannot be derived. "
            + "Please consider using upload_dataframe() instead."
        )
    if not isinstance(results, (ResultList, Result)):
        raise TypeError("'results' argument must be a Result or ResultList class type")

    if isinstance(results, Result):
        results = ResultList([results])

    if not isinstance(alias, str):
        raise TypeError(
            "'alias' argument must be a database alias. To use an existing Connector, use connector=kraken.create_connector() and then connector.upload()"
        )

    # Prepare to Upload
    start = datetime.now()
    s = "" if len(results) == 1 else "s"
    readout.print(f"Preparing to upload {len(results)} dataframe{s}...")

    # Prepare Connection
    connector = create_connector(alias=alias, username=alt_username)
    connector.connect(allow_feedback=False)

    m_schema = f"{schema}." if schema else ""
    header_pad = max(len(result.df_name) for result in results) + len(m_schema) + 2

    for result in results:
        # Prepare
        df = result.df
        table = result.df_name
        upload_name = f"'{m_schema}{result.df_name}'".ljust(header_pad)
        progress_header = f"  - Uploading to {upload_name}"

        # Upload
        connector.upload(
            df=df,
            table=table,
            schema=schema,
            if_table_exists=if_table_exists,
            header_case=header_case,
            max_header_length=max_header_length,
            set_varchar_length=set_varchar_length,
            chunksize=chunksize,
            index=index,
            progress_header=progress_header,
            feedback=feedback,
            fast=fast,
            **kwargs,
        )

    connector.close_connection()
    readout.print(f"Table{s} uploaded in {calculate_runtime(start).message}\n")
