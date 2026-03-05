from pathlib import Path

import pytest
from support import integrity  # noqa
from support.config import config

from kraken.classes.pack_lists import QueryList
from kraken.classes.packs import Query
from kraken.ribosome.ribosome import run
from kraken.ribosome.sql_execution import create_db_sql_mapping

### ====================== ###
### ---------TESTS---------###
### ====================== ###


def test_create_db_sql_mapping_groups_queries_by_file_not_df_name() -> None:
    """Test that queries are always grouped by filename."""
    filepath = Path("test.sql")
    query_list = QueryList(
        [
            Query(
                filename="test.sql",
                df_name="FirstDf",
                sql="SELECT 1;",
                filepath=filepath,
                db_alias="MAIN",
            ),
            Query(
                filename="test.sql",
                df_name="SecondDf",
                sql="SELECT 2;",
                filepath=filepath,
                db_alias="MAIN",
            ),
        ]
    )

    mapping = create_db_sql_mapping(query_list)

    assert len(mapping) == 1
    grouped_queries = list(mapping.values())[0]
    assert len(grouped_queries) == 2
    assert [query.df_name for query in grouped_queries] == ["FirstDf", "SecondDf"]


def test_queries_run_in_correct_order() -> None:
    _credentials = config.main_test.setup_test_credentials()
    SQL_TEST_ORDER = (
        integrity.PATH_SQL_EXECUTION / r"13_test_execution_behaviour/01_test_run_order"
    )
    results = run(SQL_TEST_ORDER)

    for i, result in enumerate(results):
        order = i + 1
        assert result.df.iloc[0, 0] == order


if __name__ == "__main__":
    pytest.main([__file__])
