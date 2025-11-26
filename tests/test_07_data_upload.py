from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from pandas import DataFrame, Series
from sqlalchemy.types import FLOAT, NVARCHAR, VARCHAR
from support.config import config

from kraken.connection.connector import Connector, create_connector
from kraken.credentials.credentials import Credentials
from kraken.exceptions import (
    QueryExecutionError,
    UnstructuredDataFrameError,
    UploadConflictError,
    UploadError,
    VarcharLengthError,
)
from kraken.uploading.support import (
    _convert_dtypes,
    _convert_headers,
    _force_dtypes_string,
    _truncate_cols,
)

### Constants ###
TEST_UPLOAD_TABLE = "KRAKEN_TEST_UPLOAD"
TEST_DTYPE_TABLE = "DTYPE_TEST"

main_test = config.main_test
MAIN_TEST_ALIAS = main_test.alias
MAIN_TEST_USERNAME = main_test.username
MAIN_TEST_DATABASE = main_test.database
MAIN_TEST_SCHEMA = main_test.schema


### Helpers ###
def get_mixed_type_dataframe() -> DataFrame:
    # Create a sample DataFrame for testing
    df = DataFrame(
        {
            "int_column": [1, 2, 3],
            "float_column": [4.0, 5.0, 6.0],
            "str_column": ["a", "b", "c"],
            "mixed_column": [1, 2.0, "three"],
        }
    )
    return df


def get_complex_dataframe() -> DataFrame:
    df = DataFrame(
        {
            "a": Series([1, 2, 3], dtype=np.dtype("int32")),
            "b": Series(["x", "y", "z"], dtype=np.dtype("O")),
            "c": Series([True, False, np.nan], dtype=np.dtype("object")),
            "d": Series(["h", "i", np.nan], dtype=np.dtype("O")),
            "e": Series([10, np.nan, 20], dtype=np.dtype("float")),
            "f": Series([np.nan, 100.5, 200], dtype=np.dtype("float")),
            "g": Series([np.nan, "071892", "171892"], dtype=np.dtype("float")),
            "h": Series([True, False, np.nan], dtype=np.dtype("bool")),
            "i": Series([True, False, "wor"], dtype=np.dtype("object")),
            "j": Series([np.nan, np.nan, "A Long String"], dtype=np.dtype("object")),
        }
    )
    return df


def check_columns_query() -> str:
    return f"""
    SELECT  COLUMN_NAME                 AS column_name
        ,   DATA_TYPE                   AS data_type
        ,   CHARACTER_MAXIMUM_LENGTH    AS data_length
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = '{MAIN_TEST_SCHEMA}' AND TABLE_NAME = '{TEST_DTYPE_TABLE}';
    """


def get_local_connector() -> Connector:
    credentials = Credentials(
        alias="local",
        username="local",
        password=None,
        platform="duckdb",
        connection_string="duckdb:///:memory:",
    )
    connector = create_connector(alias="local", custom_credentials=credentials)
    return connector


def get_test_connector(autocommit: bool = True, autoclose: bool = True) -> Connector:
    connector = main_test.get_connector(
        autocommit=autocommit,
        autoclose=autoclose,
    )
    if connector.config.multiple_db_support:
        connector.switch_database(MAIN_TEST_DATABASE)

    if main_test.fallback:
        connector.execute(f"CREATE SCHEMA IF NOT EXISTS {MAIN_TEST_SCHEMA}")

    return connector


def drop_if_exists(connector: Connector, table: str) -> None:
    """Attempts to drop a table in the given connector, ignoring any errors
    that may arise if the table does not exist."""
    try:
        connector.execute(
            f"DROP TABLE {table}", progress=False, commit=True, close=True
        )
    except QueryExecutionError:
        pass


## Fixtures ###
@pytest.fixture
def mixed_type_dataframe() -> DataFrame:
    return get_mixed_type_dataframe()


@pytest.fixture
def dataframe_for_upload_dtype_test() -> DataFrame:
    return DataFrame(
        {
            "integer_data": [0, 1],
            "float_data": [1.1, 2.1],
            "string_data": [
                "a_b_c",
                "long_string",  # len('long_string') = 11; expecting varchar(11) in the SQL Server
            ],
        }
    )


### ====================== ###
### ---------TESTS---------###
### ====================== ###


### Test that columns are truncated
def test_truncate_cols() -> None:
    sample_dataframe = pd.DataFrame(
        {
            "very_long_column_name_that_needs_truncation": [1, 2, 3],
            "short_column_name": [4, 5, 6],
        }
    )
    # default max_header_length
    truncated_df = _truncate_cols(sample_dataframe)
    assert len(truncated_df.columns[0]) == len(
        "very_long_column_name_that_needs_truncation"
    )

    # custom max_header_length
    custom_length = 10
    truncated_df = _truncate_cols(sample_dataframe, max_header_length=custom_length)
    assert len(truncated_df.columns[0]) == custom_length

    # max_header_length is longer than longest column name
    max_length = max([len(col) for col in sample_dataframe.columns])
    custom_length = max_length + 1
    truncated_df = _truncate_cols(sample_dataframe, max_header_length=custom_length)
    assert (truncated_df.columns == sample_dataframe.columns).all()

    # empty DataFrame
    empty_df = pd.DataFrame()
    truncated_df = _truncate_cols(empty_df)
    assert len(truncated_df.columns) == 0


### Test that _force_dtypes_string handles mixed nulls in a df correctly
def test_force_dtypes_string_mixed_nulls(mixed_type_dataframe: pd.DataFrame) -> None:
    mixed_type_dataframe["str_column"] = [np.nan, "b", None]
    assert _force_dtypes_string(mixed_type_dataframe)["str_column"].iloc[0] is np.nan
    assert _force_dtypes_string(mixed_type_dataframe)["str_column"].iloc[2] is np.nan


### Test that _force_dtypes_string does not fail with an empty DataFrame
def test_force_dtypes_string_empty_dataframe() -> None:
    empty_df = pd.DataFrame()
    df = _force_dtypes_string(empty_df)
    assert len(df.columns) == 0


### Test that the _convert_dtypes returns the correct mapping without specifying varchar_length
def test_convert_dtypes_without_varchar_length(
    mixed_type_dataframe: pd.DataFrame,
) -> None:
    mapping = _convert_dtypes(mixed_type_dataframe)
    print(mapping)
    assert "float_column" in mapping
    assert "str_column" in mapping
    assert mapping["float_column"] == FLOAT
    assert str(mapping["str_column"]) == str(VARCHAR(1))
    assert str(mapping["mixed_column"]) == str(VARCHAR(5))


### Test that the _convert_dtypes returns the correct mapping when specifying varchar_length
def test_convert_dtypes_with_custom_varchar_length(
    mixed_type_dataframe: pd.DataFrame,
) -> None:
    mapping = _convert_dtypes(df=mixed_type_dataframe, varchar_length=10)
    assert "float_column" in mapping
    assert "str_column" in mapping
    assert mapping["float_column"] == FLOAT
    # https://stackoverflow.com/a/41579742
    assert str(mapping["str_column"]) == str(VARCHAR(10))
    assert str(mapping["mixed_column"]) == str(VARCHAR(10))


### Test that headers can be converted to uppercase
def test_convert_headers_upper(mixed_type_dataframe: pd.DataFrame) -> None:
    expected_columns = ["INT_COLUMN", "FLOAT_COLUMN", "STR_COLUMN", "MIXED_COLUMN"]
    actual_df = _convert_headers(mixed_type_dataframe, convert_header_case="upper")
    assert actual_df.columns.tolist() == expected_columns


### Test that headers can be converted to lowercase
def test_convert_headers_lower(mixed_type_dataframe: pd.DataFrame) -> None:
    expected_columns = ["int_column", "float_column", "str_column", "mixed_column"]
    actual_df = _convert_headers(mixed_type_dataframe, convert_header_case="lower")
    assert actual_df.columns.tolist() == expected_columns


### Test header case can remain unchanged
def test_convert_headers_none(mixed_type_dataframe: pd.DataFrame) -> None:
    original_columns = mixed_type_dataframe.columns.tolist()
    actual_df = _convert_headers(mixed_type_dataframe, convert_header_case=None)
    assert actual_df.columns.tolist() == original_columns


### Test that dtype conversion works on complex dataframe
def test_dtype_conversion_complex() -> None:
    df = get_complex_dataframe()
    dtype_remap = _convert_dtypes(df)
    assert dtype_remap


### Test that dtype conversion works on complex dataframe when length set
def test_dtype_conversion_complex_with_set_length() -> None:
    df = get_complex_dataframe()
    dtype_remap = _convert_dtypes(df, varchar_length=64)
    assert dtype_remap


### Test that dtype conversion raises VarcharLengthError
def test_failure_dtype_conversion_complex_with_set_length() -> None:
    df = get_complex_dataframe()
    with pytest.raises(VarcharLengthError):
        _convert_dtypes(df, varchar_length=1)


### Test that an empty DataFrame can be locally uploaded
def test_upload_dataframe_unstructured_df() -> None:
    unstructured_df = pd.DataFrame()
    table = "unstructured_df"

    connector = get_local_connector()
    drop_if_exists(connector, table)

    with pytest.raises(UnstructuredDataFrameError):
        connector.upload(df=unstructured_df, table=table, schema=MAIN_TEST_SCHEMA)


### Test that a DataFrame can be uploaded
def test_upload_dataframe_real() -> None:
    df = get_mixed_type_dataframe()
    connector = get_test_connector()
    connector.set_autoclose(False)
    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    connector.upload(
        df=df,
        schema=MAIN_TEST_SCHEMA,
        table=TEST_UPLOAD_TABLE,
    )

    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    connector.close_connection()


### Test that a DataFrame upload fails when exists
def test_failure_upload() -> None:
    df = get_mixed_type_dataframe()

    connector = get_test_connector()
    checker = get_test_connector()
    connector.set_autoclose(False)

    # Ensure no table
    drop_if_exists(checker, f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")

    # Upload once
    connector.upload(
        df=df,
        schema=MAIN_TEST_SCHEMA,
        table=TEST_UPLOAD_TABLE,
    )

    # Check the table exists
    checker.execute(
        f"SELECT * FROM {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}"
        + (" WITH (NOLOCK)" if connector.platform == "mssql" else "")
    )

    # Reupload and fail with lack of input OSError
    with pytest.raises(UploadConflictError):
        connector.upload(
            df=df,
            schema=MAIN_TEST_SCHEMA,
            table=TEST_UPLOAD_TABLE,
        )

    # Reupload and fail with error input
    with pytest.raises(ValueError):
        connector.upload(
            df=df,
            schema=MAIN_TEST_SCHEMA,
            table=TEST_UPLOAD_TABLE,
            if_table_exists="SILLY",  # type: ignore
        )

    # Clean Up
    drop_if_exists(checker, f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    connector.close_connection()


### Test that a DataFrame can be reuploaded when exists
@pytest.mark.parametrize("if_table_exists", ["REPLACE", "DROP", "APPEND"])
def test_upload_table_exists(if_table_exists: str) -> None:
    with patch("builtins.input", side_effect=if_table_exists):
        df = get_mixed_type_dataframe()

        connector = get_test_connector()
        connector.set_autoclose(False)
        # Create the table
        drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
        connector.upload(
            df=df,
            schema=MAIN_TEST_SCHEMA,
            table=TEST_UPLOAD_TABLE,
        )

        # Attempt Reupload with if_table_exists
        connector.upload(
            df=df,
            schema=MAIN_TEST_SCHEMA,
            table=TEST_UPLOAD_TABLE,
            if_table_exists=if_table_exists,  # type: ignore
        )

        # Clean Up
        drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
        connector.close_connection()


### Test DataFrame upload data types
def test_upload_dataframe_no_dtype_specified(
    dataframe_for_upload_dtype_test: DataFrame,
) -> None:
    connector = get_test_connector()
    connector.set_autoclose(False)
    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_DTYPE_TABLE}")

    connector.upload(
        df=dataframe_for_upload_dtype_test,
        table=TEST_DTYPE_TABLE,
        schema=MAIN_TEST_SCHEMA,
        if_table_exists="drop",
    )
    column_data = connector.execute(check_columns_query(), progress=False)
    assert isinstance(column_data, DataFrame)
    assert {dt.lower() for dt in column_data["data_type"]} == {
        "bigint",
        "float",
        "varchar",
    }

    varchar_rows = column_data[column_data["data_type"].str.lower() == "varchar"]
    assert not varchar_rows.empty, "Expected at least one VARCHAR column"

    length = varchar_rows["data_length"].iloc[0]

    if connector.platform == "duckdb":  # DuckDB does not report fixed VARCHAR length
        assert length is None or pd.isna(length)
    else:
        assert length == 11

    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_DTYPE_TABLE}")
    connector.close_connection()

    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_DTYPE_TABLE}")
    connector.close_connection()


### Test DataFrame upload can overwrite all data types
def test_upload_dataframe_scalar_dtype(
    dataframe_for_upload_dtype_test: DataFrame,
) -> None:
    connector = get_test_connector()
    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_DTYPE_TABLE}")

    connector.upload(
        df=dataframe_for_upload_dtype_test,
        table=TEST_DTYPE_TABLE,
        schema=MAIN_TEST_SCHEMA,
        dtype=NVARCHAR,  # override all columns
        if_table_exists="drop",
    )

    column_data = connector.execute(check_columns_query(), progress=False)
    column_data = connector.execute(check_columns_query(), progress=False)
    assert isinstance(column_data, DataFrame)

    types = {dt.lower() for dt in column_data["data_type"]}
    assert len(types) == 1

    if connector.platform == "mssql":
        assert types == {"nvarchar"}
    else:
        assert types.issubset({"nvarchar", "varchar", "text"})

    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_DTYPE_TABLE}")
    connector.close_connection()


### Test DataFrame upload can overwrite a single datatype
def test_upload_dataframe_override_single_dtype(
    dataframe_for_upload_dtype_test: DataFrame,
) -> None:
    connector = get_test_connector()
    connector.set_autoclose(False)
    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_DTYPE_TABLE}")

    connector.upload(
        df=dataframe_for_upload_dtype_test,
        table=TEST_DTYPE_TABLE,
        schema=MAIN_TEST_SCHEMA,
        dtype={"integer_data": NVARCHAR},  # override integer with NVARCHAR
        if_table_exists="drop",
    )

    column_data = connector.execute(check_columns_query(), progress=False)
    assert isinstance(column_data, DataFrame)
    types_by_col = {
        row["column_name"]: str(row["data_type"]).lower()
        for _, row in column_data.iterrows()
    }

    # float_data stays numeric
    assert types_by_col["float_data"] in {"float"}

    # string_data is text
    assert types_by_col["string_data"] in {"varchar", "nvarchar", "text"}

    # integer_data was overridden to text on all supported backends
    assert types_by_col["integer_data"] in {"varchar", "nvarchar", "text"}

    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_DTYPE_TABLE}")
    connector.close_connection()


### Test DataFrame upload can overwrite a single datatype and force length
def test_upload_dataframe_dtype_and_varchar_length(
    dataframe_for_upload_dtype_test: DataFrame,
) -> None:
    connector = get_test_connector()
    connector.set_autoclose(False)
    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_DTYPE_TABLE}")

    connector.upload(
        df=dataframe_for_upload_dtype_test,
        table=TEST_DTYPE_TABLE,
        schema=MAIN_TEST_SCHEMA,
        set_varchar_length=15,  # override string_data column's length
        dtype={"integer_data": NVARCHAR},  # override integer with NVARCHAR
        if_table_exists="drop",
    )

    column_data = connector.execute(check_columns_query(), progress=False)
    assert isinstance(column_data, DataFrame)

    types_by_col = {  # -> lowercase
        row["column_name"]: str(row["data_type"]).lower()
        for _, row in column_data.iterrows()
    }

    # float_data stays numeric
    assert types_by_col["float_data"] in {"float"}

    # string_data should be some kind of text
    assert types_by_col["string_data"] in {"varchar", "nvarchar", "text"}

    # integer_data overridden to text on all supported backends
    assert types_by_col["integer_data"] in {"varchar", "nvarchar", "text"}

    # check the varchar length
    string_row = column_data[column_data["column_name"] == "string_data"].iloc[0]
    varchar_length = string_row["data_length"]

    if connector.platform == "duckdb":
        assert varchar_length is None
    else:
        assert int(varchar_length) == 15

    drop_if_exists(connector, f"{MAIN_TEST_SCHEMA}.{TEST_DTYPE_TABLE}")
    connector.close_connection()


### Test that a complex DataFrame can be uploaded
def test_complex_upload() -> None:
    # Prepare
    df = get_complex_dataframe()
    connector = get_test_connector()
    connector.set_autoclose(False)
    drop_if_exists(connector, table=f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")

    # Upload Table
    connector.upload(df=df, table=TEST_UPLOAD_TABLE, schema=MAIN_TEST_SCHEMA)

    # Clean Up
    drop_if_exists(connector, table=f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    connector.close_connection()


## Test that complex commit upload behaviour works
@pytest.mark.skipif(
    main_test.fallback,
    reason="DuckDB fallback test backend doesn't support multi-statement rollback",
)
def test_complex_rollback() -> None:
    # Prepare
    df = get_complex_dataframe()
    dropper = get_test_connector(autocommit=True, autoclose=False)
    checker = get_test_connector(autocommit=True, autoclose=False)
    uploader = get_test_connector(autocommit=False, autoclose=False)
    drop_if_exists(dropper, table=f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    dropper.close_connection()

    # Upload
    uploader.upload(df=df, table=TEST_UPLOAD_TABLE, schema=MAIN_TEST_SCHEMA)

    # Check table exists
    checker.execute(
        f"SELECT * FROM {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}", close=False
    )

    # Drop but do not commit
    uploader.execute(
        f"DROP TABLE IF EXISTS {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}",
        commit=False,
        close=False,
    )
    uploader.rollback()

    # Check table still exists
    checker.execute(f"SELECT * FROM {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")

    # Clean Up
    drop_if_exists(dropper, table=f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    for connector in [dropper, checker, uploader]:
        connector.close_connection()


@pytest.mark.skipif(
    main_test.fallback,
    reason="DuckDB fallback test backend doesn't support multi-statement rollback",
)
def test_complex_close_without_commit() -> None:
    # Prepare
    df = get_complex_dataframe()
    dropper = get_test_connector(autocommit=True, autoclose=False)
    checker = get_test_connector(autocommit=True, autoclose=False)
    uploader = get_test_connector(autocommit=False, autoclose=False)
    drop_if_exists(dropper, table=f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")

    # Upload
    uploader.upload(df=df, table=TEST_UPLOAD_TABLE, schema=MAIN_TEST_SCHEMA)

    # Check table exists
    checker.execute(f"SELECT * FROM {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")

    # Drop but close before committing
    uploader.execute(f"DROP TABLE IF EXISTS {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    uploader.close_connection()

    # Check table still exists
    checker.execute(f"SELECT * FROM {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")

    # Clean Up
    drop_if_exists(dropper, table=f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    for connector in [dropper, checker, uploader]:
        connector.close_connection()


@pytest.mark.skipif(
    main_test.fallback,
    reason=(
        "DuckDB fallback test backend doesn't support multi-statement rollback "
        + "so will always pass"
    ),
)
def test_complex_commit() -> None:
    df = get_complex_dataframe()
    dropper = get_test_connector(autocommit=True, autoclose=False)
    checker = get_test_connector(autocommit=True, autoclose=False)
    uploader = get_test_connector(autocommit=False, autoclose=False)
    drop_if_exists(dropper, table=f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")

    # Upload and commit
    uploader.upload(df=df, table=TEST_UPLOAD_TABLE, schema=MAIN_TEST_SCHEMA)
    uploader.commit()

    # Check table does exist
    check = checker.execute(f"SELECT * FROM {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    assert isinstance(check, pd.DataFrame)

    # Clean Up
    drop_if_exists(dropper, table=f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    for connector in [dropper, checker, uploader]:
        connector.close_connection()


def test_correct_null_uploading() -> None:
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "name": ["Alice", None, "Charlie", "David"],
            "age": [25, 35, np.nan, 40],
            "active": [True, False, True, None],
            "notes": ["OK", "Name is None", "Age is np.nan", "is_active is bool None"],
        }
    )
    uploader = get_test_connector()
    checker = get_test_connector()
    dropper = get_test_connector()
    drop_if_exists(dropper, table=f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")

    uploader.upload(
        df,
        table=TEST_UPLOAD_TABLE,
        schema=MAIN_TEST_SCHEMA,
    )
    check = checker.execute(f"""
            SELECT COUNT(*) AS count
            FROM {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}
            WHERE  name     IS NULL
                OR age      IS NULL
                OR active   IS NULL""")
    assert check["count"].iloc[0] == 3  # type: ignore

    # Clean Up
    drop_if_exists(dropper, table=f"{MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}")
    for connector in [dropper, checker, uploader]:
        connector.close_connection()


def test_failures_raised_correctly() -> None:
    # Prepare DFs
    df_valid = pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})

    df_fail = pd.DataFrame(
        {
            "id": [1, 1, 2],  # duplicate id
            "name": ["Alice", "Ann", "Bob"],
        }
    )

    drop_sql = f"DROP TABLE IF EXISTS {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE}"
    create_sql = f"""
        CREATE TABLE {MAIN_TEST_SCHEMA}.{TEST_UPLOAD_TABLE} (
                id      INT             PRIMARY KEY
            ,   name    NVARCHAR(100)   NOT NULL)"""

    # Prepare Table
    connector = get_test_connector()
    connector.execute(drop_sql)
    connector.execute(create_sql)

    # Test Upload & Error Handling
    table = TEST_UPLOAD_TABLE
    schema = MAIN_TEST_SCHEMA
    if_table_exists = "replace"

    connector.upload(
        df_valid, table=table, schema=schema, if_table_exists=if_table_exists
    )

    with pytest.raises(UploadError) as error:
        connector.upload(
            df_fail, table=table, schema=schema, if_table_exists=if_table_exists
        )

    error_message = str(error.value).lower()
    assert "duplicate" in error_message or "primary key" in error_message

    connector.execute(drop_sql)


if __name__ == "__main__":
    pytest.main([__file__])
