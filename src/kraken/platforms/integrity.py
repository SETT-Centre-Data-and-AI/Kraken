import importlib
from pathlib import Path

DEFAULT_NAME = "default"
PATH_PLATFORMS = Path(__file__).parent
PATH_PLATFORM_INIT = r"__init__.py"


def _find_platform_path(platform: str, suffix: str | None = None) -> Path | None:
    """Checks existence of platform directory, or files/subfolders within it and returns
    path.

    Args:
        platform (str): platform name
        suffix (str, optional): subfolder or file path suffix. Defaults to None.

    Returns:
        Path: Path to platform
    """
    platform_dir = PATH_PLATFORMS / platform
    if not platform_dir.exists():
        return None

    if not suffix:
        return platform_dir

    filepath = platform_dir / suffix

    if not filepath.exists():
        return None
    else:
        return filepath


def find_initialiser(platform: str) -> Path | None:
    """Finds the directory of a given platform '__init__.py' file (if exists).

    Args:
        platform (str): platform name

    Excepts:
        ValueError: ignores ValueError if '__init__.py' file not found

    Returns:
        Path: Path directory of platform '__init__.py' file (if exists)
    """

    try:
        filepath = _find_platform_path(platform=platform, suffix=PATH_PLATFORM_INIT)
    except ValueError:
        filepath = None
    return filepath


def initialise_platform(platform: str) -> None:
    """Takes a platform and runs imports __init__.py file if it exists.

    Args:
        platform (str): platform name
    """
    init_path = find_initialiser(platform)
    if init_path:
        module = f"kraken.{PATH_PLATFORMS.name}.{platform}"
        importlib.import_module(module)
