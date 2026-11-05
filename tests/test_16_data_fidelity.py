from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from openpyxl import load_workbook

from kraken import export_results, extract_spreadsheets
from kraken.analysis.data_manipulation import date_converter_df, examine
from kraken.classes.pack_lists import ResultList
from kraken.classes.packs import Result
from kraken.connection.connector import CursorLike, SaConnector
from kraken.connection.dtype_mapping import (
    analyse_column,
    resolve_column_kind,
    resolve_column_kinds,
)
from kraken.support.progress import Progress


def fetch_fidelity_rows(
    rows: list[tuple],
    columns: list[str],
    clean_df: bool = True,
    batch_size: int = 0,
    description: list[tuple] | None = None,
) -> pd.DataFrame:
    connector = object.__new__(SaConnector)
    connector.cursor = Mock(spec=CursorLike)
    connector.cursor.description = description or [
        (column, None, None, None, None, None, None) for column in columns
    ]
    connector.cursor.fetchall.side_effect = [rows, []]
    connector.cursor.fetchmany.side_effect = [rows, []]
    connector.batch_size = batch_size
    connector.multiset_supported = False
    return connector._fetch_data(
        query_name="fidelity",
        progress=Mock(spec=Progress),
        clean_df=clean_df,
        check_column_duplicates=False,
    )[0]


@pytest.mark.parametrize(
    "value, expected_dtype",
    [
        (2**53 + 1, "Int64"),
        (2**63 - 1, "Int64"),
        (2**63, "UInt64"),
        (-(2**63), "Int64"),
        (2**64, "object"),
        (-(2**63) - 1, "object"),
        (1.5, "float64"),
        (True, "boolean"),
        (Decimal("1234567890.123456789"), "object"),
        (date(2026, 1, 1), "object"),
        (datetime(2026, 1, 1), None),
    ],
    ids=[
        "large-integer",
        "signed-limit",
        "unsigned",
        "signed-minimum",
        "huge-positive",
        "huge-negative",
        "float",
        "boolean",
        "decimal",
        "date",
        "datetime",
    ],
)
def test_sql_fidelity_preserves_nullable_scalar_types(
    value: object, expected_dtype: str | None
) -> None:
    restored = fetch_fidelity_rows([(value,), (None,)], ["value"])

    if expected_dtype is None:
        assert pd.api.types.is_datetime64_any_dtype(restored["value"])
    else:
        assert str(restored["value"].dtype) == expected_dtype
    if expected_dtype in ("Int64", "UInt64"):
        assert int(restored["value"].iloc[0]) == value
    else:
        assert restored["value"].iloc[0] == value
    assert pd.isna(restored["value"].iloc[1])


def test_sql_fidelity_preserves_duplicate_columns_and_batches() -> None:
    restored = fetch_fidelity_rows(
        [(2**53 + 1, 1.5), (None, None)], ["value", "value"], batch_size=2
    )

    assert restored.columns.tolist() == ["value", "value"]
    assert int(restored.iloc[0, 0]) == 2**53 + 1
    assert str(restored.iloc[:, 0].dtype) == "Int64"
    assert str(restored.iloc[:, 1].dtype) == "float64"


def test_sql_fidelity_preserves_cleaning_opt_out() -> None:
    restored = fetch_fidelity_rows([(1,), (None,)], ["value"], clean_df=False)

    assert str(restored["value"].dtype) == "float64"


def test_sql_fidelity_keeps_mixed_numeric_scalars_exact() -> None:
    restored = fetch_fidelity_rows([(2**53 + 1,), (1.5,), (None,)], ["value"])

    assert restored["value"].dtype == object
    assert restored["value"].tolist() == [2**53 + 1, 1.5, None]
    assert isinstance(restored["value"].iloc[0], int)


@pytest.mark.parametrize(
    "value, dtype", [(1, "Int64"), (1.5, "float64"), (True, "boolean")]
)
def test_sql_fidelity_dtypes_do_not_depend_on_nulls(value: object, dtype: str) -> None:
    restored = fetch_fidelity_rows([(value,), (value,)], ["value"])

    assert str(restored["value"].dtype) == dtype


@pytest.mark.parametrize("rows", [[], [(None,), (None,)]], ids=["empty", "all-null"])
def test_sql_fidelity_keeps_untyped_results(rows: list[tuple]) -> None:
    restored = fetch_fidelity_rows(rows, ["value"])

    assert restored.columns.tolist() == ["value"]
    assert restored.shape == (len(rows), 1)
    assert restored["value"].isna().all()


def sql_description(
    type_code: object, precision: int | None = None, scale: int | None = None
) -> list[tuple]:
    return [("value", type_code, None, None, precision, scale, None)]


@pytest.mark.parametrize("type_code", [datetime, int, None])
@pytest.mark.parametrize("wide", [False, True])
def test_sql_fidelity_preserves_nanoseconds_and_datetime_range(
    type_code: object, wide: bool
) -> None:
    precise = pd.Timestamp("2026-01-01 00:00:00.123456789")
    values = [datetime(9999, 1, 1) if wide else precise, precise, None]

    restored = fetch_fidelity_rows(
        [(value,) for value in values],
        ["value"],
        description=sql_description(type_code),
    )["value"]

    assert restored.isna().tolist() == [False, False, True]
    assert restored.iloc[0] == values[0]
    assert restored.iloc[1] == precise
    assert restored.iloc[1].nanosecond == 789
    if wide:
        assert restored.dtype == object


@pytest.mark.parametrize("type_code", [float, int, None])
@pytest.mark.parametrize("scalar", [int, np.int64, np.uint64])
def test_sql_fidelity_preserves_numpy_integers_in_mixed_numeric_columns(
    type_code: object, scalar: type
) -> None:
    original = scalar(2**53 + 1)
    restored = fetch_fidelity_rows(
        [(original,), (1.5,), (None,)],
        ["value"],
        description=sql_description(type_code),
    )["value"]

    assert restored.dtype == object
    assert int(restored.iloc[0]) == 2**53 + 1
    assert isinstance(restored.iloc[0], (int, np.integer))
    assert restored.iloc[1] == 1.5
    assert restored.isna().tolist() == [False, False, True]


@pytest.mark.parametrize("type_code", [float, int, None])
def test_sql_fidelity_preserves_negative_zero(type_code: object) -> None:
    restored = fetch_fidelity_rows(
        [(-0.0,), (1.0,), (None,)],
        ["value"],
        description=sql_description(type_code),
    )["value"]

    assert isinstance(restored.iloc[0], (float, np.floating))
    assert np.signbit(restored.iloc[0])
    assert restored.iloc[1] == 1.0
    assert restored.isna().tolist() == [False, False, True]


@pytest.mark.skipif(
    np.finfo(np.longdouble).nmant <= np.finfo(np.float64).nmant,
    reason="longdouble has no additional precision on this platform",
)
@pytest.mark.parametrize("type_code", [float, int, None])
def test_sql_fidelity_preserves_extended_precision_floats(type_code: object) -> None:
    original = np.longdouble(1) + np.finfo(np.longdouble).eps
    restored = fetch_fidelity_rows(
        [(original,), (None,)],
        ["value"],
        description=sql_description(type_code),
    )["value"]

    assert np.longdouble(restored.iloc[0]) == original
    assert restored.isna().tolist() == [False, True]


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("type_code", [datetime, None])
def test_sql_fidelity_preserves_numpy_datetime_resolutions(
    unit: str, type_code: object
) -> None:
    original = np.datetime64("2026-01-01T12:34:56.123456789", unit)
    restored = fetch_fidelity_rows(
        [(original,), (None,)],
        ["value"],
        description=sql_description(type_code),
    )["value"]

    assert pd.Timestamp(restored.iloc[0]) == pd.Timestamp(original)
    assert restored.isna().tolist() == [False, True]


@pytest.mark.parametrize("type_code", [datetime, None])
@pytest.mark.parametrize("mixed", [False, True])
def test_sql_fidelity_preserves_timezone_representation(
    type_code: object, mixed: bool
) -> None:
    first = pd.Timestamp("2026-11-01T01:30:00.123456789-04:00")
    second = first.tz_convert("UTC") if mixed else first
    restored = fetch_fidelity_rows(
        [(first,), (None,), (second,)],
        ["value"],
        description=sql_description(type_code),
    )["value"]

    assert restored.isna().tolist() == [False, True, False]
    for position, original in [(0, first), (2, second)]:
        assert restored.iloc[position] == original
        assert restored.iloc[position].nanosecond == 789
        assert restored.iloc[position].utcoffset() == original.utcoffset()
    if mixed:
        assert restored.dtype == object


@pytest.mark.parametrize("type_code", [int, float, bool, datetime, None])
def test_sql_fidelity_preserves_all_missing_positions(type_code: object) -> None:
    restored = fetch_fidelity_rows(
        [(None,), (pd.NA,), (np.nan,), (pd.NaT,)],
        ["value"],
        description=sql_description(type_code),
    )

    assert restored.shape == (4, 1)
    assert restored["value"].isna().tolist() == [True, True, True, True]
    expected_dtype = {
        int: "Int64",
        float: "float64",
        bool: "boolean",
        datetime: "datetime64[us]",
    }
    if type_code in expected_dtype:
        assert str(restored["value"].dtype) == expected_dtype[type_code]


def test_sql_fidelity_unsigned_metadata_falls_back_to_signed_values() -> None:
    restored = analyse_column(pd.Series([-1, None, 2], dtype=object), "uint")

    assert restored is not None
    assert str(restored.dtype) == "Int64"
    assert restored.dropna().tolist() == [-1, 2]
    assert restored.isna().tolist() == [False, True, False]


@pytest.mark.parametrize("scalar", [int, np.int64, np.uint64])
def test_sql_fidelity_integral_decimal_metadata_accepts_exact_mixed_scalars(
    scalar: type,
) -> None:
    restored = fetch_fidelity_rows(
        [(Decimal("12"),), (scalar(13),), (None,)],
        ["value"],
        description=sql_description(Decimal, 38, 0),
    )["value"]

    assert str(restored.dtype) == "Int64"
    assert restored.dropna().tolist() == [12, 13]
    assert restored.isna().tolist() == [False, False, True]


@pytest.mark.parametrize(
    "original", [np.int64(-(2**63)), np.int64(2**54), np.uint64(2**64 - 1)]
)
def test_sql_fidelity_float_metadata_preserves_numpy_integer_boundaries(
    original: np.integer,
) -> None:
    restored = fetch_fidelity_rows(
        [(original,), (None,)],
        ["value"],
        description=sql_description(float),
    )["value"]

    assert int(restored.iloc[0]) == int(original)
    assert restored.isna().tolist() == [False, True]


@pytest.mark.parametrize(
    "type_code, expected_dtype",
    [
        (int, "Int64"),
        (bool, "boolean"),
        (float, "float64"),
        (datetime, "datetime64[us]"),
    ],
    ids=["int", "bool", "float", "datetime"],
)
@pytest.mark.parametrize("rows", [[], [(None,), (None,)]], ids=["empty", "all-null"])
def test_sql_fidelity_types_empty_and_all_null_results_from_metadata(
    rows: list[tuple], type_code: object, expected_dtype: str
) -> None:
    restored = fetch_fidelity_rows(
        rows, ["value"], description=sql_description(type_code)
    )

    assert str(restored["value"].dtype) == expected_dtype
    assert restored["value"].isna().all()
    assert len(restored) == len(rows)


@pytest.mark.parametrize(
    "type_code, precision, scale, rows, expected",
    [
        (Decimal, 10, 0, [(Decimal("12"),), (None,)], [12, pd.NA]),
        (Decimal, 38, 0, [(Decimal("9223372036854775808"),)], [2**63]),
        (Decimal, 12, 2, [(Decimal("1.25"),)], [Decimal("1.25")]),
        (Decimal, None, None, [(Decimal("12"),)], [Decimal("12")]),
        (float, None, None, [(2**53 + 1,)], [2**53 + 1]),
    ],
    ids=["integral", "integral-unsigned", "fractional", "no-scale", "float-column"],
)
def test_sql_fidelity_converts_decimals_by_scale(
    type_code: object,
    precision: int | None,
    scale: int | None,
    rows: list,
    expected: list,
) -> None:
    restored = fetch_fidelity_rows(
        rows, ["value"], description=sql_description(type_code, precision, scale)
    )

    assert restored["value"].tolist() == expected
    if scale == 0:
        assert str(restored["value"].dtype) in ("Int64", "UInt64")
    elif scale:
        assert restored["value"].dtype == object


@pytest.mark.parametrize(
    "type_code, rows",
    [
        (int, [(1.5,), (None,)]),
        (int, [(2**64,)]),
        (int, [("1",)]),
        (bool, [(1,), (0,)]),
        (float, [("1.5",)]),
        (datetime, [(date(2026, 1, 1),)]),
        (datetime, [(datetime(2026, 1, 1, tzinfo=timezone.utc),)]),
        (Decimal, [(Decimal("1.5"),)]),
        (Decimal, [(1.0,), (float("inf"),)]),
    ],
    ids=[
        "int-with-floats",
        "int-too-large",
        "int-with-text",
        "bool-with-ints",
        "float-with-text",
        "datetime-with-dates",
        "datetime-with-timezone",
        "integral-with-fraction",
        "integral-with-infinity",
    ],
)
def test_sql_fidelity_falls_back_when_values_contradict_metadata(
    type_code: object, rows: list
) -> None:
    scale = 0 if type_code is Decimal else None
    precision = 10 if type_code is Decimal else None
    restored = fetch_fidelity_rows(
        rows, ["value"], description=sql_description(type_code, precision, scale)
    )
    source = [row[0] for row in rows]
    without_metadata = fetch_fidelity_rows(rows, ["value"])

    assert restored["value"].dtype == without_metadata["value"].dtype
    assert [None if pd.isna(v) else v for v in restored["value"].tolist()] == [
        None if pd.isna(v) else v for v in source
    ]


WHOLE_LIMIT = 2**53


@pytest.mark.parametrize("type_code", [int, None], ids=["int-metadata", "no-metadata"])
@pytest.mark.parametrize(
    "values",
    [
        [1.0, 2.0, None],
        [-3.0, 0.0, float("nan")],
        [float(WHOLE_LIMIT), -float(WHOLE_LIMIT)],
        [1, 2.0, None],
    ],
    ids=["whole", "negative-zero-nan", "at-limit", "mixed-int-whole-float"],
)
def test_sql_fidelity_converts_whole_number_floats_to_int(
    type_code: object, values: list
) -> None:
    rows = [(value,) for value in values]
    description = sql_description(type_code) if type_code else None

    restored = fetch_fidelity_rows(rows, ["value"], description=description)

    assert str(restored["value"].dtype) == "Int64"
    for original, converted in zip(values, restored["value"].tolist(), strict=True):
        if original is None or pd.isna(original):
            assert pd.isna(converted)
        else:
            assert converted == original
            assert isinstance(converted, int)


@pytest.mark.parametrize("type_code", [int, None], ids=["int-metadata", "no-metadata"])
@pytest.mark.parametrize(
    "values",
    [
        [1.0, 2.5],
        [1.0000000001],
        [float(WHOLE_LIMIT) * 2],
        [1.0, float("inf")],
        [1.0, float("-inf")],
    ],
    ids=["fraction", "tiny-fraction", "beyond-exact-range", "inf", "negative-inf"],
)
def test_sql_fidelity_keeps_floats_when_conversion_would_change_values(
    type_code: object, values: list
) -> None:
    rows = [(value,) for value in values]
    description = sql_description(type_code) if type_code else None

    restored = fetch_fidelity_rows(rows, ["value"], description=description)

    assert str(restored["value"].dtype) == "float64"
    assert restored["value"].tolist() == values


@pytest.mark.parametrize("type_code", [int, None], ids=["int-metadata", "no-metadata"])
def test_sql_fidelity_keeps_mixed_int_and_fractional_floats_as_objects(
    type_code: object,
) -> None:
    rows = [(2**53 + 1,), (2.0,), (0.5,)]
    description = sql_description(type_code) if type_code else None

    restored = fetch_fidelity_rows(rows, ["value"], description=description)

    assert restored["value"].dtype == object
    assert restored["value"].tolist() == [2**53 + 1, 2.0, 0.5]


@pytest.mark.parametrize(
    "rows, expected",
    [
        ([(2**53,), (1.5,)], [float(2**53), 1.5]),
        ([(2**53 + 1,), (1.5,)], None),
    ],
    ids=["exact-ints", "int-beyond-exact-range"],
)
def test_sql_fidelity_float_metadata_never_rounds_integers(
    rows: list, expected: list | None
) -> None:
    restored = fetch_fidelity_rows(rows, ["value"], description=sql_description(float))

    if expected is None:
        assert restored["value"].dtype == object
        assert restored["value"].tolist() == [row[0] for row in rows]
    else:
        assert str(restored["value"].dtype) == "float64"
        assert restored["value"].tolist() == expected


def test_sql_fidelity_float_metadata_keeps_whole_numbers_as_float() -> None:
    rows = [(1.0,), (2.0,), (None,)]

    restored = fetch_fidelity_rows(rows, ["value"], description=sql_description(float))

    assert str(restored["value"].dtype) == "float64"
    assert restored["value"].dropna().tolist() == [1.0, 2.0]


def test_sql_fidelity_float_metadata_keeps_large_integers_exact() -> None:
    restored = fetch_fidelity_rows(
        [(2**53 + 1,), (None,)], ["value"], description=sql_description(float)
    )

    assert str(restored["value"].dtype) == "Int64"
    assert int(restored["value"].iloc[0]) == 2**53 + 1


def test_sql_fidelity_signed_metadata_promotes_to_unsigned_when_values_require() -> (
    None
):
    restored = fetch_fidelity_rows(
        [(2**64 - 1,), (None,)], ["value"], description=sql_description(int)
    )

    assert str(restored["value"].dtype) == "UInt64"
    assert int(restored["value"].iloc[0]) == 2**64 - 1


def test_sql_fidelity_does_not_use_metadata_when_clean_df_disabled() -> None:
    restored = fetch_fidelity_rows(
        [(1,), (None,)], ["value"], clean_df=False, description=sql_description(int)
    )

    assert str(restored["value"].dtype) == "float64"


@pytest.mark.parametrize(
    "type_code, precision, scale, driver, expected",
    [
        (int, None, None, None, "int"),
        (bool, None, None, None, "bool"),
        (float, None, None, None, "float"),
        (datetime, None, None, None, "datetime"),
        (date, None, None, None, None),
        (str, None, None, None, None),
        (bytes, None, None, None, None),
        (Decimal, 18, 0, None, "integral_decimal"),
        (Decimal, 18, 2, None, None),
        (Decimal, 0, 0, None, None),
        (None, None, None, None, None),
        (21, None, None, "psycopg2", "int"),
        (23, None, None, "psycopg2", "int"),
        (20, None, None, "psycopg2", "int"),
        (16, None, None, "psycopg2", "bool"),
        (701, None, None, "psycopg2", "float"),
        (1114, None, None, "psycopg2", "datetime"),
        (1184, None, None, "psycopg2", None),
        (1700, 10, 0, "psycopg2", "integral_decimal"),
        (1700, None, None, "psycopg2", None),
        (8, None, None, "pymysql", "int"),
        (5, None, None, "pymysql", "float"),
        (12, None, None, "pymysql", "datetime"),
        (246, 10, 0, "pymysql", "integral_decimal"),
        (246, 10, 2, "pymysql", None),
        (8, None, None, "psycopg2", None),
        (8, None, None, None, None),
    ],
)
def test_resolve_column_kind(
    type_code: object,
    precision: int | None,
    scale: int | None,
    driver: str | None,
    expected: str | None,
) -> None:
    assert resolve_column_kind(type_code, precision, scale, driver) == expected


def test_resolve_column_kinds_tolerates_short_and_missing_descriptions() -> None:
    assert resolve_column_kinds(None, None) == []
    assert resolve_column_kinds([("a", int), ("b",)], None) == ["int", None]


def test_resolve_column_kind_oracle() -> None:
    oracledb = pytest.importorskip("oracledb")

    assert resolve_column_kind(oracledb.DB_TYPE_NUMBER, 10, 0) == "integral_decimal"
    assert resolve_column_kind(oracledb.DB_TYPE_NUMBER, 10, 2) is None
    assert resolve_column_kind(oracledb.DB_TYPE_NUMBER, 0, -127) is None
    assert resolve_column_kind(oracledb.DB_TYPE_BINARY_DOUBLE) == "float"
    assert resolve_column_kind(oracledb.DB_TYPE_TIMESTAMP) == "datetime"
    assert resolve_column_kind(oracledb.DB_TYPE_TIMESTAMP_TZ) is None
    assert resolve_column_kind(oracledb.DB_TYPE_VARCHAR) is None


def test_sql_fidelity_with_real_duckdb_cursor() -> None:
    duckdb = pytest.importorskip("duckdb")
    cursor = duckdb.connect().execute(
        "SELECT * FROM (VALUES "
        "(1::TINYINT, 9223372036854775807::BIGINT, 18446744073709551615::UBIGINT, "
        "5::DECIMAL(10,0), 1.25::DECIMAL(10,2), 2.5::DOUBLE, TRUE, 'x', "
        "TIMESTAMP '9999-12-31 23:59:59.123456'), "
        "(NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)) "
        "t(a, b, c, d, e, f, g, h, i)"
    )
    connector = object.__new__(SaConnector)
    connector.cursor = cursor
    connector.batch_size = 0
    connector.multiset_supported = False

    restored = connector._fetch_data(
        query_name="duckdb", progress=Mock(spec=Progress), check_column_duplicates=False
    )[0]

    assert [str(dtype) for dtype in restored.dtypes][:7] == [
        "Int64",
        "Int64",
        "UInt64",
        "Int64",
        "object",
        "float64",
        "boolean",
    ]
    assert str(restored["i"].dtype) == "datetime64[us]"
    assert restored["i"].iloc[0] == pd.Timestamp("9999-12-31 23:59:59.123456")
    assert int(restored["b"].iloc[0]) == 2**63 - 1
    assert int(restored["c"].iloc[0]) == 2**64 - 1
    assert restored["e"].iloc[0] == Decimal("1.25")
    assert restored.iloc[1].isna().all()


def test_sql_fidelity_with_real_duckdb_empty_result_keeps_declared_types() -> None:
    duckdb = pytest.importorskip("duckdb")
    cursor = duckdb.connect().execute(
        "SELECT 1::INTEGER AS a, TRUE AS b, 1.5::DOUBLE AS c WHERE FALSE"
    )
    connector = object.__new__(SaConnector)
    connector.cursor = cursor
    connector.batch_size = 0
    connector.multiset_supported = False

    restored = connector._fetch_data(
        query_name="duckdb", progress=Mock(spec=Progress), check_column_duplicates=False
    )[0]

    assert restored.empty
    assert [str(dtype) for dtype in restored.dtypes] == ["Int64", "boolean", "float64"]


@pytest.mark.parametrize(
    "values",
    [
        [pd.Timestamp("2026-01-01"), pd.NaT],
        [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02 12:30:15.123456789")],
        [pd.Timestamp("2026-01-01", tz="UTC"), pd.NaT],
    ],
    ids=["midnight", "nanoseconds", "timezone"],
)
def test_csv_fidelity_preserves_timestamp_text(tmp_path: Path, values: list) -> None:
    source = pd.DataFrame({"timestamp": values})
    original = source.copy(deep=True)

    export_results(source, directory=tmp_path, filename="timestamps", extension="csv")

    restored = pd.read_csv(
        tmp_path / "timestamps.csv", dtype=str, keep_default_na=False
    )
    for text, value in zip(restored["timestamp"], values, strict=True):
        if pd.isna(value):
            assert text == ""
        else:
            assert " " in text
            assert pd.Timestamp(text) == value
    pd.testing.assert_frame_equal(source, original)


@pytest.mark.parametrize("extra_columns", [0, 7])
def test_csv_fidelity_preserves_timestamps_across_chunks(
    tmp_path: Path, extra_columns: int
) -> None:
    chunk_rows = 100_000 // (extra_columns + 1)
    values = [pd.Timestamp("2002-10-10")] * chunk_rows + [
        pd.Timestamp("2001-06-25"),
        pd.Timestamp("1993-04-28 14:40:00"),
        pd.Timestamp("1993-04-28 14:40:00.123456789"),
        pd.NaT,
    ]
    source = pd.DataFrame({"APPOINTMENT_DATETIME": values})
    for position in range(extra_columns):
        source[f"other_{position}"] = position
    original = source.copy(deep=True)

    export_results(source, directory=tmp_path, filename="appointments", extension="csv")

    restored = pd.read_csv(
        tmp_path / "appointments.csv", dtype=str, keep_default_na=False
    )
    assert restored["APPOINTMENT_DATETIME"].tolist() == [
        "2002-10-10 00:00:00"
    ] * chunk_rows + [
        "2001-06-25 00:00:00",
        "1993-04-28 14:40:00",
        "1993-04-28 14:40:00.123456789",
        "",
    ]
    pd.testing.assert_frame_equal(source, original)


def test_csv_fidelity_preserves_dates_and_nullable_integers(tmp_path: Path) -> None:
    source = pd.DataFrame(
        {
            "date": [date(2026, 1, 1), None],
            "integer": pd.Series([2**53 + 1, None], dtype="Int64"),
        }
    )

    export_results(source, directory=tmp_path, filename="values", extension="csv")

    restored = pd.read_csv(tmp_path / "values.csv", dtype=str, keep_default_na=False)
    assert restored.to_dict("list") == {
        "date": ["2026-01-01", ""],
        "integer": [str(2**53 + 1), ""],
    }


def test_xlsx_fidelity_keeps_string_data_literal(tmp_path: Path) -> None:
    source = pd.DataFrame({"text": ["=1+1", "https://example.com", "00123", "NA"]})

    export_results(source, directory=tmp_path, filename="literals", extension="xlsx")

    with (tmp_path / "literals.xlsx").open("rb") as stream:
        workbook = load_workbook(BytesIO(stream.read()))
    try:
        cells = [row[0] for row in workbook.active.iter_rows(min_row=2)]
        assert [cell.value for cell in cells] == source["text"].tolist()
        assert all(cell.data_type == "s" for cell in cells)
        assert all(cell.hyperlink is None for cell in cells)
    finally:
        workbook.close()

    restored = extract_spreadsheets(tmp_path / "literals.xlsx", dtype={"text": str})[
        0
    ].df
    pd.testing.assert_frame_equal(restored, source)


def test_xlsx_export_creates_tables_for_each_sheet_by_default(
    tmp_path: Path,
) -> None:
    results = ResultList(
        [
            Result(pd.DataFrame({"id": [1, 2], "label": ["a", "b"]}), "First"),
            Result(pd.DataFrame({"amount": [3]}), "Second"),
        ]
    )

    export_results(results, directory=tmp_path, filename="tables", extension="xlsx")

    workbook = load_workbook(tmp_path / "tables.xlsx")
    try:
        first, second = workbook["First"], workbook["Second"]
        assert list(first.tables) == ["Table1"]
        assert first.tables["Table1"].ref == "A1:B3"
        assert [column.name for column in first.tables["Table1"].tableColumns] == [
            "id",
            "label",
        ]
        assert list(second.tables) == ["Table2"]
        assert second.tables["Table2"].ref == "A1:A2"
        assert [cell.value for cell in first[1]] == ["id", "label"]
        assert [cell.value for cell in first[2]] == [1, "a"]
    finally:
        workbook.close()


def test_xlsx_export_can_disable_tables(tmp_path: Path) -> None:
    source = pd.DataFrame({"id": [1], "label": ["a"]})

    export_results(
        source,
        directory=tmp_path,
        filename="no_tables",
        extension="xlsx",
        excel_tables=False,
    )

    workbook = load_workbook(tmp_path / "no_tables.xlsx")
    try:
        worksheet = workbook.active
        assert len(worksheet.tables) == 0
        assert [cell.value for cell in worksheet[1]] == ["id", "label"]
        assert [cell.value for cell in worksheet[2]] == [1, "a"]
    finally:
        workbook.close()


@pytest.mark.parametrize("excel_tables", [False, True])
def test_xlsx_empty_export_preserves_headers(
    tmp_path: Path, excel_tables: bool
) -> None:
    source = pd.DataFrame(columns=["id", "label"])
    export_results(
        source,
        directory=tmp_path,
        filename="empty",
        extension="xlsx",
        excel_tables=excel_tables,
    )

    workbook = load_workbook(tmp_path / "empty.xlsx")
    try:
        worksheet = workbook.active
        assert [cell.value for cell in worksheet[1]] == ["id", "label"]
        assert len(worksheet.tables) == 0
    finally:
        workbook.close()


@pytest.mark.parametrize(
    "columns", [["value", "VALUE"], ["", "value"], [None, "value"]]
)
def test_xlsx_export_warns_and_skips_table_for_invalid_headers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], columns: list[str | None]
) -> None:
    source = pd.DataFrame([[1, 2]], columns=columns)

    export_results(
        source,
        directory=tmp_path,
        filename="invalid_headers",
        extension="xlsx",
    )

    assert "exporting without an Excel table" in capsys.readouterr().out
    workbook = load_workbook(tmp_path / "invalid_headers.xlsx")
    try:
        worksheet = workbook.active
        assert len(worksheet.tables) == 0
        expected_headers = [header or None for header in columns]
        assert [cell.value for cell in worksheet[1]] == expected_headers
        assert [cell.value for cell in worksheet[2]] == [1, 2]
    finally:
        workbook.close()


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_import_fidelity_honors_explicit_types(tmp_path: Path, extension: str) -> None:
    source = pd.DataFrame(
        {
            "float": [1.0, None, 2.0],
            "identifier": ["00123", "NA", "00456"],
            "timestamp": pd.to_datetime(["2026-01-01", None, "2026-01-02"]),
        }
    )
    export_results(source, directory=tmp_path, filename="typed", extension=extension)

    restored = extract_spreadsheets(
        tmp_path / f"typed.{extension}",
        dtype={"float": "float64", "identifier": str},
        parse_dates=["timestamp"],
    )[0].df

    pd.testing.assert_frame_equal(restored, source)


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_import_fidelity_honors_null_options(tmp_path: Path, extension: str) -> None:
    source = pd.DataFrame({"text": ["NA", "", "NULL", "nan", "other"]})
    export_results(source, directory=tmp_path, filename="nulls", extension=extension)

    restored = extract_spreadsheets(
        tmp_path / f"nulls.{extension}",
        dtype=str,
        keep_default_na=False,
        na_values=[],
    )[0].df
    pd.testing.assert_frame_equal(restored, source)

    defaults = extract_spreadsheets(tmp_path / f"nulls.{extension}", dtype=str)[0].df
    assert defaults["text"].isna().tolist() == [False, True, False, False, False]


@pytest.mark.parametrize("integer", [2**53 + 1, 2**63 - 1, 2**63, 2**64 - 1])
def test_csv_import_fidelity_preserves_large_nullable_integers(
    tmp_path: Path, integer: int
) -> None:
    source = pd.DataFrame(
        {
            "integer": pd.Series(
                [integer, None], dtype="Int64" if integer < 2**63 else "UInt64"
            ),
            "row": [0, 1],
        }
    )
    export_results(source, directory=tmp_path, filename="integers", extension="csv")

    options = {"dtype": {"integer": "UInt64"}} if integer >= 2**63 else {}
    restored = extract_spreadsheets(tmp_path / "integers.csv", **options)[0].df

    assert int(restored["integer"].iloc[0]) == integer
    assert pd.isna(restored["integer"].iloc[1])
    assert restored["integer"].dtype == source["integer"].dtype


@pytest.mark.parametrize("clean_df", [True, False])
def test_parquet_import_fidelity_preserves_schema(
    tmp_path: Path, clean_df: bool
) -> None:
    source = pd.DataFrame(
        {
            "integer": pd.Series([2**53 + 1, None], dtype="Int64"),
            "unsigned": pd.Series([2**64 - 1, None], dtype="UInt64"),
            "float": pd.Series([1.0, None], dtype="Float64"),
            "boolean": pd.Series([True, None], dtype="boolean"),
            "string": pd.Series(["00123", None], dtype="string"),
            "empty": pd.Series(["", "NA"], dtype="string"),
            "all_null": pd.Series([None, None], dtype="Int64"),
            "timestamp": pd.Series([pd.Timestamp("2026-01-01"), pd.NaT]),
            "precise_timestamp": pd.Series(
                [pd.Timestamp("2026-01-01 01:02:03.123456789", tz="UTC"), pd.NaT]
            ),
        }
    )
    export_results(source, directory=tmp_path, filename="schema", extension="parquet")

    result = extract_spreadsheets(tmp_path / "schema.parquet", clean_df=clean_df)[0]

    pd.testing.assert_frame_equal(result.df, source)
    assert result.df_name == "schema"
    assert result.filename == "schema.parquet"
    assert Path(result.filepath) == tmp_path / "schema.parquet"


@pytest.mark.parametrize("extension", ["csv", "xlsx", "parquet"])
def test_export_fidelity_omits_indexes(tmp_path: Path, extension: str) -> None:
    source = pd.DataFrame(
        {"value": [1, 2]}, index=pd.Index([10, 20], name="identifier")
    )
    original = source.copy(deep=True)
    export_results(source, directory=tmp_path, filename="indexed", extension=extension)

    restored = extract_spreadsheets(tmp_path / f"indexed.{extension}")[0].df

    assert restored.columns.tolist() == ["value"]
    assert restored.index.tolist() == [0, 1]
    pd.testing.assert_frame_equal(source, original)


def test_import_fidelity_supports_mixed_format_directories(tmp_path: Path) -> None:
    source = pd.DataFrame({"value": [1, 2]})
    for extension in ["csv", "xlsx", "parquet"]:
        export_results(
            source, directory=tmp_path, filename=extension, extension=extension
        )

    results = extract_spreadsheets(tmp_path)

    assert {result.df_name for result in results} == {"csv", "xlsx", "parquet"}
    assert all(result.df["value"].tolist() == [1, 2] for result in results)


def test_csv_import_fidelity_respects_cleaning_opt_out(tmp_path: Path) -> None:
    source = pd.DataFrame({"value": pd.Series([1, None], dtype="Int64"), "row": [0, 1]})
    export_results(source, directory=tmp_path, filename="legacy", extension="csv")

    result = extract_spreadsheets(tmp_path / "legacy.csv", clean_df=False)[0]

    assert str(result.df["value"].dtype) == "float64"


def test_csv_import_fidelity_respects_caller_backend(tmp_path: Path) -> None:
    source = pd.DataFrame({"value": [1.0, None], "row": [0, 1]})
    export_results(source, directory=tmp_path, filename="arrow", extension="csv")

    result = extract_spreadsheets(tmp_path / "arrow.csv", dtype_backend="pyarrow")[0]

    assert str(result.df["value"].dtype) == "double[pyarrow]"
    assert result.df["value"].iloc[0] == 1.0
    assert pd.isna(result.df["value"].iloc[1])


def test_csv_import_fidelity_respects_decimal_converter(tmp_path: Path) -> None:
    source = pd.DataFrame(
        {"value": [Decimal("1234567890.123456789"), None], "row": [0, 1]}
    )
    export_results(source, directory=tmp_path, filename="decimal", extension="csv")

    result = extract_spreadsheets(
        tmp_path / "decimal.csv",
        converters={"value": lambda value: Decimal(value) if value else None},
    )[0]

    assert result.df["value"].iloc[0] == source["value"].iloc[0]
    assert pd.isna(result.df["value"].iloc[1])


def test_xlsx_fidelity_distinguishes_date_and_midnight_datetime(tmp_path: Path) -> None:
    source = pd.DataFrame(
        {"date": [date(2026, 1, 1)], "timestamp": [pd.Timestamp("2026-01-01")]}
    )
    export_results(source, directory=tmp_path, filename="dates", extension="xlsx")

    workbook = load_workbook(tmp_path / "dates.xlsx")
    try:
        date_cell, timestamp_cell = list(workbook.active.iter_rows(min_row=2))[0]
        assert date_cell.number_format == "DD/MM/YYYY"
        assert timestamp_cell.number_format == "DD/MM/YYYY HH:MM:SS"
        assert timestamp_cell.value == datetime(2026, 1, 1)
    finally:
        workbook.close()


def test_xlsx_fidelity_rejects_timezone_loss(tmp_path: Path) -> None:
    source = pd.DataFrame({"timestamp": [pd.Timestamp("2026-01-01", tz="UTC")]})

    with pytest.raises(
        ValueError, match="Excel does not support datetimes with timezones"
    ):
        export_results(
            source, directory=tmp_path, filename="timezone", extension="xlsx"
        )

    assert not (tmp_path / "timezone.xlsx").exists()


def test_import_fidelity_keeps_string_analysis_compatible(tmp_path: Path) -> None:
    source = pd.DataFrame(
        {"label": ["alpha", "beta"], "date": ["2026-01-01", "2026-01-02"]}
    )
    export_results(source, directory=tmp_path, filename="analysis", extension="csv")
    restored = extract_spreadsheets(tmp_path / "analysis.csv")[0].df

    stats = examine(restored, show_results=False).stats

    assert stats.loc[stats["column_name"] == "label", "max_length"].iloc[0] == 5
    date_converter_df(restored, columns="date", readouts=False)
    assert pd.api.types.is_datetime64_any_dtype(restored["date"])
    assert restored["date"].iloc[0] == pd.Timestamp("2026-01-01")


def test_csv_fidelity_handles_nonexistent_local_midnight(tmp_path: Path) -> None:
    timestamp = pd.Timestamp("2018-11-04 01:00:00", tz="America/Sao_Paulo")
    source = pd.DataFrame({"timestamp": [timestamp]})
    export_results(source, directory=tmp_path, filename="dst", extension="csv")

    restored = pd.read_csv(tmp_path / "dst.csv", dtype=str)

    assert pd.Timestamp(restored["timestamp"].iloc[0]) == timestamp


@pytest.mark.parametrize(
    "dtype", [str, defaultdict(lambda: str)], ids=["scalar", "defaultdict"]
)
def test_csv_import_fidelity_parses_dates_with_default_string_dtype(
    tmp_path: Path, dtype: object
) -> None:
    source = pd.DataFrame(
        {
            "identifier": ["00123", "00456"],
            "timestamp": pd.to_datetime(["2026-01-01", None]),
        }
    )
    export_results(source, directory=tmp_path, filename="strings", extension="csv")

    restored = extract_spreadsheets(
        tmp_path / "strings.csv", dtype=dtype, parse_dates=["timestamp"]
    )[0].df

    pd.testing.assert_frame_equal(restored, source)
