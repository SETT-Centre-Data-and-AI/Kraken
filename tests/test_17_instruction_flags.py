from pathlib import Path

import pytest

from kraken.ribosome.support import _fetch_split_sql_behaviour
from kraken.support.support import _extract_instruction


@pytest.mark.parametrize(
    "following_comments",
    [
        "",
        "-- An unrelated line comment follows.\n",
        "/* An unrelated block comment follows. */\n",
        "-- An unrelated line comment follows.\n"
        "/* An unrelated block comment follows. */\n",
    ],
)
def test_instruction_flags_ignore_following_comments(
    following_comments: str,
) -> None:
    sql = (
        "--$Database = Research\n"
        f"{following_comments}"
        "--$Dataframe = Results\n"
        f"{following_comments}"
        "--$Split = False\n"
        f"{following_comments}"
        "SELECT 1;\n"
    )

    assert _extract_instruction(sql, "Database") == "Research"
    assert _extract_instruction(sql, "Dataframe") == "Results"
    assert _extract_instruction(sql, "Split") == "False"
    assert _fetch_split_sql_behaviour(sql, Path("flags.sql")) is False
