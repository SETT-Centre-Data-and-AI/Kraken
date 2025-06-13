from kraken.connection.connector import Connector, create_connector
from support import integrity
from support.credentials import get_credentials_for_main_connection_test

config = get_credentials_for_main_connection_test()
MAIN_TEST_USERNAME = config[integrity.USERNAME]
MAIN_TEST_DATABASE = config[integrity.DATABASE]


def get_main_test_connector() -> Connector:
    connector = create_connector(
        alias=integrity.MAIN_ALIAS, username=MAIN_TEST_USERNAME
    )
    connector.switch_database(MAIN_TEST_DATABASE)
    return connector
