import pytest  # noqa
from support import integrity  # noqa
from support.connection import get_main_test_connector  # noqa
from support.credentials import (
    setup_main_test_credentials,
    get_credentials_for_main_connection_test,
)  # noqa

config = get_credentials_for_main_connection_test()
DATABASE = config[integrity.DATABASE]
SCHEMA = config[integrity.SCHEMA]
TABLE = "test_commit"
FQN = f"{DATABASE}.{SCHEMA}.{TABLE}"

COLUMN = "ID"
ORIGINAL = "original"
EDITED = "edited"


# Test that commits can be controlled by connectors
def test_template_main():
    with setup_main_test_credentials():
        # CrePrepareate Connectors
        setup = get_main_test_connector()
        edit = get_main_test_connector()
        check = get_main_test_connector()
        all_connectors = [setup, edit, check]

    for connector in all_connectors:
        connector.connect()

    # Setup Table
    setup.execute(f"DROP TABLE IF EXISTS {FQN}", commit=True, close=False)
    setup.execute(
        f"SELECT '{ORIGINAL}' AS {COLUMN} INTO {FQN}", commit=True, close=False
    )

    # Edit and Check Without Commit
    edit.execute(f"UPDATE {FQN} SET ID = '{EDITED}'", commit=False, close=False)
    assert (
        edit.execute(f"SELECT * FROM {FQN}", commit=False, close=False)[COLUMN].iloc[0]
        == EDITED
    )
    assert (
        check.execute(f"SELECT * FROM {FQN} WITH (NOLOCK)", commit=True, close=False)[
            COLUMN
        ].iloc[0]
        == EDITED
    )

    # Close without commiting and check again
    edit.close_connection()
    assert (
        check.execute(f"SELECT * FROM {FQN}", commit=True, close=False)[COLUMN].iloc[0]
        == ORIGINAL
    )

    # Finish
    setup.execute(f"DROP TABLE IF EXISTS {FQN}", commit=True, close=False)

    for connector in all_connectors:
        connector.close_connection()


if __name__ == "__main__":
    test_template_main()
    # pytest.main([__file__])
