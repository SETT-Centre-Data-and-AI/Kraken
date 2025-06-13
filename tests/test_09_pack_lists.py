import pytest  # noqa
from kraken import execute_sql, export_results, extract_spreadsheets, extract_sql
from kraken.classes.pack_lists import QueryList, ResultList
from kraken.classes.packs import Query, Result

from support import integrity  # noqa
from support.credentials import setup_main_test_credentials  # noqa


def test_get_data():
    SQL_TEST_DIR = integrity.PATH_SQL_MAIN
    OUTPUT_TEST_DIR = integrity.PATH_OUTPUTS

    with setup_main_test_credentials():
        sql = extract_sql(SQL_TEST_DIR / "09_pack_list_test.sql")
        results = execute_sql(sql)
        print(results)
        _exports = export_results(
            results,
            OUTPUT_TEST_DIR,
            extension="xlsx",
            overwrite=True,
            filename="Pack List Test",
        )
        spreadsheets = extract_spreadsheets(OUTPUT_TEST_DIR)

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


if __name__ == "__main__":
    pytest.main([__file__])
