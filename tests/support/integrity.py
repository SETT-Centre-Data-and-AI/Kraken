from pathlib import Path

PATH_TESTS = Path(__file__).parents[1]
PATH_CONFIG = PATH_TESTS / "config"

PATH_CONFIG_CREDENTIALS = PATH_CONFIG / "credentials.yaml"

TEST_CRED_ALIAS = "KRAKEN_TEST_{suffix}"
MAIN_ALIAS = "KRAKEN_TEST_MAIN"

ALIAS = "alias"
USERNAME = "username"
DATABASE = "database"
SCHEMA = "schema"

CONFIG_MAIN_CONNECTION_TEST = "main_connection_test"
CONFIG_TEST_CONNECTIONS = "test_connections"

PATH_SQL = PATH_TESTS / "sql"
PATH_SQL_PARSING = PATH_SQL / "parsing"
SUFFIX_INPUT = "input.sql"
SUFFIX_OUTPUTS = "outputs"

PATH_SQL_EXECUTION = PATH_SQL / "execution"
PATH_SQL_MAIN = PATH_SQL_EXECUTION / "main"
PATH_OUTPUTS = PATH_TESTS / "outputs"
