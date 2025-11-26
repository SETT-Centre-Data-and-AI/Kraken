import pytest  # noqa
from support import integrity  # noqa
from kraken import export_results, extract_spreadsheets
from pandas import DataFrame
from typing import Any
from support.config import config
from pathlib import Path

PATH_OUTPUTS = integrity.PATH_OUTPUTS
TEST_SUB_DIR = Path(__name__).stem
TEST_FILENAME = "Test Export"
TEST_DATAFRAME = DataFrame(
    data={"columnA": [1, 2, 3], "columnB": [4, 5, 6], "columnC": ["7", "8", "NA"]}
)


def count_outputs(directory: Path) -> int:
    return sum(1 for file in directory.iterdir() if file.is_file())


def export_standard_file(
    directory: Path, name: str, extension: str = "xlsx", **kwargs: Any
) -> None:
    export_results(
        results=TEST_DATAFRAME,
        directory=directory,
        filename=name,
        extension=extension,
        **kwargs,
    )
    assert (directory / f"{name}.{extension}").exists()


# Test that export of all extensions is working
@pytest.mark.parametrize(
    "extension", ["xlsx", "csv", "parquet"], ids=["xlsx", "csv", "parquet"]
)
def test_export_extensions(extension: str) -> None:
    file_stem = "test_export_extensions"
    with config.setup_test_output_subdir(name=TEST_SUB_DIR) as directory:
        export_standard_file(directory=directory, name=file_stem, extension=extension)
        filepath = directory / f"{file_stem}.{extension}"
        assert filepath.exists()
        assert filepath.is_file()


# Test that export does not overwrite on a filename conflict
def test_export_name_conflict() -> None:
    file_stem = "test_export_name_conflict"
    with config.setup_test_output_subdir(name=TEST_SUB_DIR) as directory:
        # Export Twice
        for _ in range(2):
            export_standard_file(directory=directory, name=file_stem)

        filepaths = [
            directory / f"{file_stem}.xlsx",
            directory / f"{file_stem}_02.xlsx",
        ]
        for filepath in filepaths:
            assert filepath.exists()
            assert filepath.is_file()


# Test can overwrite existing file
def test_export_name_overwrite() -> None:
    file_stem = "test_export_name_overwrite"
    with config.setup_test_output_subdir(name=TEST_SUB_DIR) as directory:
        # Export twice
        for _ in range(2):
            export_standard_file(directory=directory, name=file_stem, overwrite=True)
            filepath = directory / f"{file_stem}.xlsx"

        assert count_outputs(directory) == 1
        assert filepath.exists()
        assert filepath.is_file()


# Test import
def test_import() -> None:
    with config.setup_test_output_subdir(name=TEST_SUB_DIR) as directory:
        file_stem = "test_import"
        export_standard_file(directory=directory, name=file_stem)

        expected_columns = ["columnA", "columnB", "columnC"]

        imports = extract_spreadsheets(filepaths=directory, filename=file_stem)
        test_result = imports.get(file_stem)

        assert imports is not None
        assert test_result is not None
        assert test_result.df_name == file_stem
        assert test_result.df.columns.to_list() == expected_columns
        assert (
            test_result.df.isna().sum().sum() == 0
        )  # Na should not be interpreted as NaN


if __name__ == "__main__":
    pytest.main([__file__])
