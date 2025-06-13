import pytest
from support import integrity  # noqa
from support.credentials import (  # noqa
    get_credentials_for_connection_test,
    get_credentials_for_main_connection_test,
    setup_test_credentials,
)

from kraken.connection.connector import create_connector
from kraken.exceptions import DatabaseConnectionError

config = get_credentials_for_main_connection_test()
SILLY_DATABASE = "a_silly_database"
MAIN_TEST_ALIAS = config[integrity.ALIAS]
MAIN_TEST_USERNAME = config[integrity.USERNAME]
MAIN_TEST_DATABASE = config[integrity.DATABASE]


### Test that we can connect
def test_connection():
    with setup_test_credentials(
        alias=MAIN_TEST_ALIAS, username=MAIN_TEST_USERNAME
    ) as credentials:
        connector = create_connector(
            alias=credentials.alias, username=credentials.username
        )
        connector.connect()


### Test that we can connect to the main connection testing database
def test_connection_database_exists():
    with setup_test_credentials(
        alias=MAIN_TEST_ALIAS, username=MAIN_TEST_USERNAME
    ) as credentials:
        connector = create_connector(
            alias=credentials.alias, username=credentials.username
        )
        connector.switch_database(MAIN_TEST_DATABASE)


### Test that database connection failures are caught
def test_failure_connection():
    with setup_test_credentials(
        alias=MAIN_TEST_ALIAS, username=MAIN_TEST_USERNAME
    ) as credentials:
        connector = create_connector(
            alias=credentials.alias, username=credentials.username
        )
        connector.switch_database(SILLY_DATABASE)

        with pytest.raises(DatabaseConnectionError):
            connector.connect()


def __platform_missing(platform: str):
    config = get_credentials_for_connection_test(platform=platform)
    if config:
        return False
    else:
        return True


def __reason(platform: str):
    return (
        f"Platform '{platform}' is not set up under '{integrity.CONFIG_TEST_CONNECTIONS}' "
        + f"in '{integrity.PATH_CONFIG_CREDENTIALS}'"
    )


def __test_connections(platform: str):
    alias_usernames = get_credentials_for_connection_test(platform=platform)

    for alias, username in alias_usernames:
        with setup_test_credentials(alias=alias, username=username) as credentials:
            connector = create_connector(alias=alias, custom_credentials=credentials)
            print(f"TESTING CONNECTION with {credentials}")
            connector.connect()
            connector.close_connection()


### Test Oracle Connections ###
@pytest.mark.skipif(__platform_missing("oracle"), reason=__reason("oracle"))
def test_oracle_connection():
    __test_connections(platform="oracle")


### Test Mssql Connections ###
@pytest.mark.skipif(__platform_missing("mssql"), reason=__reason("mssql"))
def test_mssql_connection():
    __test_connections(platform="mssql")


### Test Informix Connections ###
@pytest.mark.skipif(__platform_missing("informix"), reason=__reason("informix"))
def test_informix_connection():
    __test_connections(platform="informix")


### Test Cache Connections ###
@pytest.mark.skipif(__platform_missing("cache"), reason=__reason("cache"))
def test_cache_connection():
    __test_connections(platform="cache")


### Test Iris Connections ###
@pytest.mark.skipif(__platform_missing("iris"), reason=__reason("iris"))
def test_iris_connection():
    __test_connections(platform="iris")


### Test Postgresql Connections ###
@pytest.mark.skipif(__platform_missing("postgresql"), reason=__reason("postgresql"))
def test_postgresql_connection():
    __test_connections(platform="postgresql")


### Test mariadb Connections ###
@pytest.mark.skipif(__platform_missing("mariadb"), reason=__reason("mariadb"))
def test_mariadb_connection():
    __test_connections(platform="mariadb")


if __name__ == "__main__":
    pytest.main([__file__])
