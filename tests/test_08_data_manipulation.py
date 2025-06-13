import numpy as np
import pandas as pd
import pytest

from kraken.analysis.data_manipulation import check_df_integers


@pytest.fixture
def get_integers_input_df():
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


def test_check_df_integers(get_integers_input_df: pd.DataFrame):
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
