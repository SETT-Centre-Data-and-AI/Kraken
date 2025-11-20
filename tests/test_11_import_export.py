import pytest  # noqa
from unittest.mock import patch
from support import integrity  # noqa
from kraken import export_results, extract_spreadsheets
from pandas import DataFrame
from typing import Any
from support.config import config
from pathlib import Path

PATH_OUTPUTS = integrity.PATH_OUTPUTS
TEST_FILENAME = "Test Export"
TEST_DATAFRAME = DataFrame(
    data={"columnA": [1, 2, 3], "columnB": [4, 5, 6], "columnC": ["7", "8", "NA"]}
)
test_file = Path(__name__).stem


def count_outputs(directory: Path) -> int:
    return sum(1 for file in directory.iterdir() if file.is_file())


def export_standard_file(
    directory: Path, extension: str = "xlsx", **kwargs: Any
) -> None:
    export_results(
        results=TEST_DATAFRAME,
        directory=directory,
        filename=TEST_FILENAME,
        extension=extension,
        **kwargs,
    )


# Test that export of all extensions is working
@pytest.mark.parametrize("extension", ["xlsx", "csv", "parquet"])
def test_export_extensions(extension: str) -> None:
    with config.setup_test_output_subdir(name=test_file) as directory:
        with patch("builtins.input", side_effect=extension):
            export_standard_file(directory=directory, extension=extension)
            filepath = directory / f"{TEST_FILENAME}.{extension}"
            assert filepath.exists()
            assert filepath.is_file()


# Test that export does not overwrite on a filename conflict
def test_export_name_conflict() -> None:
    with config.setup_test_output_subdir(name=test_file) as directory:
        # Export Twice
        for _ in range(2):
            export_standard_file(directory=directory)

        filepaths = [
            directory / f"{TEST_FILENAME}.xlsx",
            directory / f"{TEST_FILENAME}_02.xlsx",
        ]
        for filepath in filepaths:
            assert filepath.exists()
            assert filepath.is_file()


# Test can overwrite existing file
def test_export_name_overwrite() -> None:
    with config.setup_test_output_subdir(name=test_file) as directory:
        # Export twice
        for _ in range(2):
            export_standard_file(directory=directory, overwrite=True)
            filepath = directory / f"{TEST_FILENAME}.xlsx"

        assert count_outputs(directory) == 1
        assert filepath.exists()
        assert filepath.is_file()


# Test import
def test_import() -> None:
    with config.setup_test_output_subdir(name=test_file) as directory:
        export_standard_file(directory=directory)

        expected_columns = ["columnA", "columnB", "columnC"]

        imports = extract_spreadsheets(filepaths=directory, filename="TEST_FILENAME")
        test_result = imports.get(TEST_FILENAME)

        assert imports is not None
        assert test_result is not None
        assert test_result.df_name == TEST_FILENAME
        assert test_result.df.columns.to_list() == expected_columns
        assert (
            test_result.df.isna().sum().sum() == 0
        )  # Na should not be interpreted as NaN


if __name__ == "__main__":
    pytest.main([__file__])
