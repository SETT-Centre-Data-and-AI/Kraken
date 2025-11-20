import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Generic, Literal, Protocol, Type, TypeVar, runtime_checkable

import pyodbc  # type: ignore[import-not-found]
import sqlalchemy as sa
from pandas import DataFrame
from sqlalchemy.engine.url import URL

from kraken.analysis.data_manipulation import check_df_integers as clean_dataframe
from kraken.connection.support import (
    _compile_pyodbc_connection_string,
    _split_pyodbc_connection_string,
)
from kraken.credentials.credentials import Credentials
from kraken.credentials.helpers import fetch_credentials
from kraken.exceptions import (
    CommitError,
    DatabaseConnectionError,
    QueryExecutionError,
)
from kraken.platforms.config import PlatformConfig, get_platform_config
from kraken.support.progress import Progress
from kraken.support.readout import readout
from kraken.support.support import (
    _prepare_sql_snippet,
    abbreviate_number,
)
from kraken.support.warnings import DuplicateColumnWarning

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


@runtime_checkable
class CursorLike(Protocol):
    def close(self) -> None: ...

    @property
    def description(self) -> Any: ...

    def nextset(self) -> bool | None: ...

    def fetchmany(self, size: int = ...) -> Sequence[Any]: ...

    def fetchall(self) -> Sequence[Any]: ...

    def execute(self, query: str) -> Self: ...


TCursor = TypeVar("TCursor", bound=CursorLike, covariant=True)


class ConnectionLike(Protocol, Generic[TCursor]):
    def close(self) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def cursor(self, *args: Any, **kwargs: Any) -> TCursor: ...


TConn = TypeVar("TConn", bound=ConnectionLike)


class Connector(ABC, Generic[TConn, TCursor]):
    def __init__(
        self,
        alias: str,
        username: str | None = None,
        batch_size: int | None = 5000,
        feedback: bool = True,
        custom_credentials: Credentials | None = None,
        autocommit: bool = True,
        autoclose: bool = True,
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
    ) -> None:
        self.credentials: Credentials = (
            custom_credentials
            if custom_credentials
            else fetch_credentials(alias=alias, username=username)
        )
        self.config: PlatformConfig = get_platform_config(
            platform=self.credentials.platform
        )
        self.alias: str | None = self.credentials.alias
        self.platform: str | None = self.credentials.platform
        self.connection_string: str | URL = self.credentials.connection_string
        self.batch_size: int = batch_size if batch_size is not None else 0
        self.feedback: bool = feedback
        self.autocommit: bool = autocommit
        self.autoclose: bool = autoclose
        self.isolation_level: (
            Literal[
                "SERIALIZABLE",
                "REPEATABLE READ",
                "READ COMMITTED",
                "READ UNCOMMITTED",
                "AUTOCOMMIT",
            ]
            | None
        ) = isolation_level

        self.engine: sa.Engine | None = None
        self.connection: TConn | None = None
        self.cursor: TCursor | None = None
        self.connected: bool = False
        self.multiset_supported: bool = False

    def __repr__(self) -> str:
        return (
            f"Connector(alias='{self.alias}', username='{self.credentials.username}', "
            + f"state='{('Connected' if self.connected else 'Disconnected')}', "
            + f"platform='{self.platform}', library='{self.config.sql_library}'"
            + ")"
        )

    def _say(
        self, *values: object, sep: str = " ", end: str = "\n", flush: bool = False
    ) -> None:
        if self.feedback:
            readout.print(*values, sep=sep, end=end, flush=flush)

    ### Functions ###
    def set_autocommit(self, autocommit: bool) -> None:
        """Changes default Connector commit behaviour after executing queries.

        Args:
            autocommit (bool): Whether the Connector should commit queries.
                Can be overridden in each execute() call.
        """
        self.autocommit = autocommit

    def set_autoclose(self, autoclose: bool) -> None:
        """Changes default Connector connection closing behaviour after executing queries.

        Args:
            autoclose (bool): Whether the Connector should close the connection after executing queries.
                Can be overridden in each execute() call.
        """
        self.autoclose = autoclose

    def set_batch_size(self, batch_size: int) -> None:
        """Changes default Connector batch size for fetching rows.

        Args:
            batch_size (bool): Number of rows to fetch in each batch. Turn off batching with 0.
        """
        self.batch_size = batch_size

    def connect(
        self,
        allow_feedback: bool = False,
    ) -> None:
        """Connects to database, attaches the connection to the Connector,
        and begins a new transaction.

        Args:
            allow_feedback (bool): Whether to print feedback.

        Raises:
            DatabaseConnectionError: if error in connection
        """
        message_alias = (
            f"'{self.alias}' database '{self.get_database()}'"
            if self.get_database()
            else f"'{self.alias}'"
        )
        try:
            if not self.is_connected():
                self._connect_child()

            self.connected = True
            self.__set_multiset_support()

            if allow_feedback:
                self._say(f"Connected to {message_alias}")

        except Exception as e:
            error_text = (
                f"Could not connect to {message_alias} - check user permissions"
            )
            raise DatabaseConnectionError(f"{error_text} // from error: {e}") from e

    def close_connection(self) -> None:
        """Closes connection, if open.

        Returns:
            None (closes connection)
        """
        self.__close_cursor()
        if self.connection:
            if self.is_connected():
                self.connection.close()
        if self.cursor:
            self.cursor.close()

        self.cursor = None
        self.connection = None
        self.connected = False

    def commit(self) -> None:
        """Commit all uncommited queries in the current connection.

        Raises:
            CommitError: if connection is closed.
        """
        if self.is_connected():
            self.connection.commit()  # type: ignore[union-attr]
        else:
            raise CommitError(
                "Cannot commit as Connector.connection is closed. Remember to set_autoclose = False when managing commits manually."
            )

    def rollback(self) -> None:
        """Rollback all uncommitted queries in the current connection, and
        begins a new transaction.

        Raises:
            CommitError: if query cannot be rolled back
        """
        if self.is_connected():
            self.connection.rollback()  # type: ignore[union-attr]
        else:
            raise CommitError(
                "Cannot rollback as Connector.connection is closed. Remember to set_autoclose = False when managing commits manually."
            )

    def execute(
        self,
        query: str,
        query_name: str | None = None,
        commit: bool | None = None,
        close: bool | None = None,
        batch_size: int | None = None,
        clean_df: bool = True,
        check_column_duplicates: bool = True,
        header_indent: str = "",
        progress: bool = True,
    ) -> DataFrame | list[DataFrame]:
        """Execute SQL query using connection.

        Args:
            -   query (str): SQL Query
            -   query_name (str):
            -   commit (bool): If True, connection commits after executing. Defaults to None, using the Connector default (Connector.autocommit).
            -   close (bool): If True, closes the connection after executing. Defaults to None, using the Connector default (Connector.autoclose).
            -   batch_size (int): Downloads data in batches. Uses current Connector.batch_size if None. Set to 0 to
                download all data without batching.
            -   clean_df (bool): Cleans DataFrame after pandas generation, including converting float64 to Int64 if
                applicable (recommended).
            -   check_column_duplicates (bool): Checks DataFrame for duplicate column names and throws warning.
            -   header_indent (str): Prefix each readout with an indent (e.g. ' -> ')
            -   progress (bool): If True, activates query progress bar. Switching to False may save a little
                overhead if looping over a large number of very fast queries.

        Returns:
            DataFrame: Pandas DataFrame with results of query
        """
        # Set Parameters
        commit = commit if isinstance(commit, bool) else self.autocommit
        close = close if isinstance(close, bool) else self.autoclose
        self.batch_size = batch_size if batch_size is not None else self.batch_size
        query_name = (
            query_name
            if query_name
            else f"'{_prepare_sql_snippet(query, max_characters=20)}'"
        )
        indent = header_indent
        dataframes = None

        status = "Executing  " if self.is_connected() else "Connecting "
        header = f"{indent}Query: {query_name} {status} |"

        with Progress(
            header=header, active=progress, auto_update_interval=0.5
        ) as progress_ctx:
            self.connect(allow_feedback=False)
            progress_ctx.update_header(
                header=f"{indent}Query: {query_name} Executing   |"
            )
            progress_ctx.start_auto_update()

            try:
                if not self.cursor:
                    self.cursor = self.connection.cursor()
                self.cursor.execute(query)

            except Exception as e:
                self.__close_connection_in_error()
                raise QueryExecutionError(str(e)) from e

            dataframes = self.__fetch_data(
                query_name=query_name,
                progress=progress_ctx,
                indent=indent,
                clean_df=clean_df,
                check_column_duplicates=check_column_duplicates,
            )

            self.__execute_finish(commit=commit, close=close)

            if len(dataframes) == 1:
                return dataframes[0]
            else:
                return dataframes

    def upload(
        self,
        df: DataFrame,
        table: str,
        schema: str,
        if_table_exists: Literal["append", "replace", "drop"] | None = None,
        header_case: Literal["upper", "lower"] | None = None,
        max_header_length: int | None = None,
        set_varchar_length: int | None = None,
        chunksize: int = 10_000,
        index: bool = False,
        feedback: bool = True,
        progress_header: str | None = None,
        fast: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Summary:
            - Uploads dataframe to database.
            - **Note that upload always commits**
            For fine-grained commit/rollback control, generate INSERT statements manually, and use Connector.execute().

        Args:
            - df (DataFrame): Dataframe to upload.
            - table (str): Name of resulting table to be saved.
            - schema (str): Schema to write table dataframe to. A database can be appended here for services that support multiple databases (such as SQL Server), like: 'master.dbo'.
            - if_table_exists (str, optional): Pandas sql upload behaviour if table already exists - including 'drop', 'append' or 'replace'. Defaults to None (failing).
            - header_case (bool, optional): Convert header case before upload. Accepts 'upper' or 'lower'.
            - max_header_length (int, optional): Truncates length of column and table names. Defaults to None, allowing any length.
            - set_varchar_length (int, optional): Sets maximum length of varchar columns. Defaults to None, in which case length is set to the maximum string length of each column.
            - chunksize (int, optional): Number of rows per bulk insertion. Defaults to 10000.
            - feedback (bool, optional): Can be ignored - affects behaviour of readouts only. Utilised by encompassing functions.
            - progress_header (str, optional): Can be ignored - affects behaviour of readouts only. Utilised by encompassing functions.
            - fast (bool, optional): If True, will attempt to execute upload by binding parameters in bulk or combining INSERT statements, significantly boosting upload speed.
                Note that on slow network speeds, `fast=True` may in fact result in a slower upload.

        Raises:
            - ValueError: Raised if column names detected, either before or after column name length truncation

        Returns:
            - None
        """
        from kraken.uploading.uploader import Uploader

        # Checks
        if_table_exists = if_table_exists.lower() if if_table_exists else None

        if not self.autocommit:
            readout.warn(
                "WARNING: Connector.autocommit is set to False, but upload() will always commit.\n"
                "For fine-grained control of commit/rollback behaviour, "
                "generate INSERT SQL from the DataFrame manually and use the Connector.execute() function"
            )

        # Prepare Connection
        if not self.is_connected():
            self.connect(allow_feedback=feedback)

        # Upload DataFrame
        uploader = Uploader(
            connector=self,
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
            progress_header=progress_header,
            fast=fast,
            **kwargs,
        )

        uploader.upload()

    ### Private Functions ###
    def __close_connection_in_error(self) -> None:
        try:
            self.close_connection()
        except Exception:
            # Error closing connection, try to force
            try:
                self.connect()
                self.close_connection()
            except Exception:
                pass

    def __close_cursor(self) -> None:
        if self.cursor:
            self.cursor.close()
            self.cursor = None

    def __set_multiset_support(self) -> None:
        """Detect whether the current cursor supports `.nextset()` (i.e., multiple result sets)."""
        if self.cursor:
            self.multiset_supported = callable(getattr(self.cursor, "nextset", None))

    def __process_dataframe(
        self, df: DataFrame, clean_df: bool, check_column_duplicates: bool
    ) -> DataFrame:
        if df is None:
            return

        df = clean_dataframe(df) if clean_df else df
        if check_column_duplicates and df.columns.has_duplicates:
            dupe_cols = df.columns[df.columns.duplicated()].to_list()
            readout.warn(
                DuplicateColumnWarning(
                    f"WARNING: Duplicate column(s) {dupe_cols} found in the dataframe."
                )
            )
        return df

    def __fetch_columns(self) -> list[str]:
        return [column[0] for column in self.cursor.description]

    def __fetch_rows(self) -> list[tuple]:
        if self.batch_size:
            return [tuple(row) for row in self.cursor.fetchmany(self.batch_size)]
        else:
            return [tuple(row) for row in self.cursor.fetchall()]

    def __fetch_data(
        self,
        query_name: str,
        progress: Progress,
        indent: str = "",
        clean_df: bool = True,
        check_column_duplicates: bool = True,
    ) -> list[DataFrame]:
        dataframes = []
        set_count = 0
        row_count = 0

        while True:
            if self.cursor.description is not None:
                # Process the current result set
                set_count += 1
                set_text = (
                    " \033[1;33m(Multiple DataFrames)\033[0m" if set_count > 1 else ""
                )
                progress.update_header(
                    header=f"{indent}Query: {query_name} Downloading |",
                    suffix=f"{abbreviate_number(row_count)} Rows{set_text}",
                )
                progress.update()

                columns = self.__fetch_columns()
                rows: list[tuple] = []

                while True:
                    batch = self.__fetch_rows()
                    if not batch:
                        break
                    rows.extend(batch)
                    row_count += len(batch)
                    progress.update_header(
                        suffix=f"{abbreviate_number(row_count)} Rows{set_text}"
                    )
                    progress.update()

                # Only add a DataFrame if it has columns (i.e., it's not just a USE/SET/etc)
                if columns:
                    progress.update_header(
                        header=f"{indent}Query: {query_name} Processing  |"
                    )
                    df = DataFrame(data=rows, columns=columns)
                    df = self.__process_dataframe(
                        df=df,
                        clean_df=clean_df,
                        check_column_duplicates=check_column_duplicates,
                    )

                    if df is not None:
                        dataframes.append(df)

            # Move to next result set if possible
            try:
                if not self.multiset_supported or not self.cursor.nextset():
                    break
            except Exception:
                # certain drivers like psycopg2 report multiset_supported
                # but then fail on cursor.nextset() with a NotSupported error
                break

        progress.update_header(header=f"{indent}Query: {query_name} Completed   |")
        progress.finish()

        return dataframes

    def __execute_finish(self, commit: bool, close: bool) -> None:
        if commit and self.connection:
            self.connection.commit()

        self.__close_cursor()

        if close:
            self.close_connection()

    @abstractmethod
    def switch_database(self, database: str) -> None:
        pass

    @abstractmethod
    def get_database(self) -> str | None:
        pass

    @abstractmethod
    def _connect_child(self) -> None:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass


class SaConnector(
    Connector[sa.PoolProxiedConnection, sa.engine.interfaces.DBAPICursor]
):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.engine: sa.Engine = self.create_engine()
        self.connection: sa.PoolProxiedConnection

    def create_engine(self) -> sa.Engine:
        """Creates SQLAlchemy Engine, sets self.engine and returns.

        Returns:
            Engine: SQLAlchemy Engine
        """
        self.engine = sa.create_engine(
            url=self.connection_string, isolation_level=self.isolation_level
        )
        return self.engine

    def is_connected(self) -> bool:
        return bool(self.connection and self.connection.is_valid)

    def _connect_child(self) -> None:
        """Create SQL Alchemy Connection.

        Returns:
            saConnection: SQL Alchemy Connection
        """
        self.connection = self.engine.raw_connection()
        self.cursor = self.connection.cursor()

    def get_database(self) -> str | None:
        """Fetch database name from self.connection_string.

        Returns:
            str: database name
        """
        return self.engine.url.database

    def switch_database(self, database: str) -> None:
        """Amends URL of existing SQL ALchemy engine with new database, and creates new
        engine.

        Args:
            database (str): New Database

        Returns:
            None: (Amends engine to point to new database)
        """
        if not self.config.multiple_db_support:
            raise ValueError(
                f"Platform '{self.platform}' does not support multiple databases - cannot switch database"
            )
        self.close_connection()
        self.connection_string = self.engine.url.set(database=database)
        self.create_engine()
        self._say(f"Switching to database '{database}'")


class PyoConnector(Connector[pyodbc.Connection, pyodbc.Cursor]):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.connection_string: str
        self.connection: pyodbc.Connection

    def _connect_child(self) -> None:
        """Create pyodbc Connection.

        Returns:
            pyoConnection: pyodbc Connection
        """
        self.connection = pyodbc.connect(self.connection_string)
        self.cursor: pyodbc.Cursor = self.connection.cursor()

    def is_connected(self) -> bool:
        return bool(self.connection and not self.connection.closed)

    def get_database(self) -> str | None:
        """Fetch database name from self.connection_string.

        Returns:
            str: database name
        """
        for key, value in _split_pyodbc_connection_string(
            connection_string=self.connection_string
        ).items():
            if key.strip().upper() in ["DATABASE", "INITIAL CATALOG"]:
                return value.strip()
        return None

    def switch_database(self, database: str) -> None:
        """Closes connection if open, and amends URL of existing pyodbc
        connection_string with new database. Does not connect.

        Args:
            database (str): New Database

        Returns:
            None: (Amends connection_string to point to new database)
        """

        if not self.config.multiple_db_support:
            raise ValueError(
                f"Platform '{self.platform}' does not support multiple databases - cannot switch database"
            )

        connection_string_dictionary = _split_pyodbc_connection_string(
            connection_string=self.connection_string
        )
        for key in connection_string_dictionary.keys():
            if key.strip().upper() in ["DATABASE", "INITIAL CATALOG"]:
                connection_string_dictionary[key] = database

        self.connection_string = _compile_pyodbc_connection_string(
            connection_string_dictionary=connection_string_dictionary
        )

        self.close_connection()
        self._say(f"Switching to database '{database}'")


def create_connector(
    alias: str,
    username: str | None = None,
    custom_credentials: Credentials | None = None,
    autocommit: bool = True,
    autoclose: bool = True,
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
) -> Connector:
    """Creates Kraken Connector.

    Args:
        alias (str): Kraken database service alias
        username (str): Database service username. If None, Kraken will attempt to fetch the default
        custom_credentials (Credentials): If a custom Credentials object is provided, Kraken will use this to connect rather fetching credentials.
        autocommit (bool): Whether the Connector commits queries by default. Overridable in each execute(). Defaults to True.
        autoclose (bool): Whether the Connector closes the connection after query. Overridable in each execute(). Defaults to True.
        isolation_level (str | None): SQL Alchemy isolation level. Defaults to None. If errors are raised related to not being able to perform
        queries within transactions, (for example as typical with Synapse databases), try using "AUTOCOMMIT". This will override the ability to
        commit and rollback using the Connector, so this should be handled within SQL.

    Returns:
        Connector: Kraken Connector class
    """
    credentials = (
        custom_credentials
        if custom_credentials
        else fetch_credentials(alias=alias, username=username)
    )
    config = get_platform_config(credentials.platform)

    connector: Type[SaConnector | PyoConnector]
    if config.sql_library == "sqlalchemy":
        connector = SaConnector
    elif config.sql_library == "pyodbc":
        connector = PyoConnector
    else:
        raise ValueError("Invalid Connector")

    return connector(
        alias=credentials.alias,
        username=credentials.username,
        custom_credentials=custom_credentials,
        autocommit=autocommit,
        autoclose=autoclose,
        isolation_level=isolation_level,
    )
