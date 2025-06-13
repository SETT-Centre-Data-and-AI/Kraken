import pytest  # noqa
from unittest.mock import patch
from support import integrity  # noqa
from support.connection import get_main_test_connector  # noqa
from kraken import export_results, extract_spreadsheets
from pandas import DataFrame

PATH_OUTPUTS = integrity.PATH_OUTPUTS
TEST_FILENAME = "Test Export"
TEST_DATAFRAME = DataFrame(
    data={"columnA": [1, 2, 3], "columnB": [4, 5, 6], "columnC": ["7", "8", "NA"]}
)


def clear_outputs() -> None:
    for file in PATH_OUTPUTS.iterdir():
        if file.is_file():
            file.unlink()


def count_outputs() -> int:
    return sum(1 for file in PATH_OUTPUTS.iterdir() if file.is_file())


def export_standard_xlsx(**kwargs) -> None:
    export_results(
        results=TEST_DATAFRAME,
        directory=PATH_OUTPUTS,
        filename=TEST_FILENAME,
        extension="xlsx",
        **kwargs,
    )


# Test that export of all extensions is working
@pytest.mark.parametrize("extension", ["xlsx", "csv", "parquet"])
def test_export_extensions(extension):
    clear_outputs()
    with patch("builtins.input", side_effect=extension):
        export_results(
            results=TEST_DATAFRAME,
            directory=PATH_OUTPUTS,
            filename=TEST_FILENAME,
            extension=extension,
        )
        filepath = PATH_OUTPUTS / f"{TEST_FILENAME}.{extension}"
        assert filepath.exists()
        assert filepath.is_file()
    clear_outputs()


# Test that export does not overwrite on a filename conflict
def test_export_name_conflict():
    clear_outputs()

    # Export Twice
    for _ in range(2):
        export_standard_xlsx()

    filepaths = [
        PATH_OUTPUTS / f"{TEST_FILENAME}.xlsx",
        PATH_OUTPUTS / f"{TEST_FILENAME}_02.xlsx",
    ]
    for filepath in filepaths:
        assert filepath.exists()
        assert filepath.is_file()

    clear_outputs()


# Test can overwrite existing file
def test_export_name_overwrite():
    clear_outputs()

    # Export twice
    for _ in range(2):
        export_standard_xlsx(overwrite=True)
    filepath = PATH_OUTPUTS / f"{TEST_FILENAME}.xlsx"

    assert count_outputs() == 1
    assert filepath.exists()
    assert filepath.is_file()

    clear_outputs()


# Test import
def test_import():
    clear_outputs()
    export_standard_xlsx()

    expected_columns = ["columnA", "columnB", "columnC"]

    imports = extract_spreadsheets(filepaths=PATH_OUTPUTS, filename="TEST_FILENAME")
    test_result = imports.get(TEST_FILENAME)

    assert imports is not None
    assert test_result is not None
    assert test_result.df_name == TEST_FILENAME
    assert test_result.df.columns.to_list() == expected_columns
    assert test_result.df.isna().sum().sum() == 0  # Na should not be interpreted as NaN
    clear_outputs()


if __name__ == "__main__":
    pytest.main([__file__])
