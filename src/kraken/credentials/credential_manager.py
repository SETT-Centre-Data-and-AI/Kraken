from platform import system as os_system

import keyring
from keyring.errors import PasswordDeleteError

from kraken.credentials.credentials import Credentials
from kraken.credentials.integrity import DEFAULT_USERNAME_TOKEN
from kraken.exceptions import CredentialError
from kraken.support.support import decode, encode


class CredentialManager:
    """Manages the saving and fetching of Kraken connection Credential objects
    from the OS' secret storage (e.g. Windows Credential Manager).

    Raises:
        CredentialError: Raises if a Credential cannot be found
    """

    os: str = os_system()
    credentials: Credentials | None = None

    def __init__(self) -> None:
        pass

    def __repr__(self) -> str:
        if self.credentials:
            return f"{self.__class__.__name__}(Credential Loaded: '{self.credentials.username}@{self.credentials.alias}')"
        else:
            return f"{self.__class__.__name__}(No Credential Loaded)"

    def __patch_credentials(
        self, credentials: Credentials, alias: str, username: str
    ) -> None:
        """Backfills alias and username in a Credential, if missing.
        For backwards compatability with Kraken build < v1.0

        Args:
            credentials (Credentials): Credentials object
            alias (str): Service/database alias
            username (str): Username
        """
        credentials.alias = credentials.alias or alias
        credentials.username = credentials.username or username

    def __save_default_username(self, alias: str, username: str) -> None:
        """Save a username as a default for a given service/database alias

        Args:
            alias (str): Service database/alias
            username (str): Username
        """
        encode(alias=DEFAULT_USERNAME_TOKEN, service=alias, secret=username)

    def get_default_username(self, alias: str) -> str:
        default_username = decode(alias=DEFAULT_USERNAME_TOKEN, service=alias)

        if default_username:
            return default_username
        else:
            raise CredentialError(f"No default username found for '{alias}'")

    def delete_default_username(self, alias: str) -> None:
        """Deletes the default username record for the alias.

        Args:
            alias (str): Service database/alias
        """
        try:
            keyring.delete_password(service_name=alias, username=DEFAULT_USERNAME_TOKEN)
        except PasswordDeleteError as e:
            raise CredentialError(
                "Could not delete default username - "
                + f"'{DEFAULT_USERNAME_TOKEN}@{alias}' not found."
            ) from e

    def fetch_credentials(self, alias: str, username: str | None = None) -> Credentials:
        """Fetches a saved service from OS secret storage. If no username is given, Kraken
        will check whether a default username has been saved for the service alias.

        Args:
            alias (str): Stored service/database alias
            username (str, optional): Stored username. Defaults to None.

        Raises:
            CredentialError: Raises if a Credentials object cannot be found

        Returns:
            Credentials: Credentials object with service connection details
        """
        if not username:
            username = decode(DEFAULT_USERNAME_TOKEN, alias)
            if not username:
                raise CredentialError(
                    f"No username provided, and no default username could be found for service alias '{alias}'"
                )

        credentials_json = decode(username, alias)
        if not credentials_json:
            raise CredentialError(
                f"No credentials found for username '{username}' and service alias '{alias}'"
            )

        credentials = Credentials.from_json(credentials_json)
        self.__patch_credentials(credentials, alias, username)
        self.credentials = credentials
        return self.credentials

    def delete_credentials(self, alias: str, username: str) -> None:
        """Deletes a saved service from OS secret storage, and removes the username
        as the default for the alias, if set. Raises an error if it does not exist.

        Args:
            alias (str): Stored service/database alias
            username (str, optional): Stored username. Defaults to None.

        Raises:
            CredentialError: If credentials cannot be found.

        Returns:
            None: Deletes credentials

        """
        credentials = self.fetch_credentials(alias=alias, username=username)
        keyring.delete_password(
            service_name=credentials.alias, username=credentials.username
        )

        if decode(alias=DEFAULT_USERNAME_TOKEN, service=credentials.alias):
            self.delete_default_username(alias=credentials.alias)

    def save_credentials(
        self,
        alias: str,
        username: str,
        platform: str,
        connection_string: str,
        password: str | None = None,
        default_username: bool = False,
    ) -> Credentials:
        """Takes input connection details to build a Credential, and saves this in the
        OS secret storage. If `default_username = True`, Kraken saves this username as
        the default for this service, allowing it to be retrieved when no username is
        given (e.g. `kraken.fetch_service(alias='my_service')` ).


        Args:
            alias (str): Service/database alias
            username (str): Username
            platform (str): Service platform (e.g. 'oracle' or 'mssql')
            connection_string (str): sqlalchemy/pyodbc connection string
            password (str, optional): User password. Defaults to None.
            default_username (bool, optional): If True, username is used as the default
                for this service. Defaults to False.

        Returns:
            Credentials: Connection details packaged into a Credentials object.
        """
        credentials = Credentials(
            alias=alias,
            username=username,
            password=password,
            platform=platform,
            connection_string=connection_string,
        )

        encode(alias=username, service=alias, secret=credentials.json)

        if default_username:
            self.__save_default_username(alias=alias, username=credentials.username)

        self.credentials = credentials
        return self.credentials
