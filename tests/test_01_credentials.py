import json
from contextlib import contextmanager
from typing import Iterator

import keyring
import pytest
from keyring.errors import PasswordDeleteError

from kraken.credentials.credential_manager import CredentialManager
from kraken.credentials.credentials import Credentials
from kraken.credentials.integrity import (
    ALIAS,
    CONNECTION_STRING,
    DEFAULT_USERNAME_TOKEN,
    PASSWORD,
    PLATFORM,
    USERNAME,
)
from kraken.exceptions import CredentialError

# Constants
TEST_USERNAME = "KRAKEN_TEST_USERNAME"
TEST_ALIAS = "KRAKEN_TEST_CREDENTIALS"
TEST_PLATFORM = "a_test_platform"
TEST_CONNECTION_STRING = "a_connection_string"
TEST_PASSWORD = "a_test_password"

TEST_SILLY_USERNAME = "KRAKEN_TEST_SILLY_USERNAME"
TEST_SILLY_ALIAS = "KRAKEN_TEST_SILLY_ALIAS"


# Helpers
@contextmanager
def cleanup() -> Iterator[None]:
    try:
        yield
    finally:
        for token in (TEST_USERNAME, DEFAULT_USERNAME_TOKEN):
            try:
                keyring.delete_password(service_name=TEST_ALIAS, username=token)
            except PasswordDeleteError:
                pass


### ====================== ###
### ---------TESTS---------###
### ====================== ###


### Test that credentials are processed into json
def test_credentials_json_creation() -> None:
    credentials = Credentials(
        alias=TEST_ALIAS,
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        platform=TEST_PLATFORM,
        connection_string=TEST_CONNECTION_STRING,
    )

    # Check json creation
    assert credentials.json, "Credentials object did not create json"

    # Check json matches
    assert json.loads(credentials.json) == {
        ALIAS: TEST_ALIAS,
        USERNAME: TEST_USERNAME,
        PASSWORD: TEST_PASSWORD,
        PLATFORM: TEST_PLATFORM,
        CONNECTION_STRING: TEST_CONNECTION_STRING,
    }, "Credentials json does not match"


### Test that credentials can be saved
def test_save_credentials() -> None:
    credential_manager = CredentialManager()

    # Save credentials
    with cleanup():
        credential_manager.save_credentials(
            alias=TEST_ALIAS,
            username=TEST_USERNAME,
            platform=TEST_PLATFORM,
            connection_string=TEST_CONNECTION_STRING,
            password=TEST_PASSWORD,
            default_username=True,
        )


### Test that credentials can be fetched and match
def test_fetch_credentials() -> None:
    credential_manager = CredentialManager()

    # Save credentials
    with cleanup():
        credential_manager.save_credentials(
            alias=TEST_ALIAS,
            username=TEST_USERNAME,
            platform=TEST_PLATFORM,
            connection_string=TEST_CONNECTION_STRING,
            password=TEST_PASSWORD,
            default_username=True,
        )

        # Fetch credentials
        credentials = credential_manager.fetch_credentials(TEST_ALIAS, TEST_USERNAME)

        # Check credentials
        assert isinstance(
            credentials, Credentials
        ), "returned credentials is not a Credentials object"
        assert credentials.alias == TEST_ALIAS, "Alias mismatch"
        assert credentials.username == TEST_USERNAME, "Username mismatch"
        assert credentials.platform == TEST_PLATFORM, "Platform mismatch"
        assert (
            credentials.connection_string == TEST_CONNECTION_STRING
        ), "Connection string mismatch"
        assert credentials.password == TEST_PASSWORD, "Password mismatch"


### Test that default credentials can be fetched without a username
def test_fetch_credentials_when_default() -> None:
    credential_manager = CredentialManager()

    # Save credentials
    with cleanup():
        credential_manager.save_credentials(
            alias=TEST_ALIAS,
            username=TEST_USERNAME,
            platform=TEST_PLATFORM,
            connection_string=TEST_CONNECTION_STRING,
            password=TEST_PASSWORD,
            default_username=True,
        )

        # Fetch credentials with no username
        credentials = credential_manager.fetch_credentials(TEST_ALIAS, username=None)

        # Check credentials
        assert isinstance(
            credentials, Credentials
        ), "returned credentials is not a Credentials object"
        assert credentials.alias == TEST_ALIAS, "Alias mismatch"
        assert credentials.username == TEST_USERNAME, "Username mismatch"
        assert credentials.platform == TEST_PLATFORM, "Platform mismatch"
        assert (
            credentials.connection_string == TEST_CONNECTION_STRING
        ), "Connection string mismatch"
        assert credentials.password == TEST_PASSWORD, "Password mismatch"


### Test that credentials cannot be fetched if they don't exist
def test_failure_fetch_credentials_not_exist() -> None:
    credential_manager = CredentialManager()

    # Try to fetch silly credentials
    with pytest.raises(CredentialError):
        credential_manager.fetch_credentials(
            alias=TEST_SILLY_ALIAS, username=TEST_SILLY_USERNAME
        )


### Test that default credentials cannot be fetched without a username
def test_failure_fetch_credentials_no_default() -> None:
    credential_manager = CredentialManager()

    # Save credentials
    with cleanup():
        credential_manager.save_credentials(
            alias=TEST_ALIAS,
            username=TEST_USERNAME,
            platform=TEST_PLATFORM,
            connection_string=TEST_CONNECTION_STRING,
            password=TEST_PASSWORD,
            default_username=False,
        )

        # Fetch credentials with username
        credential_manager.fetch_credentials(alias=TEST_ALIAS, username=TEST_USERNAME)

        # Try to fetch without username
        with pytest.raises(CredentialError):
            credential_manager.fetch_credentials(alias=TEST_ALIAS, username=None)


if __name__ == "__main__":
    pytest.main([__file__])
    cleanup()
