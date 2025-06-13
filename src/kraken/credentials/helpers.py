from kraken.credentials.credential_manager import CredentialManager
from kraken.credentials.credentials import Credentials


def fetch_credentials(alias: str, username: str | None = None) -> Credentials:
    """Fetches a saved service from OS secret storage. If no username is given, Kraken
    will check whether a default username has been saved for the service alias.

    Args:
        alias (str): Stored service/database alias
        username (str, optional): Stored username. Defaults to None.

    Returns:
        Credentials: Credentials object with service connection details
    """
    manager = CredentialManager()
    return manager.fetch_credentials(alias=alias, username=username)


def delete_credentials(alias: str, username: str) -> None:
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
    manager = CredentialManager()
    manager.delete_credentials(alias=alias, username=username)
