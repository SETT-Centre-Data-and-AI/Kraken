import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import keyring
import yaml
from keyring.errors import PasswordDeleteError

from kraken.credentials.credential_manager import CredentialManager
from kraken.credentials.credentials import Credentials
from kraken.credentials.integrity import DEFAULT_USERNAME_TOKEN
from kraken.exceptions import CredentialError
from support.integrity import (
    ALIAS,
    CONFIG_MAIN_CONNECTION_TEST,
    CONFIG_TEST_CONNECTIONS,
    DATABASE,
    MAIN_ALIAS,
    PATH_CONFIG_CREDENTIALS,
    SCHEMA,
    TEST_CRED_ALIAS,
    USERNAME,
)

PLEASE_CHECK_MESSAGE = f"Please check: '{PATH_CONFIG_CREDENTIALS}'"


def __get_config_credentials() -> dict:
    """Loads `credentials.yaml` elements"""
    with open(PATH_CONFIG_CREDENTIALS) as file:
        config = yaml.safe_load(file)
        return config


def get_credentials_for_main_connection_test() -> dict:
    """Loads credential details for `main_connection_test` from `credentials.yaml`"""
    config = __get_config_credentials()
    config = config.get(CONFIG_MAIN_CONNECTION_TEST)
    assert config, (
        f"Something's gone wrong - failed to find '{CONFIG_MAIN_CONNECTION_TEST}'."
        + f" Please check: '{PATH_CONFIG_CREDENTIALS}'"
    )
    for element in {ALIAS, USERNAME, DATABASE, SCHEMA}:
        assert config[element], (
            f"Something's gone wrong - failed to find '{element}' under '{CONFIG_MAIN_CONNECTION_TEST}'."
            + f" {PLEASE_CHECK_MESSAGE}"
        )
    return config


def get_credentials_for_connection_test(platform: str) -> list[tuple]:
    """Loads credential details for a platform in `test_connections` from `credentials.yaml`,
    returning a list of tuples as (alias, username) for connection testing. Warns, but does not
    error, if credentials for a platform are not set.
    """
    config = __get_config_credentials()
    config: dict = config.get(CONFIG_TEST_CONNECTIONS)
    assert config, (
        f"Something's gone wrong - failed to find '{CONFIG_TEST_CONNECTIONS}'."
        + f" {PLEASE_CHECK_MESSAGE}"
    )
    config: dict = config.get(platform)
    if not config or len(config) == 0:
        warnings.warn(
            f"WARNING: No test credentials set for {platform}. {PLEASE_CHECK_MESSAGE}",
            stacklevel=1,
        )
        return None

    alias_usernames = []
    for alias, usernames in config.items():
        for username in usernames:
            alias_username = (alias, username)
            alias_usernames.append(alias_username)
    return alias_usernames


def __setup_test_credentials(alias: str, username: str = None) -> Credentials:
    """Fetches credentials for a given alias and username, and saves and returns credentials under a test alias."""
    cred_manager = CredentialManager()
    try:
        credentials = cred_manager.fetch_credentials(alias=alias, username=username)
        credentials.alias = TEST_CRED_ALIAS.format(suffix=alias)
        cred_manager.save_credentials(
            alias=credentials.alias,
            username=credentials.username,
            platform=credentials.platform,
            password=credentials.password,
            connection_string=credentials.connection_string,
            default_username=True,
        )
        return credentials
    except CredentialError as e:
        raise AssertionError(
            f"Something has gone wrong - failed to find existing credentials '{username}@{alias}'."
            + " Please ensure you have these credentials already saved for use in testing"
        ) from e


def __setup_test_credentials_as_main(alias: str, username: str = None) -> Credentials:
    """Fetches credentials for a given alias and username, and saves and returns credentials under a test alias.
    As SQL database flags are fixed within SQL files, these credentials are saved with a fixed alias.
    """
    cred_manager = CredentialManager()
    try:
        credentials = cred_manager.fetch_credentials(alias=alias, username=username)
        credentials.alias = MAIN_ALIAS
        cred_manager.save_credentials(
            alias=credentials.alias,
            username=credentials.username,
            platform=credentials.platform,
            password=credentials.password,
            connection_string=credentials.connection_string,
            default_username=True,
        )
        return credentials
    except CredentialError as e:
        raise AssertionError(
            f"Something has gone wrong - failed to find existing credentials '{username}@{alias}'."
            + " Please ensure you have these credentials already saved for use in testing"
        ) from e


def __remove_test_credentials(alias: str, username: str):
    """Removes test alias and username. Warning: the test alias must be entered as an argument,
    rather than the base/existing alias.
    """
    try:
        keyring.delete_password(service_name=alias, username=username)
    except PasswordDeleteError:
        pass

    try:
        keyring.delete_password(service_name=alias, username=DEFAULT_USERNAME_TOKEN)
    except PasswordDeleteError:
        pass

    # Check is deleted:
    credentials = keyring.get_password(service_name=alias, username=username)
    assert credentials is None, (
        f"Something has gone wrong - failed to delete test credentials '{username}@{alias}'."
        + f" Please check support function: '{Path(__file__).absolute()}'."
    )
    default_credentials = keyring.get_password(
        service_name=alias, username=DEFAULT_USERNAME_TOKEN
    )
    assert default_credentials is None, (
        f"Something has gone wrong - failed to delete default test credentials '{DEFAULT_USERNAME_TOKEN}@{alias}'."
        + f" Please check support function: '{Path(__file__).absolute()}'."
    )


@contextmanager
def setup_test_credentials(
    alias: str, username: str = None
) -> Generator[Credentials, None, None]:
    """Fetches existing credentials, makes and saves a test copy, and then removes the copy once complete or on error.
    Args:
        alias (str): alias for existing credentials to copy.
        username (str, optional): username for existing credentials to copy. Defaults to None.

    Yields:
        Generator[Credentials, None, None]: Credentials object
    """
    credentials = __setup_test_credentials(alias=alias, username=username)
    try:
        yield credentials
    finally:
        __remove_test_credentials(
            alias=credentials.alias, username=credentials.username
        )


@contextmanager
def setup_main_test_credentials() -> Generator[Credentials, None, None]:
    """Fetches existing credentials for the main connection test, makes and saves a test copy,
    and then removes the copy once complete or on error.
    Args:
        alias (str): alias for existing credentials to copy.
        username (str, optional): username for existing credentials to copy. Defaults to None.

    Yields:
        Generator[Credentials, None, None]: Credentials object
    """
    config = get_credentials_for_main_connection_test()
    MAIN_TEST_ALIAS = config[ALIAS]
    MAIN_TEST_USERNAME = config[USERNAME]

    credentials = __setup_test_credentials_as_main(
        alias=MAIN_TEST_ALIAS, username=MAIN_TEST_USERNAME
    )
    try:
        yield credentials
    finally:
        __remove_test_credentials(alias=MAIN_ALIAS, username=credentials.username)
