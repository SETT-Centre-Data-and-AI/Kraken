import sqlalchemy
import pyodbc

### Connection ###
DEFAULT_ARRAYSIZE = 10_000


def _split_pyodbc_connection_string(connection_string: str) -> dict[str, str]:
    """Separates a pyodbc-style connection string into constituent parts and returns in
    a dictionary.

    Args:
        connection_string (str): pyodbc-style connection string

    Returns:
        dict: dictionary of connection detail parts of the connection string
    """
    connection_string_dictionary = {}
    parts = connection_string.split(";")
    for part in parts:
        key_value = part.split("=", 1)
        if len(key_value) == 2:
            key, value = key_value
            connection_string_dictionary[key.strip()] = value.strip()

    return connection_string_dictionary


def _compile_pyodbc_connection_string(
    connection_string_dictionary: dict[str, str],
) -> str:
    """Takes a dictionary of a pyodbc-style connection string's constituent parts, and
    compiles the dictionary into a string.

    Args:
        connection_string_dictionary (dict): dictionary of elements of the connection string

    Returns:
        str: pyodbc-style connection string
    """
    connection_string_parts = []
    for key, value in connection_string_dictionary.items():
        part = f"{key.strip()}={value.strip()}"
        connection_string_parts.append(part)
    return ";".join(connection_string_parts)


def _check_execution_error(error: Exception, platform: str = "") -> str:
    if isinstance(error, (pyodbc.ProgrammingError, sqlalchemy.exc.ProgrammingError)):
        e_lower = error.__str__().lower()
        # mssql DECLARE variable error
        if (
            platform == "mssql"
            and "must declare" in e_lower
            and "variable" in e_lower
        ):
            return (
                "If using DECLARE to set variables in separate queries in MSSQL, "
                + "ensure the `--$Split=False` "
                + "flag is used within the SQL file."
            )
    return str(error)
