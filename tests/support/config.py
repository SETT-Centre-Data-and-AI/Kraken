import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import keyring
import yaml  # type: ignore
from keyring.errors import PasswordDeleteError

from kraken.connection.connector import Connector, create_connector
from kraken.credentials.credential_manager import CredentialManager
from kraken.credentials.credentials import Credentials
from kraken.credentials.helpers import fetch_credentials
from kraken.credentials.integrity import DEFAULT_USERNAME_TOKEN
from kraken.credentials.save_convenience import save_connection_DuckDB
from kraken.exceptions import CredentialError
from kraken.platforms.config import PlatformConfig
from support.integrity import (
    PATH_CONFIG,
    PATH_CONFIG_CREDENTIALS,
    PATH_CONFIG_TEMPLATE_CREDENTIALS,
    PATH_OUTPUTS,
)

# YAML Tokens
ALIAS = "alias"
USERNAME = "username"
DATABASE = "database"
SCHEMA = "schema"
CONFIG_MAIN_CONNECTION_TEST = "main_connection_test"
CONFIG_TEST_CONNECTIONS = "test_connections"

# Aliases
MAIN_TEST_ALIAS = "KRAKEN_TEST_MAIN"
OTHER_TEST_ALIAS = "KRAKEN_TEST_{suffix}"

# Fallback DuckDB testing database
TEMP_USERNAME: str = "integrated"
TEMP_DATABASE: str = str(":memory:")
TEMP_SCHEMA: str = "sandbox"


# Helpers
def _ensure_output_folder_exists() -> None:
    # Ensure output folder exists
    PATH_OUTPUTS.mkdir(parents=True, exist_ok=True)


def _ensure_config_exists() -> None:
    if not PATH_CONFIG_CREDENTIALS.exists():
        PATH_CONFIG.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PATH_CONFIG_TEMPLATE_CREDENTIALS, PATH_CONFIG_CREDENTIALS)


def _add_temp_credentials(
    credentials: Credentials, main_test: bool = True, default_username: bool = True
) -> Credentials:
    credentials.alias = (
        MAIN_TEST_ALIAS
        if main_test
        else OTHER_TEST_ALIAS.format(suffix=credentials.alias)
    )
    cred_manager = CredentialManager()
    cred_manager.save_credentials(
        alias=credentials.alias,
        username=credentials.username,
        platform=credentials.platform,
        connection_string=credentials.connection_string,
        password=credentials.password,
        default_username=default_username,
    )
    return credentials


def _remove_test_credentials(alias: str, username: str) -> None:
    for token in [username, DEFAULT_USERNAME_TOKEN]:
        try:
            keyring.delete_password(service_name=alias, username=token)
        except PasswordDeleteError:
            pass


# Config Class
@dataclass
class MainTest:
    """Configuration for the primary test connection supplied in `credentials.yaml`,
    falling back to an in-memory DuckDB database if no test alias is provided.
    Provides methods for setting up temporary credentials and connections."""

    # Magic
    def __init__(
        self,
        alias: str | None = None,
        username: str | None = None,
        database: str | None = None,
        schema: str | None = None,
    ):
        self.fallback: bool = False if alias else True
        self.alias: str = MAIN_TEST_ALIAS if self.fallback else alias  # type: ignore
        self.username: str = TEMP_USERNAME if self.fallback else username  # type: ignore
        self.database: str = TEMP_DATABASE if self.fallback else database  # type: ignore
        self.schema: str = TEMP_SCHEMA if self.fallback else schema  # type: ignore

    def __repr__(self) -> str:
        return (
            f"MainPlatform(alias='{self.alias}', "
            + f"username='{self.username}', "
            + f"database='{self.database}', "
            + f"schema='{self.schema})'"
        )

    # Properties
    @property
    def config(self) -> PlatformConfig:
        platform = self.__get_credentials().platform
        return PlatformConfig(platform=platform)

    @property
    def multi_db_support(self) -> bool:
        return self.config.multiple_db_support

    # Functions
    def __get_credentials(self) -> Credentials:
        """Fetches original template credentials as provided in
        `credentials.yaml`"""
        return fetch_credentials(alias=self.alias, username=self.username)

    def setup_test_credentials(self) -> Credentials:
        """Sets up credentials for the main testing connection. This
        uses the details provided in `credentials.yaml` to fetch the credentials,
        and resave as testing credentials. These are not automatically removed,
        preventing testing race conditions. Use TestConfig().cleanup() once all
        tests are complete to remove testing credentials.

        If testing credentials are not provided, an in-memory DuckDB fallback
        will be used. Username is always saved as default to enable ribosome
        testing.

        Returns:
            Credentials: Main test Kraken Credentials object.
        """
        credentials = self.__get_credentials()
        credentials = _add_temp_credentials(
            credentials, main_test=True, default_username=True
        )

        return credentials

    def get_connector(
        self, autocommit: bool = True, autoclose: bool = True
    ) -> Connector:
        """Returns a Kraken Connector object for the main testing connection as
        per details provided in `credentials.yaml`, or DuckDB as a fallback once.
        This uses temp credentials, which are removed automatically once the
        connector is returned.

        To persist credentials for a longer period, use:
        ```python
        with main.setup_temp_credentials() as credentials:
            connector = create_connector(
                alias=credentials.alias,
                username=credentials.username
            )
        ```

        Returns:
            Connector: Connector object for main testing connection.
        """
        credentials = self.setup_test_credentials()
        connector = create_connector(
            alias=credentials.alias,
            username=credentials.username,
            autocommit=autocommit,
            autoclose=autoclose,
        )

        if self.multi_db_support:
            connector.switch_database(self.database)
        return connector


class SecondaryTest:
    """Configuration for an optional secondary test connection supplied
    in `credentials.yaml`."""

    def __init__(self, alias: str, username: str, platform: str):
        self.alias = alias
        self.username = username
        self.platform = platform

    def __repr__(self) -> str:
        return (
            f"Platform(alias='{self.alias}', "
            + f"username='{self.username}', "
            + f"platform='{self.platform}')"
        )

    @property
    def config(self) -> PlatformConfig:
        return PlatformConfig(platform=self.platform)

    @property
    def multi_db_support(self) -> bool:
        return self.config.multiple_db_support

    def __get_credentials(self) -> Credentials:
        """Fetches original template credentials as provided in
        `credentials.yaml`"""
        return fetch_credentials(alias=self.alias, username=self.username)

    def setup_test_credentials(self) -> Credentials:
        """Sets up credentials for the secondary testing connection. This
        uses the details provided in `credentials.yaml` to fetch the credentials,
        and resave as testing credentials. These are not automatically removed,
        preventing testing race conditions. Use TestConfig().cleanup() once all
        tests are complete to remove testing credentials.

        Username is never saved as default to prevent race test interference.

        Returns:
            Credentials: Secondary test Kraken Credentials object.
        """
        credentials = self.__get_credentials()
        credentials = _add_temp_credentials(
            credentials, main_test=False, default_username=False
        )
        return credentials

    def get_connector(self) -> Connector:
        """Returns a Kraken Connector object for this secondary testing connection as
        per details provided in `credentials.yaml`. This uses temp credentials, which
        are instantiated and removed automatically once the connector is returned.

        To persist credentials for a longer period, use:
        ```python
        with main.setup_temp_credentials() as credentials:
            connector = create_connector(
                alias=credentials.alias,
                username=credentials.username
            )
        ```

        Returns:
            Connector: Connector object for secondary testing connection.
        """
        credentials = self.setup_test_credentials()
        connector = create_connector(
            alias=credentials.alias, username=credentials.username
        )
        return connector


class TestConfig:
    """Configuration for all testing connections provided in `credentials.yaml`.
    Test configurations stored under main_test and secondary_tests provide functions
    to return credentials and connectors, while tweaking credential aliases to temporary
    copies and removing them automatically when returned or `with` blocks are exited."""

    def __init__(self) -> None:
        _ensure_config_exists()
        _ensure_output_folder_exists()

        # Import credentials.yaml
        with open(PATH_CONFIG_CREDENTIALS) as file:
            config = yaml.safe_load(file)
            main_test: dict[str, str] = config[CONFIG_MAIN_CONNECTION_TEST]
            secondary_tests: dict[str, dict[str, list[str]]] = config[
                CONFIG_TEST_CONNECTIONS
            ]

        # Set main connection
        self.main_test: MainTest = MainTest(
            alias=main_test[ALIAS],
            username=main_test[USERNAME],
            database=main_test[DATABASE],
            schema=main_test[SCHEMA],
        )

        # set test connections
        self.secondary_tests: dict[str, list[SecondaryTest]] = {}
        for platform, credentials in secondary_tests.items():
            if credentials:
                for alias, usernames in credentials.items():
                    for username in usernames:
                        if alias and username:
                            self.secondary_tests.setdefault(platform, []).append(
                                SecondaryTest(
                                    alias=alias, username=username, platform=platform
                                )
                            )

        # Save the fallback database
        if self.main_test.fallback:
            manager = CredentialManager()
            try:
                manager.fetch_credentials(alias=MAIN_TEST_ALIAS, username=TEMP_USERNAME)
            except CredentialError:
                save_connection_DuckDB(alias=MAIN_TEST_ALIAS, database=TEMP_DATABASE)

    def __repr__(self) -> str:
        return (
            f"TestConfig(main_connection={self.main_test}, "
            + f"test_connections={self.secondary_tests})"
        )

    def has_test_connection(self, platform: str) -> bool:
        return platform in self.secondary_tests

    @contextmanager
    def setup_test_output_subdir(self, name: str) -> Iterator[Path]:
        root = PATH_OUTPUTS
        subdir = root / f"outputs_{name}"

        if subdir.exists():
            shutil.rmtree(subdir)

        subdir.mkdir(parents=True, exist_ok=True)
        try:
            yield subdir

        finally:
            shutil.rmtree(subdir)

    def cleanup(self) -> None:
        # remove main test credentials
        _remove_test_credentials(
            alias=MAIN_TEST_ALIAS, username=self.main_test.username
        )

        # remove secondary test credentials
        for tests in self.secondary_tests.values():
            for test in tests:
                alias = OTHER_TEST_ALIAS.format(suffix=test.alias)
                username = test.username
                _remove_test_credentials(alias=alias, username=username)


config = TestConfig()
