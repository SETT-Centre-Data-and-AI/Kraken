from typing import Any, Literal

from pandas import DataFrame
from pandas.core.dtypes.common import is_dict_like
from sqlalchemy import Connection as SaConnection
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import InvalidRequestError, ProgrammingError
from sqlalchemy.types import FLOAT, VARCHAR

from kraken.connection.connector import Connector
from kraken.exceptions import (
    QueryExecutionError,
    UnstructuredDataFrameError,
    UploadConflictError,
    UploadError,
)
from kraken.support.progress import Progress
from kraken.support.support_checks import (
    _enforce_in_list,
    _enforce_type,
)
from kraken.uploading.support import (
    HEADER_CASE_OPTIONS,
    TABLE_EXISTS_OPTIONS,
    _convert_dtypes,
    _convert_headers,
    _force_dtypes_string,
    _truncate_cols,
)


class Uploader:
    def __init__(
        self,
        connector: Connector,
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
        self.parent_connector: Connector = connector
        self.table: str = table
        self.schema: str = schema
        self.schema_m: str = f"{schema}." if schema else ""
        self.if_table_exists: str | None = (
            if_table_exists.lower() if if_table_exists else None
        )
        self.header_case: str | None = header_case.lower() if header_case else None
        self.max_header_length: int | None = max_header_length
        self.set_varchar_length: int | None = set_varchar_length
        self.chunksize: int = chunksize
        self.index: bool = index
        self.feedback: bool = feedback
        self.progress_header: str = (
            progress_header if progress_header else f"Uploading to '{schema}.{table}'"
        )
        self.kwargs: dict = kwargs
        self.__enforce_upload_argument_types()
        self.df: DataFrame = self.__prepare_dataframe_for_upload(df)
        self.dtype_remap: dict[str, FLOAT[Any] | VARCHAR] = self.__get_dtypes()
        self.connection: SaConnection | None = None
        self.cursor = None
        self.connected: bool = False
        self.fast: bool = fast
        self.Engine: Engine | None = None
        self.__create_engine()

    # Connection & Execution Handling
    def __create_engine(self) -> None:
        if self.parent_connector.config.fast_executemany_support and self.fast:
            self.engine = create_engine(
                url=self.parent_connector.connection_string, fast_executemany=True
            )
        else:
            self.engine = create_engine(url=self.parent_connector.connection_string)

    def __connect(self) -> None:
        self.connection = self.engine.connect()
        self.connection.begin()
        self.connected = True

    def __close_cursor(self) -> None:
        if self.cursor:
            try:
                self.cursor.close()
            except Exception:
                self.cursor = None

    def __close_connection(self) -> None:
        self.__close_cursor()

        if self.connection:
            try:
                self.connection.close()
            except Exception:
                self.connection = None
                self.connected = False

    def __close_connection_in_error(self) -> None:
        try:
            self.__close_connection()
        except Exception:
            # Error closing connection, try to force
            try:
                self.__connect()
                self.__close_connection()
                self.connected = False
            except Exception:
                self.connection = None
                self.connected = False

    def __execute(self, query: str, commit: bool = False, close: bool = False) -> None:
        """Execute SQL query using connection.

        Args:
            -   query (str): SQL Query
            -   commit (bool): If True, connection commits after executing. Defaults to False.
            -   close (bool): If True, closes the connection after executing. Defaults to False.
        """
        # Set Parameters
        if not self.connected:
            self.__connect()

        try:
            self.cursor = self.connection.execute(text(query))
        except Exception as e:
            self.connection.rollback()
            self.__close_connection_in_error()
            raise QueryExecutionError(str(e)) from e

        if commit:
            self.connection.commit()

        if close:
            self.__close_connection()

        return None

    def __get_dtypes(self) -> dict[str, FLOAT[Any] | VARCHAR]:
        if is_dict_like(kwargs_dtype := self.kwargs.get("dtype", {})):
            # using or operator to allow to_sql dtype param (refer to PEP 584 for syntax).
            # kwarg.dtype's data types are prioritised over _convert_dtypes's data types
            dtype_remap = (
                _convert_dtypes(self.df, varchar_length=self.set_varchar_length)
                | kwargs_dtype
            )
        else:
            dtype_remap = self.kwargs.get("dtype")
        self.kwargs.pop("dtype", None)
        return dtype_remap  # type: ignore[no-any-return]

    def __enforce_upload_argument_types(self) -> None:
        _enforce_type(self.table, "table", str)
        if self.schema:
            _enforce_type(self.schema, "schema", str)

        if self.if_table_exists:
            _enforce_in_list(self.if_table_exists, TABLE_EXISTS_OPTIONS)
        if self.header_case:
            _enforce_in_list(self.header_case, HEADER_CASE_OPTIONS)
        if self.max_header_length:
            _enforce_type(self.max_header_length, "max_header_length", int)
        if self.set_varchar_length:
            _enforce_type(self.set_varchar_length, "set_varchar_length", int)
        if self.chunksize:
            _enforce_type(self.chunksize, "chunksize", int)
        if self.index:
            _enforce_type(self.index, "index", bool)
        if self.progress_header:
            _enforce_type(self.progress_header, "progress_header", str)

    def __prepare_dataframe_for_upload(self, df: DataFrame) -> DataFrame:
        _enforce_type(df, "df", DataFrame)
        if df.shape[0] == 0:
            raise UnstructuredDataFrameError()

        # table = self.table
        max_header_length = self.max_header_length
        header_case = self.header_case

        if max_header_length:
            self.table = self.table[:max_header_length]

        df = _truncate_cols(df, max_header_length)

        if len(df.columns) != len(set(df.columns)):
            raise ValueError(
                "Duplicate column names - potentially after column name length truncation. Check dataframe and max_header_length, if set."
            )

        df = (
            _convert_headers(df, convert_header_case=header_case) if header_case else df
        )

        df = _force_dtypes_string(df)
        return df

    def __check_if_table_exists_command(self, error: Exception) -> None:
        if not self.if_table_exists:
            self.__raise_if_table_exists_match_error(error=error)

        elif self.if_table_exists not in TABLE_EXISTS_OPTIONS:
            self.__raise_if_table_exists_match_error(error=error)

    def __raise_if_table_exists_match_error(self, error: Exception) -> None:
        self.__close_connection()
        raise UploadConflictError(
            "Table already exists. To set conflict behaviour, "
            + f"pass 'if_table_exists' as: {TABLE_EXISTS_OPTIONS}"
        ) from error

    def __upload_dataframe(
        self, df: DataFrame, if_exists: Literal["fail", "replace", "append"]
    ) -> None:
        df.to_sql(
            name=self.table,
            con=self.connection,  # type: ignore[arg-type]
            schema=self.schema,
            chunksize=self.chunksize,
            dtype=self.dtype_remap,  # type: ignore[arg-type]
            index=self.index,
            if_exists=if_exists,
            **self.kwargs,
        )

    def __upload_with_append(self, df: DataFrame) -> None:
        # Upload with append
        self.__upload_dataframe(df=df, if_exists="append")

    def __upload_with_replace(self, df: DataFrame) -> None:
        # Delete from table
        self.__execute(
            f"DELETE FROM {self.schema_m}{self.table}",
            close=False,
            commit=False,
        )
        try:
            # Upload with append
            self.__upload_dataframe(df=df, if_exists="append")

        except InvalidRequestError:
            # Attempt find with lowercase
            original_table = self.table
            self.table = self.table.lower()

            # Upload with append
            self.__upload_dataframe(df=df, if_exists="append")
            self.table = original_table

    def __upload_with_drop(self, df: DataFrame) -> None:
        # Drop table
        self.__execute(
            f"DROP TABLE {self.schema_m}{self.table}",
            close=False,
            commit=False,
        )

        # Upload with append
        self.__upload_dataframe(df=df, if_exists="append")

    def __upload_with_conflict(self, df: DataFrame) -> None:
        if self.if_table_exists == "append":
            self.__upload_with_append(df=df)

        elif self.if_table_exists == "replace":
            self.__upload_with_replace(df=df)

        elif self.if_table_exists == "drop":
            self.__upload_with_drop(df=df)

        else:
            self.__raise_if_table_exists_match_error(ValueError("Invalid option"))

    def upload(self) -> None:
        with Progress(
            header=self.progress_header, active=self.feedback, complete_text="Completed"
        ) as progress:
            progress.start_auto_update()

            # Prepare
            if not self.connected:
                self.__connect()

            # Attempt Upload
            progress.update(show=True)
            try:
                self.__upload_dataframe(df=self.df, if_exists="fail")
                self.connection.commit()
                self.__close_connection()
                progress.finish()

            # Handle Conflict
            except Exception as error:
                # TODO: Consider better error handling
                if (
                    isinstance(error, ValueError)
                    and error.__str__() == f"Table '{self.table}' already exists."
                ):
                    self.__check_if_table_exists_command(error=error)
                    try:
                        # If table exists
                        suffix = f"with '{self.if_table_exists}'"
                        progress.update_header(suffix=suffix)
                        self.__upload_with_conflict(df=self.df)
                        progress.update_header(suffix=" " * len(suffix))
                        progress.complete_text = (
                            f"Completed with '{self.if_table_exists}'"
                        )
                        self.connection.commit()
                        self.__close_connection()
                        progress.finish()

                    # Fail on second attempt
                    except Exception as second_error:
                        # Roll Back & Close
                        self.connection.rollback()
                        self.__close_connection()

                        # Identify Error
                        if (
                            self.fast
                            and self.parent_connector.config.fast_executemany_support
                        ):
                            if (
                                isinstance(second_error, ProgrammingError)
                                and "String data, right truncation"
                                in second_error.__str__()
                            ):
                                raise UploadError(
                                    "Upload string buffer error. Check maximum string lengths in DataFrame vs database columns, including trailing whitespace."
                                ) from second_error

                        # Default: Raise for all other cases
                        raise UploadError(second_error.__str__()) from second_error

                else:
                    # Other errors
                    self.__close_connection()
                    raise UploadError(error.__str__()) from error
