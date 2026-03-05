import re
import time
from datetime import datetime
from functools import wraps
from math import trunc
from pathlib import Path
from typing import Callable, ParamSpec, TypeVar

from IPython.core.getipython import get_ipython
from keyring import get_password, set_password
from pandas import DataFrame
from pandas.api.types import is_numeric_dtype

# from kraken.classes.pack_lists import Result
from kraken.classes.data_types import Runtime
from kraken.classes.pack_lists import QueryList, ResultList
from kraken.support.readout import readout

KRAKEN_DEFAULT = "KRAKEN_DEFAULT"
TOKEN_DATABASE = "DATABASE"
TOKEN_ORACLE_CLIENT = "ORACLE_CLIENT"

P = ParamSpec("P")
R = TypeVar("R")


### Encode Credentials ###
def encode(alias: str, service: str, secret: str) -> None:
    """
    Saves secret in OS's credential manager as:
        {alias}@{service} = {secret}

    Args:
        -   alias (str):    username or parameter
        -   service (str):  domain or database alias
        -   secret (str):   secret or password
    """

    set_password(service, alias, secret)


### Decode Credentials ###
def decode(alias: str, service: str) -> str | None:
    """
    Returns secret from OS's credential manager, stored as:
        {alias}@{service} = {secret}

    Args:
        -   alias (str):    username or parameter
        -   service (str):  domain or database alias

    Returns:
        -   str: secret
    """

    return get_password(service, alias)


### Setup Kraken Defaults ###
def __save_kraken_default(param: str, input_prompt: str) -> str | None:
    """
    Private function to save kraken defaults as:
        {parameter}@KRAKEN_DEFAULT -> {default_parameter}
    """

    input_value = input(input_prompt)

    if input_value == "":
        return None

    encode(param, KRAKEN_DEFAULT, input_value)
    return input_value


def set_default_alias(alias: str) -> None:
    """Saves alias as default. If a SQL file does not contain a `--$database`
    flag, Kraken will execute against this default database.

    Args:
        alias (str): Database alias to save as default.
    """
    encode(TOKEN_DATABASE, KRAKEN_DEFAULT, alias)
    print(f"'{alias}' saved as default database")


def set_kraken_defaults() -> None:
    """
    -   Run setup to save default Kraken parameters.
    -   Kraken will prompt for input for each parameter.
    -   Empty inputs will be ignored.
    """

    default_messages = {
        TOKEN_DATABASE: (
            "Please enter the alias of your default database, e.g. EPR:",
            "default database",
        ),
        TOKEN_ORACLE_CLIENT: (
            r"Please enter path of your Oracle .dll files, e.g. c:\oracle:",
            "default filepath for oracle client",
        ),
    }

    for param, (input_prompt, output_message) in default_messages.items():
        input_value = __save_kraken_default(param, input_prompt)
        if input_value is not None:
            print(f"{input_value} saved as {output_message}")
        else:
            print(f"Empty input, therefore no {output_message} saved/overwritten")


### Runtime Wrapper ###
def print_runtime(
    message: str = "Runtime: {time:.4f} seconds",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            runtime = end_time - start_time
            print(message.format(time=runtime))
            return result

        return wrapper

    return decorator


### Check Path Filetype ###
def _check_filetype(filepath: str | Path, extension: str | list[str]) -> bool:
    extensions = [extension] if isinstance(extension, str) else extension
    extensions = [f".{ext}" if ext[0] != "." else ext for ext in extensions]
    filepath = Path(filepath)
    return any(filepath.suffix.lower() == extension.lower() for extension in extensions)


### Calculate Runtime & Message ###
def calculate_runtime(start: datetime, stop: datetime | None = None) -> Runtime:
    """Summary:
        -   Takes two datetimes, and calculates the difference.
        -   Returns a message and raw timedelta as a named tuple, callable with .message or .delta

    Args:
        -   start (datetime):   Start time for calculation.
        -   stop (datetime):    Stop time for calculation. Defaults to now if not entered.

    Returns:
        tuple[str, timedelta]: Returns tuple, callable with .message (string) or .delta (raw timedelta)
    """
    stop = stop if stop else datetime.now()
    runtime = stop - start
    total_seconds = runtime.total_seconds()
    hours = trunc(total_seconds / 3600)
    minutes = trunc((total_seconds - (hours * 3600)) / 60)
    seconds = trunc((total_seconds - (hours * 3600) - (minutes * 60)) * 10) / 10
    runtime_message = (
        (f"{hours}h " if hours else "")
        + (f"{minutes}m " if minutes else "")
        + (f"{seconds}s" if not hours and not minutes else f"{trunc(seconds)}s")
    )

    return Runtime(message=runtime_message, timedelta=runtime)


### Load Filepaths ###
def _load_filepaths(
    filepaths: str | list[str] | Path | list[Path], extensions: str | list[str]
) -> list[Path]:
    filepath_list = []
    warning_list = []
    if isinstance(filepaths, (str, Path)):
        filepaths = [filepaths]  # type: ignore[assignment]
    fps = [Path(fp) for fp in filepaths]  # type: ignore[union-attr]

    for filepath in fps:
        # Process filepath if file
        if filepath.is_file():
            if not _check_filetype(filepath, extensions):
                raise ValueError(
                    f"Entered filepath not a {extensions} file: {filepath}"
                )
            else:
                filepath_list.append(Path(filepath))

        # Process filepath if directory
        elif filepath.is_dir():
            number_of_files = 0
            for file in sorted(filepath.iterdir()):
                if _check_filetype(file, extensions):
                    number_of_files += 1
                    filepath_list.append(file)

            if number_of_files == 0:
                warning_list.append(Path(filepath))

        else:
            raise ValueError(
                f"Entered filepath not detected as file or directory: {filepath}"
            )

    if not filepath_list:
        raise ValueError(f"No {extensions} files detected or extracted")

    if warning_list:
        readout.warn(f"WARNING - No {extensions} files detected in:")
        for filepath in warning_list:
            readout.print(f"(' -> '){filepath}")
        print("")

    return filepath_list


### Extract Comments From SQL ###
def _extract_comments(sql: str) -> list[str]:
    line_comments = r"--.{,}?\n"
    block_comments = r"/\*.+?\*/"
    return re.findall(f"{line_comments}|{block_comments}", sql + "\n", flags=re.DOTALL)


### Extract Instructions ###
def __match_instruction_comments(sql: str, instruction: str) -> list[str]:
    """Return all comments matching the given instruction name."""
    search = instruction if instruction.startswith("$") else f"${instruction}"
    pattern = re.compile(re.escape(search), flags=re.IGNORECASE)
    return [comment for comment in _extract_comments(sql) if pattern.search(comment)]


def _extract_instruction(sql: str, instruction: str) -> str | None:
    """Extract the value assigned to an instruction like `$instruction=value`."""
    comments = __match_instruction_comments(sql, instruction)
    values = [comment.partition("=")[-1].strip() for comment in comments]
    try:
        if not values:
            return None
        return values[-1]
    except IndexError as e:
        raise IndexError("Have you forgotten to add '=' to the $variable?") from e


def _count_instructions(sql: str, instruction: str) -> int:
    """Count how many comments match the instruction name."""
    return len(__match_instruction_comments(sql, instruction))


### Credential Checker ###
def _check_credentials(
    database_alias: str, username: str | None = None
) -> tuple[str, str, str]:
    DEFAULT_USERNAME = "DEFAULT_USERNAME"

    if username is not None:
        mode = "input"
    else:
        mode = "default"
        username = decode(DEFAULT_USERNAME, database_alias)

    if username is None:
        raise ValueError(
            f"No username provided, and no default username set for database '{database_alias}'. "
            + "Run 'kraken.save_connection_xxx' to save an alias, with default=True to save as the "
            + "default username for this connection."
        )

    connection_json = decode(username, database_alias)

    if connection_json is None:
        raise ValueError(f"No connection details found for {username}@{database_alias}")
    print(f"Database Alias: {database_alias}")
    print(f"Username: \t{username} (as {mode})")
    print(
        "-> Connection Details Retrieved"
        if connection_json is not None
        else "No Connection Details Found"
    )

    return (database_alias, username, connection_json)


def is_notebook() -> bool:
    """https://stackoverflow.com/a/39662359"""
    try:
        shell: str = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False


### Set Engine Path Convenience ###
def get_engine_path(filepath: str = "") -> str:
    """Convenience function to return the directory of the current file. Can be left blank for a Jupyter Notebook, otherwise enter "get_engine_path(__file__)".

    Args:
        filepath (optional): Can be left blank for a Jupyter Notebook, otherwise enter __file__. Defaults to None.

    Returns:
        str: Filepath of current file as a string.
    """
    absolute = Path(filepath).absolute()
    return f"{str(absolute.parent)}\\" if absolute.is_file() else f"{str(absolute)}\\"


def _prepare_sql_snippet(sql: str, max_characters: int = 100) -> str:
    snippet = sql + "\n"

    for comment in _extract_comments(snippet):
        snippet = snippet.replace(comment, "")

    snippet = re.sub(" +", " ", snippet.replace("\n", " ").replace("\t", " "))
    if len(snippet) > max_characters:
        snippet = f"{snippet[:max_characters]}..."
    snippet = snippet.strip()
    return snippet


### Helper: Check Query list for duplicate df_names ###
def _check_df_name_duplicates(df_name_list: QueryList | ResultList) -> None:
    df_names = [item.df_name for item in df_name_list]
    if duplicates := {df_name for df_name in df_names if df_names.count(df_name) > 1}:
        s = "" if len(duplicates) == 1 else "s"
        readout.warn(
            f"WARNING: {len(duplicates)} duplicate dataframe name{s} detected. Recommend amending name{s} to avoid unexpected behaviour downstream:"
        )
        for dup in duplicates:
            readout.warn(f" -> {dup}")

        readout.print("\n", end="")


def datestamp(
    sep: str = "",
    full_year: bool = True,
    iso_format: bool = False,
    iso_colon_replace: str | None = None,
    iso_timespec: str = "seconds",
) -> str:
    """Returns current datestamp in a particular format (YYMMDD, YYYYMMDD, or ISO)

    Args:
        sep (str, optional): specified separator. Defaults to "".
        full_year (bool, optional): returns year with all digits. Defaults to True.
        iso_format (bool, optional): returns ISO timestamp. Defaults to False.
        replace_iso_colon (str, optional): when using iso_format, will replace colons in timestamp with provided string. Defaults to None (no replace).
        iso_timespec (str, optional): optional terms for the iso_format. Valid options are 'auto', 'hours', 'minutes', 'seconds', 'milliseconds' and 'microseconds'.

    Returns:
        str: datestamp
    """
    iso_datestamp = datetime.now().isoformat(timespec=iso_timespec)
    if iso_colon_replace is not None:
        iso_datestamp = iso_datestamp.replace(":", iso_colon_replace)
        if not full_year:
            iso_datestamp = iso_datestamp[2:]

    datestamp = (
        iso_datestamp
        if iso_format
        else (
            datetime.now().strftime(f"%Y{sep}%m{sep}%d")
            if full_year
            else datetime.now().strftime(f"%y{sep}%m{sep}%d")
        )
    )

    return datestamp


def timestamp(time_sep: str = "-", timespec: str = "seconds") -> str:
    """Returns current ISO timestamp in format YYYY-MM-DDTHH-MM-SS by default. Amend time_sep to change time separator."""
    return datetime.now().isoformat(timespec=timespec).replace(":", time_sep)


def abbreviate_number(
    count: int, decimals_from: str = "m", right_adjust: int = 6
) -> str:
    """Convert a count to a fixed-width human-readable format using dynamic suffixes,
    including decimals starting from the specified suffix and standardises alignment."""
    suffixes = ["", "k", "m", "b", "t", "q", "qi", "sx", "sp", "o", "n", "d"]
    if decimals_from not in suffixes:
        raise ValueError(
            f"'decimals_from' argument value '{decimals_from}' not in suffix list. Allowed: {suffixes}"
        )
    index = 0
    while count >= 1000 and index < len(suffixes) - 1:
        count /= 1000  # type: ignore[assignment]
        index += 1

    show_decimal = index >= suffixes.index(decimals_from)

    if show_decimal:
        formatted = f"{count:.1f}"
    else:
        formatted = f"{int(count)}"

    return f"{formatted}{suffixes[index]}".rjust(right_adjust)


def list_as_bullets(
    list: list,
    bullet: str = " - ",
    quote_enclose: bool = True,
    begin_on_new_line: bool = True,
) -> str:
    """Converts elements from a list into a bulleted string"""
    list = [f"'{element}'" for element in list] if quote_enclose else list
    first_bullet = f"\n{bullet}" if begin_on_new_line else bullet
    new_bullet = f"\n{bullet}"
    return f"{first_bullet}{new_bullet.join(list)}"


### Generate Where Clause ###
def generate_where_clause(
    df: DataFrame,
    where: str,
    batch_size: int = 1000,
    separator: str = "OR",
    in_mode: bool = False,
) -> list[str]:
    """Takes a template SQL WHERE clause with reference to column names,
    and loops over rows in a DataFrame to generate SQL referring to column names.

    Args:
        df (DataFrame): Input DataFrame
        where (str): Template clause, referring to column names e.g. "PATIENT_ID = {id} AND RESULT_DATE BETWEEN {start_date} AND {end_date}".
        batch_size (int, optional): Number of elements to return in each batch. Defaults to 1000.
        separator (str, optional): Text to separate each clause. Defaults to "OR".
        in_mode (bool, optional): If True, will extract unique elements from a column for us in 'IN' statements e.g. "PATIENT_ID IN ({id})",
            rather than copying the template for each DataFrame row. If True, can only support a single referenced column. Defaults to False.

    Raises:
        ValueError: If column not found in DataFrame.

    Returns:
        list[str]: List of clauses, batched as per the batch_size.
    """
    result = []
    if in_mode:
        placeholders = re.findall(r"{(\w+)}", where)
        if len(placeholders) != 1:
            raise ValueError(
                "When using in_mode, only one column can be referenced. "
                "To produce multiple IN statements, run the function separately for each column."
            )

        column: str = placeholders[0]
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in DataFrame.")

        unique_values = df[column].dropna().unique()
        quote_values = not is_numeric_dtype(df[column])

        for start_idx in range(0, len(unique_values), batch_size):
            batch = unique_values[start_idx : start_idx + batch_size]
            formatted_values = [
                f"'{val}'" if quote_values else str(val) for val in batch
            ]

            value_clause = "\n    " + "\n ,  ".join(formatted_values)
            clause = where.format(**{column: value_clause})
            result.append(f"({clause})")

    else:
        for start_idx in range(0, len(df), batch_size):
            batch = df.iloc[start_idx : start_idx + batch_size]  # type: ignore
            batch_conditions = []

            for _, row in batch.iterrows():  # type: ignore
                condition = where.format(**row.to_dict())
                batch_conditions.append(f"({condition})")

            result.append(
                "("
                + " " * (len(separator))
                + f"\n{separator} ".join(batch_conditions)
                + ")"
            )

    return result
