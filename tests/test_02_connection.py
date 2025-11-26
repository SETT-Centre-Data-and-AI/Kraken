import keyring
import pytest
from support import integrity  # noqa
from support.config import config

from kraken.connection.connector import create_connector
from kraken.credentials.integrity import DEFAULT_USERNAME_TOKEN
from kraken.exceptions import DatabaseConnectionError

# Constants
SILLY_DATABASE = "a_silly_database"
main_test = config.main_test
secondary_tests = config.secondary_tests


# Helpers
def __no_multi_db() -> bool:
    if main_test.multi_db_support:
        return False
    else:
        return True


def __platform_missing(platform: str) -> bool:
    if config.has_test_connection(platform):
        return False
    else:
        return True


def __reason(platform: str) -> str:
    return (
        f"Platform '{platform}' is not set up under '{integrity.CONFIG_TEST_CONNECTIONS}' "
        + f"in '{integrity.PATH_CONFIG_CREDENTIALS}'"
    )


### ====================== ###
### ---------TESTS---------###
### ====================== ###


### Test all config credentials can be sourced
def test_config_credentials_exist() -> None:
    errors = []

    # Check main credentials
    main_test = config.main_test
    for token in [main_test.username, DEFAULT_USERNAME_TOKEN]:
        if not keyring.get_password(main_test.alias, token):
            errors.append(("Main Test", main_test.alias, token))

    # Check secondary credentials
    secondary_tests = config.secondary_tests
    for _platform, tests in secondary_tests.items():
        for test in tests:
            if not keyring.get_password(test.alias, test.username):
                errors.append(("Secondary Test", test.alias, test.username))

    missing = (
        " - "
        + "\n - ".join(
            f"{test_type}: '{username}@{alias}'"
            for test_type, alias, username in errors
        )
        if errors
        else ""
    )
    assert len(errors) == 0, f"Source credentials missing: {missing}"


### Test main test saved with default username for ribosome test
def test_config_main_credentials_has_default() -> None:
    main_test = config.main_test
    assert keyring.get_password(main_test.alias, DEFAULT_USERNAME_TOKEN), (
        "Main test credentials not saved with default username, "
        "which is required for a ribosome test. Run `kraken.save_connection_XXX()` "
        "with `default=True` for your desired main test"
    )


### Test that we can connect
def test_connection() -> None:
    credentials = main_test.setup_test_credentials()
    connector = create_connector(alias=credentials.alias, username=credentials.username)
    connector.connect()


### Test that we can connect to the main connection testing database
def test_connection_database_exists() -> None:
    credentials = main_test.setup_test_credentials()
    connector = create_connector(alias=credentials.alias, username=credentials.username)
    if main_test.multi_db_support:
        connector.switch_database(main_test.database)


### Test that database connection failures are caught
@pytest.mark.skipif(
    __no_multi_db(), reason="Main connection does not support multiple databases"
)
def test_failure_connection() -> None:
    credentials = main_test.setup_test_credentials()
    connector = create_connector(alias=credentials.alias, username=credentials.username)

    connector.switch_database(SILLY_DATABASE)
    with pytest.raises(DatabaseConnectionError):
        connector.connect()


def __test_connections(platform: str) -> None:
    tests = secondary_tests[platform]

    for test in tests:
        credentials = test.setup_test_credentials()
        connector = create_connector(alias=test.alias, custom_credentials=credentials)
        print(f"TESTING CONNECTION with {credentials}")
        connector.connect()
        connector.close_connection()


### Test Oracle Connections ###
@pytest.mark.skipif(__platform_missing("oracle"), reason=__reason("oracle"))
def test_oracle_connection() -> None:
    __test_connections(platform="oracle")


### Test Mssql Connections ###
@pytest.mark.skipif(__platform_missing("mssql"), reason=__reason("mssql"))
def test_mssql_connection() -> None:
    __test_connections(platform="mssql")


### Test Informix Connections ###
@pytest.mark.skipif(__platform_missing("informix"), reason=__reason("informix"))
def test_informix_connection() -> None:
    __test_connections(platform="informix")


### Test Cache Connections ###
@pytest.mark.skipif(__platform_missing("cache"), reason=__reason("cache"))
def test_cache_connection() -> None:
    __test_connections(platform="cache")


### Test Iris Connections ###
@pytest.mark.skipif(__platform_missing("iris"), reason=__reason("iris"))
def test_iris_connection() -> None:
    __test_connections(platform="iris")


### Test Postgresql Connections ###
@pytest.mark.skipif(__platform_missing("postgresql"), reason=__reason("postgresql"))
def test_postgresql_connection() -> None:
    __test_connections(platform="postgresql")


### Test mariadb Connections ###
@pytest.mark.skipif(__platform_missing("mariadb"), reason=__reason("mariadb"))
def test_mariadb_connection() -> None:
    __test_connections(platform="mariadb")


if __name__ == "__main__":
    pytest.main([__file__])
