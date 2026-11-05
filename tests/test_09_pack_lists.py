import pytest  # noqa
from pandas import DataFrame
from kraken import execute_sql, export_results, extract_spreadsheets, extract_sql
from kraken.classes.pack_lists import QueryList, ResultList
from kraken.classes.packs import Query, Result
from kraken.ribosome import sql_execution

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


def test_result_list_supports_position_and_name_indexing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    first = Result(DataFrame({"value": [1]}), "first")
    duplicate = Result(DataFrame({"value": [2]}), "duplicate")
    result_list = ResultList(
        [first, duplicate, Result(DataFrame({"value": [3]}), "duplicate")]
    )

    assert result_list[0] is first
    assert result_list[:2] == [first, duplicate]
    assert isinstance(result_list[:2], ResultList)
    assert result_list["first"] is first
    assert result_list["duplicate"] is duplicate
    assert "duplicate matches found" in capsys.readouterr().out


def test_result_list_drop_removes_all_matching_results(
    capsys: pytest.CaptureFixture[str],
) -> None:
    first = Result(DataFrame({"value": [1]}), "first")
    duplicate = Result(DataFrame({"value": [2]}), "duplicate")
    middle = Result(DataFrame({"value": [3]}), "middle")
    remaining_duplicate = Result(DataFrame({"value": [4]}), "duplicate")
    result_list = ResultList([first, duplicate, middle, remaining_duplicate])

    result_list.drop("duplicate")

    assert list(result_list) == [first, middle]
    assert "all 2 matches will be dropped" in capsys.readouterr().out


def test_result_list_drop_can_remove_only_first_match(
    capsys: pytest.CaptureFixture[str],
) -> None:
    first = Result(DataFrame({"value": [1]}), "duplicate")
    second = Result(DataFrame({"value": [2]}), "duplicate")
    result_list = ResultList([first, second])

    result_list.drop("duplicate", drop_all=False)

    assert list(result_list) == [second]
    assert "only the first match will be dropped" in capsys.readouterr().out


def test_result_list_remove_aliases_drop() -> None:
    first = Result(DataFrame({"value": [1]}), "first")
    second = Result(DataFrame({"value": [2]}), "second")
    result_list = ResultList([first, second])

    result_list.remove("first", "df_name")

    assert list(result_list) == [second]


def test_query_list_supports_position_and_name_indexing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    filepath = Path("test.sql")
    first = Query("test", "first", "SELECT 1", filepath)
    duplicate = Query("test", "duplicate", "SELECT 2", filepath)
    query_list = QueryList(
        [first, duplicate, Query("test", "duplicate", "SELECT 3", filepath)]
    )

    assert query_list[0] is first
    assert query_list[:2] == [first, duplicate]
    assert isinstance(query_list[:2], QueryList)
    assert query_list["first"] is first
    assert query_list["duplicate"] is duplicate
    assert "duplicate matches found" in capsys.readouterr().out


def test_query_list_remove_aliases_drop() -> None:
    filepath = Path("test.sql")
    first = Query("test", "first", "SELECT 1", filepath)
    second = Query("test", "second", "SELECT 2", filepath)
    query_list = QueryList([first, second])

    query_list.remove("first", "df_name")

    assert list(query_list) == [second]


def test_query_list_drop_removes_all_duplicate_matches(
    capsys: pytest.CaptureFixture[str],
) -> None:
    filepath = Path("test.sql")
    first = Query("test", "duplicate", "SELECT 1", filepath)
    second = Query("test", "duplicate", "SELECT 2", filepath)
    query_list = QueryList([first, second])

    query_list.drop("duplicate")

    assert len(query_list) == 0
    assert "all 2 matches will be dropped" in capsys.readouterr().out


def test_remove_item_preserves_user_list_behavior() -> None:
    result = Result(DataFrame({"value": [1]}), "result")
    result_list = ResultList([result])
    result_list.drop(result)
    assert len(result_list) == 0
    result_list.append(result)
    result_list.remove(result)
    assert len(result_list) == 0

    query = Query("test", "query", "SELECT 1", Path("test.sql"))
    query_list = QueryList([query])
    query_list.drop(query)
    assert len(query_list) == 0
    query_list.append(query)
    query_list.remove(query)
    assert len(query_list) == 0


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


def test_execute_sql_accepts_single_query(monkeypatch: pytest.MonkeyPatch) -> None:
    query = Query(
        filename="test",
        df_name="sample",
        sql="SELECT 1",
        filepath=Path("test.sql"),
        db_alias="test_db",
    )
    captured: dict[str, object] = {}

    def fake_execute_all_queries(**kwargs: object) -> ResultList:
        captured.update(kwargs)
        return ResultList()

    monkeypatch.setattr(
        sql_execution, "__execute_all_queries", fake_execute_all_queries
    )

    result = execute_sql(query)

    mapping = captured["db_sql_mapping"]
    assert isinstance(result, ResultList)
    assert isinstance(mapping, dict)
    assert list(mapping.values()) == [QueryList([query])]


if __name__ == "__main__":
    pytest.main([__file__])
