import numpy as np
import pandas as pd
import pytest

from kraken.analysis.data_manipulation import (
    check_df_integers,
    date_converter_df,
    examine,
)
from kraken.classes.data_types import StatsPack
from kraken.classes.pack_lists import ResultList
from kraken.classes.packs import Result


@pytest.fixture
def get_integers_input_df() -> pd.DataFrame:
    # data source: pandas.Series.convert_dtypes
    df = pd.DataFrame(
        {
            "a": pd.Series([1, 2, 3], dtype=np.dtype("int32")),
            "b": pd.Series(["x", "y", "z"], dtype=np.dtype("O")),
            "c": pd.Series([True, False, np.nan], dtype=np.dtype("O")),
            "d": pd.Series(["h", "i", np.nan], dtype=np.dtype("O")),
            "e": pd.Series([10, np.nan, 20], dtype=np.dtype("float")),
            "f": pd.Series([np.nan, 100.5, 200], dtype=np.dtype("float")),
        }
    ).assign(g=[10, 15, 20])
    df["g"] = df["g"].astype(np.dtype("int32"))
    df = df.rename(columns={"g": "e"})
    return df


def test_check_df_integers(get_integers_input_df: pd.DataFrame) -> None:
    output_df = check_df_integers(get_integers_input_df)
    expected_df = pd.DataFrame(
        {
            "a": pd.Series([1, 2, 3], dtype=np.dtype("int32")),
            "b": pd.Series(["x", "y", "z"], dtype=np.dtype("O")),
            "c": pd.Series([True, False, np.nan], dtype=np.dtype("O")),
            "d": pd.Series(["h", "i", np.nan], dtype=np.dtype("O")),
            "e": pd.Series([10, pd.NA, 20], dtype="Int64"),
            "f": pd.Series([np.nan, 100.5, 200], dtype=np.dtype("float")),
        }
    ).assign(g=[10, 15, 20])
    expected_df["g"] = expected_df["g"].astype(np.dtype("int32"))
    expected_df = expected_df.rename(columns={"g": "e"})
    pd.testing.assert_frame_equal(output_df, expected_df, check_dtype=True)


def test_date_converter_leaves_numpy_string_categories_unchanged() -> None:
    source = pd.DataFrame(
        {"specialty": np.random.default_rng(1).choice(["Cardiology", "Respiratory"], 4)}
    )

    converted = date_converter_df(source, readouts=False)

    assert converted["specialty"].tolist() == [
        "Cardiology",
        "Respiratory",
        "Respiratory",
        "Respiratory",
    ]
    assert converted["specialty"].dtype == object


def test_date_converter_converts_numpy_string_dates() -> None:
    source = pd.DataFrame(
        {"event_date": np.array(["2025-01-01", "2025-02-01"], dtype=np.str_)}
    )

    converted = date_converter_df(source, readouts=False)

    assert str(converted["event_date"].dtype) == "datetime64[ns]"
    assert converted["event_date"].tolist() == [
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-02-01"),
    ]


def test_date_converter_converts_sql_datetime_strings_with_microseconds() -> None:
    source = pd.DataFrame(
        {"event_date": ["2023-10-19 00:00:00.000000", "2023-10-20 12:30:15.123456"]}
    )

    converted = date_converter_df(source, readouts=False)

    assert str(converted["event_date"].dtype) == "datetime64[ns]"
    assert converted["event_date"].tolist() == [
        pd.Timestamp("2023-10-19"),
        pd.Timestamp("2023-10-20 12:30:15.123456"),
    ]


def test_examine_always_returns_stats_pack() -> None:
    source = pd.DataFrame({"category": ["a", "b", "b"]})

    result = examine(source, df_name="example", show_results=False)

    assert isinstance(result, StatsPack)
    assert result.df_name == "example"
    assert result.stats.shape == (1, 14)
    assert result.categories.shape == (2, 4)


def test_examine_return_results_is_a_deprecated_no_op() -> None:
    source = pd.DataFrame({"category": ["a", "b", "b"]})

    expected = examine(source, show_results=False)
    with pytest.warns(DeprecationWarning, match="deprecated and has no effect"):
        compatible = examine(source, show_results=False, return_results=True)

    pd.testing.assert_frame_equal(compatible.stats, expected.stats)
    pd.testing.assert_frame_equal(compatible.categories, expected.categories)


def test_stats_pack_repr_is_compact_and_names_selectable_dataframes() -> None:
    result = examine(
        pd.DataFrame({"category": ["a", "b", "b"]}),
        df_name="example",
        show_results=False,
    )

    assert repr(result) == (
        "StatsPack(df_name='example', stats=DataFrame(shape=(1, 14)), "
        "categories=DataFrame(shape=(2, 4)))"
    )
    assert "column_name" not in repr(result)
    assert isinstance(result.stats, pd.DataFrame)
    assert isinstance(result.categories, pd.DataFrame)


def test_examine_wrappers_always_return_stats_pack() -> None:
    source = pd.DataFrame({"category": ["a", "b", "b"]})
    result = Result(source, df_name="example")
    results = ResultList([result])

    direct = result.examine(show_results=False)
    selected = results.examine("example", show_results=False)

    assert isinstance(direct, StatsPack)
    assert isinstance(selected, StatsPack)
    assert direct.df_name == selected.df_name == "example"
