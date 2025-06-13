import pytest  # noqa
from support.credentials import setup_main_test_credentials  # noqa
from support import integrity  # noqa
from kraken.ribosome.ribosome import run
from kraken.classes.pack_lists import ResultList


def test_ribosome():
    SQL_TEST_DIR = integrity.PATH_SQL_MAIN / "10_test_ribosome"

    with setup_main_test_credentials():
        results = run(filepaths=SQL_TEST_DIR, variables={})

    assert results is not None
    assert isinstance(results, ResultList)
    assert len(results) == 6
    assert results.get("Diagnosis").df.iloc[0, 0] == 1
    assert results.get("Tests").df.iloc[0, 0] == 2
    assert results.get("TestResults").df.iloc[0, 0] == 3
    assert results.get("Single").df.iloc[0, 0] == 0
    assert results.get("Multiple").df.iloc[0, 0] == 1
    assert results.get("Multiple_02").df.iloc[0, 0] == 2


if __name__ == "__main__":
    pytest.main([__file__])
