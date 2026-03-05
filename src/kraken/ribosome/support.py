from pathlib import Path

from kraken.support.support import _extract_instruction
from kraken.support.support_checks import _enforce_type, _enforce_type_one_of


def _check_filepaths_type(filepaths: str | Path | list[str] | list[Path]) -> None:
    _enforce_type_one_of(
        filepaths,
        "filepaths",
        (str, Path, list),
        error_message="'filepaths' argument must be type string, Path, or list of strings or Paths",
    )

    if isinstance(filepaths, list):
        for filepath in filepaths:
            _enforce_type_one_of(
                filepath,
                "filepath",
                (str, Path),
                error_message="'filepaths' argument must be type string, Path, or list of strings or Paths",
            )


def _check_variables_type(variables: dict[str, str]) -> None:
    _enforce_type(
        variables,
        "variables",
        dict,
        error_message="optional 'variables' argument must be a dictionary if entered",
    )


def _fetch_split_sql_behaviour(raw_sql: str, filepath: Path) -> bool:
    split_command = (_extract_instruction(raw_sql, "SPLIT") or "").strip()
    split_command_upper = split_command.upper()
    if not split_command:
        return True

    if split_command.upper() not in ("TRUE", "FALSE"):
        raise ValueError(
            f"Invalid split command: '{split_command}' in file '{filepath}'. Accepts 'TRUE' or 'FALSE'. "
            + f"\nFilepath: '{filepath.absolute()}'"
        )
    else:
        return split_command_upper == "TRUE"
