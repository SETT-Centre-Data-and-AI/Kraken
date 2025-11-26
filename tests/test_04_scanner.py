import pytest

from kraken.parsing.scanning import Scanner, create_scanner


# Fixtures
@pytest.fixture
def sample_scanner() -> Scanner:
    sql = """--$Database=EPR
    SELECT * FROM FINDING WHERE description LIKE '%melanoma%';
    -- Comment
    /* Block comment
    insert some data*/
    INSERT INTO users (id, name) VALUES (2, 'John');"""
    comment_tokens = [("--", "\n"), ("/*", "*/")]
    wrapper_tokens = [("'", "'")]
    split_tokens = [(";", None)]

    return create_scanner(
        sql=sql,
        comment_tokens=comment_tokens,
        wrapper_tokens=wrapper_tokens,
        split_tokens=split_tokens,
        feedback=False,
        comment_only_mode=False,
    )


### ====================== ###
### ---------TESTS---------###
### ====================== ###


def test_scan_for_zones(sample_scanner: Scanner) -> None:
    sample_scanner._Scanner__scan_for_zones()  # type: ignore
    regions = sample_scanner.regions
    assert len(regions) == 5


def test_scan_for_splits(sample_scanner: Scanner) -> None:
    sample_scanner.scan_sql()
    splits = [region for region in sample_scanner.regions if region.type == "Split"]
    assert len(splits) == 2  # Expecting 2 split points due to the two semicolons


def test_suppress_sql_zones(sample_scanner: Scanner) -> None:
    sample_scanner._Scanner__scan_for_zones()  # type: ignore
    sample_scanner._Scanner__suppress_sql_zones()  # type: ignore
    suppressed_sql = sample_scanner.zone_suppressed_sql

    if isinstance(suppressed_sql, str):
        assert "--$Database=EPR" not in suppressed_sql
        assert "-- Comment" not in suppressed_sql
        assert "/* Block comment */" not in suppressed_sql


def test_event_handling(sample_scanner: Scanner) -> None:
    sample_scanner._Scanner__scan_for_zones()  # type: ignore
    sample_scanner._Scanner__scan_for_splits()  # type: ignore
    events = sample_scanner._Scanner__return_events("Split")  # type: ignore
    assert len(events) == 4


if __name__ == "__main__":
    pytest.main([__file__])
