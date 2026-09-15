from pathlib import Path

from kraken import demo
from kraken.classes.pack_lists import ResultList


def test_demo_generator_is_available_from_top_level_package(tmp_path: Path) -> None:
    results = demo.generate_demo_data(output_dir=tmp_path, seed=20260824)

    assert isinstance(results, ResultList)
    assert [result.df_name for result in results] == [
        "patients",
        "inpatient_spells",
        "lab_tests",
    ]
    assert [len(result.df) for result in results] == [2_500, 10_000, 40_000]
    assert sorted(path.name for path in tmp_path.glob("*.csv")) == [
        "inpatient_spells.csv",
        "lab_tests.csv",
        "patients.csv",
    ]
