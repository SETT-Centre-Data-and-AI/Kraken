import textwrap

import pytest

from kraken.parsing.parsing import Parser
from kraken.platforms.config import get_platform_config


### Helpers ###
def setup_parser(platform: str) -> Parser:
    """Setup a mock configuration and initialize the parser."""
    parser_config = get_platform_config(platform)

    parser = Parser(platform=parser_config.platform, feedback=False)
    return parser


def oracle_parser() -> Parser:
    return setup_parser("oracle")


def mssql_parser() -> Parser:
    return setup_parser("mssql")


### ====================== ###
### ---------TESTS---------###
### ====================== ###


def test_load_sql() -> None:
    """Test that SQL input is correctly loaded and stripped."""
    parser = mssql_parser()
    test_sql = "SELECT * FROM table;         \n\n"
    parser._Parser__load_sql(test_sql)  # type: ignore
    assert parser.input_sql == "SELECT * FROM table;\n"


def test_oracle_extract_variables() -> None:
    """Test that variable declarations are correctly extracted."""
    parser = oracle_parser()
    test_sql = """
    DEFINE var1 = 'value1'
    DEFINE var2 = 'value2'
    DEFINE var3 = 0
    SELECT * FROM table;
    """
    parser.parse_sql(test_sql)

    expected_variables = {"var1": "value1", "var2": "value2", "var3": "0"}
    assert parser.start_variables == expected_variables


def test_mssql_extract_variables() -> None:
    """Test that variable declarations are correctly extracted."""
    parser = mssql_parser()
    test_sql = """
    DECLARE @var1 NVARCHAR(6) = 'value1'
    DECLARE @var2 NVARCHAR(6) = 'value2'
    DECLARE @var3 BIT = 0
    SELECT * FROM table;
    """
    parser.parse_sql(test_sql)

    expected_variables = {"var1": "value1", "var2": "value2", "var3": "0"}
    assert parser.start_variables == expected_variables


def test_variable_replacement() -> None:
    """Test that variable replacements are applied correctly."""
    parser = mssql_parser()
    test_sql = textwrap.dedent(
        """
                               DECLARE @var1 NVARCHAR(6) = 'value1';
                               SELECT * FROM table WHERE column = var1;
                               """
    )
    user_variables = {"var1": "new_value"}

    parser.parse_sql(test_sql, user_variables)
    expected_sql = "DECLARE @var1 NVARCHAR(6) = new_value\nSELECT * FROM table WHERE column = var1;"

    assert parser.processing_sql and parser.processing_sql.strip() == expected_sql


def test_split_queries() -> None:
    """Test that queries are correctly split based on platform settings."""
    parser = mssql_parser()
    test_sql = """
    SELECT * FROM table1;
    SELECT * FROM table2;
    """
    parser.parse_sql(test_sql)

    assert len(parser.queries) == 2
    assert parser.queries[0].sql.strip() == "SELECT * FROM table1;"
    assert parser.queries[1].sql.strip() == "SELECT * FROM table2;"


def test_summary_report() -> None:
    """Test that the summary report is correctly generated."""
    parser = mssql_parser()
    test_sql = """
    DECLARE @var1 NVARCHAR(6) = 'value1'
    DECLARE @var2 NVARCHAR(6) = 'value2'
    SELECT * FROM table WHERE column = var1;
    """
    user_variables = {"var1": "new_value", "var2": "new_value"}

    parser.parse_sql(test_sql, user_variables)
    report = parser.get_summary_report()

    assert "Total Queries Found:   1" in report
    assert "Variable Replacements:  2" in report


def test_comment_new_lines() -> None:
    """Test that the parser correctly handles line and block comments,
    leaving new lines in place.
    """
    input = """Line 1
Line 2 --another comment
/*
Line 4
Line 5
*/
Line 7"""
    output = "Line 1\nLine 2                  \n  \n      \n      \n  \nLine 7\n"

    parser = oracle_parser()
    parser.parse_sql(input)
    assert (
        parser.comment_suppressed_sql
        and parser.comment_suppressed_sql.strip() == output.strip()
    )


def test_variable_handling_with_comment() -> None:
    """Test that variable replacement is not disrupted by comments"""

    input = """
    DEFINE GlobalStartDate = "01-DEC-2024" -- comment
    DEFINE GlobalEndDate = "02-DEC-2024"

    SELECT  *
    FROM    Patients
    WHERE   1=1
        AND Patients.BIRTH_DATE BETWEEN '&GlobalStartDate'
                                    AND '&GlobalEndDate'
    """

    output = """


    SELECT  *
    FROM    Patients
    WHERE   1=1
        AND Patients.BIRTH_DATE BETWEEN '01-DEC-2024'
                                    AND '02-DEC-2024'
    """

    parser = oracle_parser()
    parser.parse_sql(input_sql=input)
    assert parser.processing_sql and parser.processing_sql.strip() == output.strip()

    parser.reset()
    parser.parse_sql(input, user_variables={"GlobalEndDate": "31-DEC-2024"})
    assert (
        parser.processing_sql
        and parser.processing_sql.strip()
        == output.replace("02-DEC-2024", "31-DEC-2024").strip()
    )


def test_variable_handling_remove_declaration() -> None:
    parser = oracle_parser()
    variables = {"Prefix": "new"}
    input_sql = """
use big_projects
DEFINE Prefix = 'old'
SELECT  *
FROM    a_table
WHERE   a_column LIKE '&Prefix' || '%'"""
    output_sql = """
use big_projects

SELECT  *
FROM    a_table
WHERE   a_column LIKE 'new' || '%'"""
    parser.parse_sql(input_sql, user_variables=variables)
    assert parser.processing_sql and parser.processing_sql.strip() == output_sql.strip()


def test_variable_handling_no_remove_declaration() -> None:
    parser = mssql_parser()
    variables = {"Prefix": "new"}
    input_sql = """
use big_projects
DECLARE @Prefix VARCHAR(1) = 'old'
SELECT  *
FROM    a_table
WHERE   a_column LIKE '@Prefix' + '%'
    """

    output_sql = """
use big_projects
DECLARE @Prefix VARCHAR(1) = 'new'
SELECT  *
FROM    a_table
WHERE   a_column LIKE '@Prefix' + '%'
    """
    parser.parse_sql(input_sql, user_variables=variables)
    assert parser.processing_sql and parser.processing_sql.strip() == output_sql.strip()


if __name__ == "__main__":
    pytest.main([__file__])
