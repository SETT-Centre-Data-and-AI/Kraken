import pytest  # noqa
from support import integrity  # noqa
from support.config import config

TABLE = "test_commit"
SCHEMA = config.main_test.schema
FQN = f"{SCHEMA}.{TABLE}"

COLUMN = "ID"
ORIGINAL = "original"
EDITED = "edited"

main_test = config.main_test


# Test that commits can be controlled by connectors
@pytest.mark.skipif(main_test.fallback, reason="Using DuckDB")
def test_template_main() -> None:
    _credentials = main_test.setup_test_credentials()
    main_test.get_connector()
    # Create Connectors
    setup = main_test.get_connector()
    edit = main_test.get_connector()
    check = main_test.get_connector()
    all_connectors = [setup, edit, check]

    for connector in all_connectors:
        connector.connect()

    # SQL
    setup_drop_table = f"DROP TABLE IF EXISTS {FQN}"
    sql_add_data = (
        f"CREATE TABLE {FQN} AS SELECT '{ORIGINAL}' AS '{COLUMN}' "
        if main_test.fallback
        else f"SELECT '{ORIGINAL}' AS {COLUMN} INTO {FQN}"
    )
    sql_update = f"UPDATE {FQN} SET ID = '{EDITED}'"
    sql_select = f"SELECT * FROM {FQN}"
    sql_select_no_lock = f"SELECT * FROM {FQN} WITH (NOLOCK)"

    # Setup table
    setup.execute(setup_drop_table, commit=True, close=False)
    setup.execute(sql_add_data, commit=True, close=False)

    # Edit and Check Without Commit
    edit.execute(sql_update, commit=False, close=False)
    assert (
        edit.execute(sql_select, commit=False, close=False)[COLUMN].iloc[0]  # type: ignore
        == EDITED
    )
    assert (
        check.execute(sql_select_no_lock, commit=True, close=False)[COLUMN].iloc[0]  # type: ignore
        == EDITED
    )

    # Close without commiting and check again
    edit.close_connection()
    assert (
        check.execute(sql_select, commit=True, close=False)[COLUMN].iloc[0]  # type: ignore
        == ORIGINAL
    )

    # Finish
    setup.execute(setup_drop_table, commit=True, close=False)

    for connector in all_connectors:
        connector.close_connection()


if __name__ == "__main__":
    test_template_main()
    # pytest.main([__file__])
