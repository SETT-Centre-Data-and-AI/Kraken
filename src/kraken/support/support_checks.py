from typing import Any


def _enforce_type(
    variable: Any,
    variable_name: str,
    variable_type: type,
    error_message: str | None = None,
) -> None:
    """Check variable is a particular type.

    Args:
        variable: variable
        variable_name (str): variable name
        variable_type (type): type

    Raises:
        TypeError: errors if variable is not the given type
    """
    error_message = (
        error_message
        if error_message
        else f"Variable '{variable_name}' must be type '{variable_type.__name__}'"
    )
    if not isinstance(variable, variable_type):
        raise TypeError(error_message)


def _enforce_type_one_of(
    variable: Any,
    variable_name: str,
    variable_types: tuple,
    error_message: str | None = None,
) -> None:
    """Check variable is a particular type.

    Args:
        variable: variable
        variable_name (str): variable name
        variable_type (type): type

    Raises:
        TypeError: errors if variable is not the given type
    """
    _enforce_type(variable_types, "variable_type", tuple)

    error_message = (
        error_message
        if error_message
        else (
            f"Variable '{variable_name}' is a '{type(variable).__name__}' type"
            + f", but must be one of '{[v.__name__ for v in variable_types]}'"
        )
    )
    if not isinstance(variable, variable_types):
        raise TypeError(error_message)


def _enforce_in_list(
    value: str, items: list | dict | tuple | set, message: str | None = None
) -> None:
    message = (
        message
        if message
        else f"Entered value '{value}' is not allowed. Allowed: {items}"
    )

    if not isinstance(items, list):
        items = list(items)

    if value not in items:
        raise ValueError(message)
