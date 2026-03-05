import pytest  # noqa
from pandas import DataFrame
from kraken import execute_sql, export_results, extract_spreadsheets, extract_sql
from kraken.classes.pack_lists import QueryList, ResultList
from kraken.classes.packs import Query, Result

from support import integrity  # noqa
from support.config import config
from pathlib import Path

TEST_SUB_DIR = Path(__name__).stem


def test_get_data() -> None:
    SQL_TEST_DIR = integrity.PATH_SQL_MAIN

    _credentials = config.main_test.setup_test_credentials()
    sql = extract_sql(SQL_TEST_DIR / "09_pack_list_test.sql")
    results = execute_sql(sql)
    print(results)
    with config.setup_test_output_subdir(name=TEST_SUB_DIR) as directory:
        export_results(
            results,
            directory,
            extension="xlsx",
            overwrite=True,
            filename="Pack List Test",
        )

        spreadsheets = extract_spreadsheets(directory)

        assert sql is not None
        assert results is not None
        assert spreadsheets is not None

        assert isinstance(sql, QueryList)
        assert isinstance(results, ResultList)
        assert isinstance(spreadsheets, ResultList)

        assert isinstance(sql.get("Diagnosis"), Query)
        assert isinstance(results.get("Diagnosis"), Result)
        assert isinstance(spreadsheets.get("Diagnosis"), Result)

        results.get("Diagnosis")


def test_query_list_get_all_returns_query_list() -> None:
    filepath = Path("test.sql")
    query_list = QueryList(
        [
            Query(
                filename="test",
                df_name="dupe",
                sql="SELECT 1",
                filepath=filepath,
            ),
            Query(
                filename="test",
                df_name="dupe",
                sql="SELECT 2",
                filepath=filepath,
            ),
        ]
    )

    found = query_list.get("dupe", get_all=True)
    assert isinstance(found, QueryList)
    assert len(found) == 2
    assert found[0].sql == "SELECT 1"
    assert found[1].sql == "SELECT 2"


def test_result_query_executes_sql() -> None:
    result = Result(df=DataFrame({"value": [1, 2, 3]}), df_name="sample")

    output = result.query("SELECT SUM(value) AS total FROM sample")

    assert int(output["total"].iloc[0]) == 6


def test_result_list_query_executes_sql() -> None:
    result_list = ResultList(
        [
            Result(df=DataFrame({"id": [1, 2]}), df_name="a"),
            Result(df=DataFrame({"id": [10]}), df_name="b"),
        ]
    )

    output = result_list.query("SELECT COUNT(*) AS c FROM a")

    assert int(output["c"].iloc[0]) == 2


if __name__ == "__main__":
    pytest.main([__file__])
