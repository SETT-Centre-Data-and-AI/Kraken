from __future__ import annotations

from pathlib import Path

# Paths
PATH_TESTS = Path(__file__).parents[1]
PATH_SQL = PATH_TESTS / "sql"
PATH_SQL_PARSING = PATH_SQL / "parsing"
PATH_CONFIG = PATH_TESTS / "config"

PATH_CONFIG_CREDENTIALS = PATH_CONFIG / "credentials.yaml"
PATH_CONFIG_TEMPLATE_CREDENTIALS = PATH_TESTS / "config_template/credentials.yaml"

# Tokens
CONFIG_TEST_CONNECTIONS = "test_connections"

# Aliases
SUFFIX_INPUT = "input.sql"
SUFFIX_OUTPUTS = "outputs"

PATH_SQL_EXECUTION = PATH_SQL / "execution"
PATH_SQL_MAIN = PATH_SQL_EXECUTION / "main"
PATH_OUTPUTS = PATH_TESTS / "outputs"
