import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from pandas import DataFrame

from kraken.classes.pack_lists import ResultList
from kraken.classes.packs import Result
from kraken.exporting.result_export_extensions import (
    _prepare_results_csv,
    _prepare_results_parquet,
    _prepare_results_xlsx,
)
from kraken.support.readout import readout
from kraken.support.support import (
    _check_df_name_duplicates,
    calculate_runtime,
)
from kraken.support.support_checks import (
    _enforce_in_list,
    _enforce_type,
    _enforce_type_one_of,
)

SUPPORTED_EXTENSIONS: dict[str, tuple[str, Callable[..., bytes]]] = {
    "xlsx": ("single", _prepare_results_xlsx),
    "csv": ("multiple", _prepare_results_csv),
    "parquet": ("multiple", _prepare_results_parquet),
}


def export_results(
    results: Result | ResultList | DataFrame,
    directory: str | Path = "",
    extension: str = "csv",
    filename: str = "",
    prefix: str = "",
    suffix: str = "",
    overwrite: bool = False,
    zip_filename: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Summary:
        -   Exports results or a dataframe to a supported extension type (csv or xlsx).
        -   For filetypes supporting multiple dataframes (such as xlsx), the filename argument can be provided.
        -   For filetypes supporting single dataframes only (such as csv) the filename provided will be appended to the prefix (if given), with the dataframe name used instead.

    Args:
        -   results (Result | ResultList | DataFrame): results to export.
        -   directory (str | Path): Output directory. Created if not found.
        -   extension (str, optional): Extension to write files to. Defaults to "csv".
        -   filename (str, optional): If entered, used as the output file name. If multiple files are output, this is appended the prefix and precedes the dataframe name. Defaults to "".
        -   prefix (str, optional): Prefix to use when multiple output files are generated. Defaults to "".
        -   suffix (str, optional): Suffix to use when multiple output files are generated. Defaults to "".
        -   overwrite (bool, optional): If False, Kraken will append the output file in the event of a conflict. If True, Kraken will overwrite the existing file. Defaults to False.
        -   zip_filename (str, optional): If provided, Kraken will zip files in memory before writing to this filename, rather than directly. Defaults to None (direct writing of files).

    **kwargs:
        -   delimiter (str, optional): If exporting to a delimited file format (like CSV), this is used as the delimiter. Defaults to ",".

    Returns: Nothing
    """

    # Prepare
    readout.print("Preparing to Export Results...")
    start = datetime.now()
    extension = extension.replace(".", "")

    # Checks
    __run_argument_checks(results, directory, extension)

    # Prepare export packs
    export_pack_list = __prepare_export_packs(
        results, filename, prefix, suffix, extension
    )

    # Check for dataframes
    number_of_dataframes = len(export_pack_list)
    if number_of_dataframes == 0:
        readout.warn("  -> WARNING: No dataframes in results. Ignoring Export.'\n")
        return

    # Prepare for Export
    export_directory = _prepare_export_directory(directory)
    export_filename = __set_single_export_filename(
        export_pack_list, filename, prefix, suffix, extension
    )
    single_file_mode = __is_single_file_mode(export_pack_list, extension)
    _file_prep_func = __fetch_extension_prep_function(extension)

    # Single File Export
    if single_file_mode:
        files_to_write = __prepare_single_file_buffers(
            export_pack_list, export_filename, extension, **kwargs
        )

    # Multi File Mode
    if not single_file_mode:
        files_to_write = __prepare_multi_file_buffers(
            export_pack_list, extension, filename, prefix, suffix, **kwargs
        )

    readout.print("\n", end="")

    # Write files
    if zip_filename:
        __write_files_to_zip(files_to_write, export_directory, overwrite, zip_filename)

    else:
        __write_files_directly(files_to_write, export_directory, overwrite)

    readout.print(
        f"\nExport Complete in {calculate_runtime(start, datetime.now()).message}\n"
    )


### Support Functions ###
# Check Output Filepath
def _prepare_export_directory(filepath: str | Path) -> Path:
    filepath = Path(filepath)
    if Path.is_dir(filepath):
        readout.print(f"  Output directory detected: {filepath.resolve()}")
    else:
        readout.print(f"  Output directory not detected: {filepath.resolve()}")
        filepath.mkdir(parents=True, exist_ok=False)
        readout.warn("  - Output directory created")
    return filepath


# Prepare Export Packs
def __prepare_export_packs(
    results: DataFrame | Result | ResultList,
    filename: str,
    prefix: str,
    suffix: str,
    extension: str,
) -> dict[str, DataFrame]:
    if isinstance(results, (ResultList)):
        export_pack_list = results.convert_to_dict()
    elif isinstance(results, (Result)):
        export_pack_list = {results.df_name: results.df}
    elif isinstance(results, DataFrame):
        if filename:
            df_name = f"{filename}"
        else:
            df_name = f"{datetime.now().strftime('%y%m%d')}_Kraken_Export"
            readout.warn(
                f"WARNING: Exporting lone dataframe with empty 'filename' argument. Exporting as '{prefix}{df_name}{suffix}.{extension}'...\n"
            )
        export_pack_list = {df_name: results}
    return export_pack_list


# Check Filename Conflicts
def _check_overwrite_conflict(filepath: str | Path, overwrite: bool = False) -> Path:
    # Assertions
    _enforce_type_one_of(
        filepath, "filepath", (str, Path), "'filepath' must be a string or a Path"
    )
    _enforce_type(overwrite, "overwrite", bool, "'overwrite' must be True or False")

    # Assess Conflict
    filepath = Path(filepath)
    if not Path.exists(filepath):
        return filepath

    # Process Conflict
    readout.warn("conflict: ", end="")

    if overwrite:
        readout.warn("overwriting... ", end="")
        return filepath

    old_stem = filepath.stem
    ext = filepath.suffix
    conflicts = [
        Path(dir_file).stem
        for dir_file in Path(filepath.parent).glob("**/*")
        if dir_file.is_file()
        and Path(dir_file).suffix == Path(filepath).suffix
        and Path(dir_file).stem[: len(old_stem)] == old_stem
    ]

    for i in range(len(conflicts) + 1):
        new_stem = f"{old_stem}_{i + 2:02d}"
        if not conflicts.count(new_stem):
            new_filename = f"{new_stem}{ext}"
            new_filepath = Path.joinpath(filepath.parent, new_filename)
            readout.warn(f"renaming to '{new_filename}'... ", end="")
            return new_filepath


# Check Arguments
def __run_argument_checks(
    results: Result | ResultList | DataFrame,
    directory: str | Path,
    extension: str,
) -> None:
    _enforce_in_list(
        extension,
        SUPPORTED_EXTENSIONS,
        message=f"extension '{extension}' is not supported. Supported extensions = {list(SUPPORTED_EXTENSIONS)}",
    )
    _enforce_type_one_of(results, "results", (Result, ResultList, DataFrame))
    _enforce_type_one_of(directory, "directory", (str, Path))

    # Check for duplicates
    if isinstance(results, (ResultList)):
        _check_df_name_duplicates(results)


# Set Export Filename for Single File Mode
def __set_single_export_filename(
    export_pack_list: dict, filename: str, prefix: str, suffix: str, extension: str
) -> str:
    if filename:
        return f"{prefix}{filename}{suffix}.{extension}"
    else:
        number_of_dataframes = len(export_pack_list)
        first_df_name = next(iter(export_pack_list))
        s = "s" if number_of_dataframes > 2 else ""
        multi_append = (
            ""
            if number_of_dataframes == 1
            else f" (+{number_of_dataframes - 1} dataframe{s})"
        )
    return f"{prefix}{first_df_name}{multi_append}{suffix}.{extension}"


# Check Single/Multi Mode
def __is_single_file_mode(export_pack_list: dict, extension: str) -> bool:
    number_of_dataframes = len(export_pack_list)
    return number_of_dataframes == 1 or SUPPORTED_EXTENSIONS[extension][0] == "single"


# Fetch Extension Preparation Function
def __fetch_extension_prep_function(extension: str) -> Callable[..., bytes]:
    return SUPPORTED_EXTENSIONS[extension][1]


# Write Files to ZIP
def __write_files_to_zip(
    files_to_write: dict,
    export_directory: Path,
    overwrite: bool,
    zip_filename: str,
) -> None:
    readout.print(f"Writing files to '{zip_filename}.zip'... ", end="")
    full_export_filepath = _check_overwrite_conflict(
        Path.joinpath(export_directory, zip_filename + ".zip"), overwrite=overwrite
    )
    readout.print("\n", end="")
    with zipfile.ZipFile(full_export_filepath, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for export_filename, buffer in files_to_write.items():
            readout.print(f" - adding '{export_filename}'")
            zip_file.writestr(export_filename, buffer)


# Write Files Directly
def __write_files_directly(
    files_to_write: dict, export_directory: Path, overwrite: bool
) -> None:
    readout.print("Writing files...")
    for export_filename, buffer in files_to_write.items():
        readout.print(f" - writing '{export_filename}'... ", end="")
        full_export_filepath = _check_overwrite_conflict(
            Path.joinpath(export_directory, export_filename), overwrite=overwrite
        )
        with open(full_export_filepath, "wb") as file:
            file.write(buffer)

        readout.print("complete")


def __prepare_single_file_buffers(
    export_pack_list: dict, export_filename: str, extension: str, **kwargs: Any
) -> dict:
    files_to_write = {}
    readout.print(f"\nPreparing file '{export_filename}'... ", end="")
    _file_prep_func = __fetch_extension_prep_function(extension)
    file_buffer = _file_prep_func(export_pack_list, **kwargs)
    files_to_write[export_filename] = file_buffer
    readout.print("\n", end="")

    return files_to_write


def __prepare_multi_file_buffers(
    export_pack_list: dict,
    extension: str,
    filename: str,
    prefix: str,
    suffix: str,
    **kwargs: Any,
) -> dict:
    files_to_write = {}
    number_of_dataframes = len(export_pack_list)
    readout.print(f"\nPreparing {number_of_dataframes} {extension} files... ")
    if filename:
        readout.warn(
            f"  -> WARNING: filename '{filename}' entered, but multiple .{extension} files to export. Appending dataframe names."
        )

    for df_name, df in export_pack_list.items():
        export_filename = f"{prefix}{filename}{df_name}{suffix}.{extension}"
        readout.print(f" - preparing '{export_filename}'... ")
        _file_prep_func = __fetch_extension_prep_function(extension)
        file_buffer = _file_prep_func({df_name: df}, **kwargs)
        files_to_write[export_filename] = file_buffer

    return files_to_write
