import re
from difflib import Differ
from pathlib import Path

import pytest
from support.exceptions import MissingError
from support.integrity import PATH_SQL_PARSING, SUFFIX_INPUT, SUFFIX_OUTPUTS

from kraken.parsing.parsing import Parser
from kraken.platforms.config import platforms


### Helper Class ###
class PlatformTest:
    def __init__(self, platform: str):
        """Parsing test coordinator for a given platform. To set up parsing tests
        for a platform, under the `tests/sql/parsing` we should have the structure:

        `platform/` (folder name should be the name of the platform, case-sensitive)
         - `test_n/` (minimum of one test, folder name not enforced but should be in order)
           - `input.sql` (input SQL, file name enforced)
           - `outputs/` (folder for each expected output query, folder name enforced)
            - `1.sql` (first expected output query - integer filename not enforced but should be in order)
            - `2.sql`
            -  `...`

        During comparison of parsed and expected outputs, multiple line breaks are
        ignored, as is start and end whitespace.
        """
        self.platform: str = platform
        self.parsing_tests: list[ParsingTest] = list()
        self.platform_folder: Path = PATH_SQL_PARSING / platform

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(platform='{self.platform}', parsing_tests={len(self.parsing_tests)})"

    def load_parsing_tests(self) -> None:
        """Instantiates a ParsingTest class for each test in the platform folder."""
        test_folders: list[Path] = []
        for file in self.platform_folder.glob("*"):
            if file.is_dir():
                test_folders.append(file)

        for test_folder in test_folders:
            test = ParsingTest(platform=self.platform, test_folder=test_folder)
            self.parsing_tests.append(test)

        if not len(self.parsing_tests):
            raise MissingError(
                f"No tests found for platform '{self.platform}'. Check: '{self.platform_folder}'"
            )

    def run_tests(self) -> None:
        if not len(self.parsing_tests):
            raise ValueError(
                "No parsing tests to run. First run `self.load_parsing_tests()`"
            )
        for test in self.parsing_tests:
            test.run_test()


class ParsingTest:
    def __init__(self, platform: str, test_folder: Path) -> None:
        self.platform: str = platform
        self.test_folder: Path = test_folder
        self.name: str = test_folder.name
        self.input: str | None = None
        self.expected_outputs: list[str] | None = None
        self.parser = Parser(platform=platform, feedback=False)
        self.reports: list[tuple[str, str]] | None = None
        self.__get_input_sql()
        self.__get_output_sql()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(platform='{self.platform}', name='{self.name}')"
        )

    def __get_input_sql(self) -> None:
        """Attaches input sql from test folder.

        Raises:
            MissingError: if input sql is not found
        """
        input_file = self.test_folder / SUFFIX_INPUT
        with input_file.open() as file:
            self.input = file.read()

        if not self.input:
            raise MissingError(f"No expected input sql found. Check: '{input_file}'")

    def __get_output_sql(self) -> None:
        """Attaches expected output sql from test folder.

        Raises:
            MissingError: if no expected output queries are found
        """
        self.expected_outputs = list()
        output_folder = self.test_folder / SUFFIX_OUTPUTS
        for filepath in sorted(output_folder.glob("*.sql")):
            with filepath.open() as file:
                output = file.read()
                self.expected_outputs.append(output)

        if not len(self.expected_outputs):
            raise ValueError(f"No expected output SQL found. Check: '{output_folder}'")

    def _clean_text(self, text: str) -> str:
        """Removes multiple line breaks and start and end whitespace."""
        stripped_lines = [line.strip() for line in text.splitlines()]
        cleaned_text = "\n".join(stripped_lines)
        cleaned_text = re.sub(r"\n+", "\n", cleaned_text)
        cleaned_text = cleaned_text.strip()
        return cleaned_text

    def _check_diff(self, expected: str, actual: str) -> str:
        """Examines difference between expected and actual queries, and returns
        results."""
        differ = Differ()
        diff = list(differ.compare(expected.splitlines(), actual.splitlines()))

        highlighted = []
        for line in diff:
            if line.startswith("+ "):
                highlighted.append(f"\033[92m{line[2:]}\033[0m")  # Green
            elif line.startswith("- "):
                highlighted.append(f"\033[91m{line[2:]}\033[0m")  # Red
            elif line.startswith("? "):
                highlighted.append(f"\033[93m{line[2:]}\033[0m")  # Yellow
            else:
                highlighted.append(line[2:])

        return "\n".join(highlighted)

    def get_report(self) -> str:
        report = []
        if self.reports is not None:
            for i, (status, sql_diff) in enumerate(self.reports):
                report.append(
                    f"Output {i + 1} ({status}):\n{sql_diff}\n-----------------"
                )

        return "\n\n".join(report)

    def print_report(self) -> None:
        print(self.get_report())

    def run_test(self) -> None:
        """Parses input SQL, and compares results against expected outputs.
        Checks correct number of outputs, and errors if disparity in count or
        content of each query."""
        self.reports = list()

        if not self.input:
            raise ValueError(
                f"No input SQL found for test. Check: '{self.test_folder}'"
            )

        if not self.expected_outputs:
            raise ValueError(
                f"No expected outputs found for test. Check: '{self.test_folder}'"
            )

        self.parser.parse_sql(input_sql=self.input)

        assert len(self.parser.queries) == len(self.expected_outputs), (
            "Disparity in number of expected vs parsed outputs "
            + f"({self.platform}/{self.name}):"
            + f"\nExpected: {len(self.expected_outputs)} queries"
            + f"\nParsed:   {len(self.parser.queries)} queries"
        )

        failures = 0
        for i in range(len(self.parser.queries)):
            expected_output = self._clean_text(self.expected_outputs[i])
            actual_output = self._clean_text(self.parser.queries[i].sql)
            sql_diff = self._check_diff(expected_output, actual_output)

            if actual_output == expected_output:
                status = "PASS"
            else:
                status = "FAIL"
                failures += 1

            self.reports.append((status, sql_diff))

        assert failures == 0, (
            f"Parsed query differs from expectation ({self.platform}/{self.name}):"
            + "\n\nInput SQL:"
            + f"{self.input}"
            + f"\n\n{self.get_report()}"
        )


### Helpers ###
def collect_parsing_tests() -> list[ParsingTest]:
    all_tests: list[ParsingTest] = []
    for platform in platforms:
        platform_test = PlatformTest(platform)
        platform_test.load_parsing_tests()
        all_tests.extend(platform_test.parsing_tests)
    return all_tests


### ====================== ###
### ---------TESTS---------###
### ====================== ###


@pytest.mark.parametrize(
    "parsing_test",
    collect_parsing_tests(),
    ids=lambda t: f"{t.platform}/{t.name}",
)
def test_parser_dialects(parsing_test: ParsingTest) -> None:
    """Run a single parsing test (one platform + one tes)."""
    parsing_test.run_test()


if __name__ == "__main__":
    pytest.main([__file__])
