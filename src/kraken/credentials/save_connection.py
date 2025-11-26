from kraken.connection.connector import create_connector
from kraken.credentials.credential_manager import CredentialManager
from kraken.credentials.credentials import Credentials
from kraken.credentials.integrity import INTEGRATED_TOKEN
from kraken.exceptions import DatabaseConnectionError
from kraken.support.readout import readout


### Save Connections ###
def save_connection(
    alias: str,
    connection_string: str,
    username: str | None = None,
    password: str | None = None,
    platform: str | None = None,
    default: bool = False,
    autosave: bool = False,
) -> None:
    """
    Save a specific database connection string to credential manager under
    a callable alias and username. Kraken will first attempt a connection
    to the database, and upon failure, request confirmation to save. If
    'default' is set to True, this username will be used as the default for
    the given alias. Saves as:

        {username}@{alias} -> {connection_string}

    Args:
        alias (str): Alias for the database. Connection engines can be created
            using this alias, and can be fed into kraken from SQL files.
        connection_string (str): Database connection string
        username (str, optional): Username. If None, Kraken will save the username
            as "integrated" and later interpret this to be an integrated connection.
            Defaults to None.
        platform (str, optional): Database platform. Affects downstream SQL parsing
            and execution behaviour. Defaults to None.
        default (bool, optional): If True, saves username as default for database
            alias. Defaults to False.
        autosave (bool, optional): If True, Kraken will save the connection regardless
            of connection failure.
    """
    username = username if username else INTEGRATED_TOKEN
    platform = "unknown" if platform is None else platform

    credentials = Credentials(
        alias=alias,
        username=username,
        password=password,
        platform=platform,
        connection_string=connection_string,
    )

    # Test Connection
    readout.print(
        f"Testing connection to {credentials.platform} database '{credentials.alias}' with username '{credentials.username}'... ",
        end="",
    )

    connection_success, error = __test_connection(credentials=credentials)
    abort_message = f"\n -> Aborted credentials save for {alias}"

    if connection_success:
        save_credentials = True

    else:
        readout.warn("error connecting... ", end="")
        if autosave:
            save_input = "y"
        else:
            save_input = input(
                "Error connecting to database. Continue with save (y/n)? ||| ERROR:"
                f" {error}"
            )
        if save_input.lower() == "y":
            save_credentials = True
        elif save_input.lower() in ["n", ""]:
            save_credentials = False
        else:
            readout.warn(f"{abort_message} (Unknown command received: '{save_input}')")
            return

    # Save credentials
    if save_credentials:
        credentials_manager = CredentialManager()
        credentials_manager.save_credentials(
            alias=credentials.alias,
            username=credentials.username,
            platform=credentials.platform,
            connection_string=credentials.connection_string,
            password=credentials.password,
            default_username=default,
        )

        success_message = (
            f"saved credentials{' as default for alias' if default else ''}"
        )
        failure_message = f"{success_message} regardless"
        if connection_success:
            readout.print(success_message)
        else:
            readout.warn(failure_message)
    else:
        readout.warn(abort_message)


### Platform-Specific Saving ###


### Private Functions ###
def __test_connection(
    credentials: Credentials,
) -> tuple[bool, None | DatabaseConnectionError]:

    connector = create_connector(
        alias=credentials.alias, custom_credentials=credentials
    )
    try:
        connector.connect(allow_feedback=False)
        connector.close_connection()
        return (True, None)
    except DatabaseConnectionError as e:
        return (False, e)
