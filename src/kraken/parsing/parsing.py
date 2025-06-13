import difflib
import re

from kraken.parsing.scanning import SPLIT, ZONE, Region, Scanner, create_scanner
from kraken.parsing.support_classes import Replacement, ScannedQuery
from kraken.platforms.config import PlatformConfig, get_platform_config


class Parser:
    """The `Parser` loads a SQL string and outputs queries. It uses the input
    `platform` to fetch relevant settings (if supported), and first parses the
    SQL for variable declarations - overwriting these as appropriate to the
    platform if applicable. Then, it instantiates a `Scanner`, identifies split
    points as per platform syntax, and splits up the SQL into queries.
    """

    def __init__(self, platform: str | None, feedback: bool = False) -> None:
        self.config: PlatformConfig = get_platform_config(platform)
        self.input_sql: str | None = None
        self.comment_suppressed_sql: str | None = None
        self.processing_sql: str | None = None
        self.replacements: list[Replacement] = []
        self.regions: list[Region] = []
        self.comments: list[Region] = []
        self.queries: list[ScannedQuery] = []
        self.all_queries: list[ScannedQuery] = []
        self.empty_queries: list[ScannedQuery] = []
        self.start_variables: dict = {}
        self.user_variables: dict = {}
        self.final_variables: dict = {}
        self.scanner: Scanner | None = None
        self.feedback: bool = feedback
        self.summary_report: str | None = None

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(platform='{self.config.platform}', "
            + f"queries={len(self.queries)}, "
            + f"variables={len(self.final_variables)}"
            + ")"
        )

    ### Support ###
    def __load_sql(self, input_sql: str) -> None:
        """Loads SQL, stripping white space and adding a final new line to allow
        terminating characters to be fully expressed (e.g. Oracle's '/')

        Args:
            input_sql (str): SQL to be parsed
        """

        self.input_sql = input_sql.strip() + "\n"
        self.processing_sql = self.input_sql

    def __say(self, *values: object, sep: str = " ", end: str = "\n") -> None:
        if self.feedback:
            print(*values, sep=sep, end=end)

    def __attach_scanner(self, comment_only_mode: bool = False) -> None:
        self.scanner = create_scanner(
            sql=self.processing_sql,
            comment_tokens=self.config.comment_tokens,
            wrapper_tokens=self.config.wrapper_tokens,
            split_tokens=self.config.split_tokens,
            comment_only_mode=comment_only_mode,
        )

    def __detach_scanner(self) -> None:
        self.scanner = None

    def __sort_regions(self) -> None:
        if self.regions:
            self.regions = sorted(self.regions, key=lambda x: x.start, reverse=False)

    def __return_regions(self, region_type: str) -> list[Region]:
        regions = [region for region in self.regions if region.type == region_type]
        return sorted(regions, key=lambda x: x.start, reverse=False)

    def __is_string(self, value: str) -> bool:
        if value.startswith(("'", '"')) and value.endswith(
            (
                "'",
                '"',
            )
        ):
            return True
        return False

    def __set_user_variables(self, user_variables: dict | None = None) -> None:
        self.user_variables = user_variables or {}

    def __strip_one_quote(self, value: str) -> str:
        value = value.strip()
        if (value.startswith("'") and value.endswith("'")) or (
            value.startswith('"') and value.endswith('"')
        ):
            return value[1:-1]
        return value

    def __supress_comments(self) -> None:
        self.__attach_scanner(comment_only_mode=True)
        self.scanner.scan_sql()
        self.comment_suppressed_sql = self.scanner.zone_suppressed_sql
        self.comments = self.scanner.regions
        self.__detach_scanner()

    ### Variable Extraction ###
    def __extract_variables(self) -> None:
        # Extract Comment Suppressed SQL
        declare_pattern = self.config.declare_pattern
        sql = self.comment_suppressed_sql

        if declare_pattern:
            matches: list[tuple[str, str]] = re.findall(
                declare_pattern, sql, re.IGNORECASE
            )
            declarations = {
                var_name: self.__strip_one_quote(var_value)
                for var_name, var_value in matches
            }
            self.start_variables = declarations or {}

    def __set_final_variables(self) -> None:
        for var_name in self.start_variables.keys():
            if var_name in self.user_variables:
                self.final_variables[var_name] = self.user_variables[var_name]
            else:
                self.final_variables[var_name] = self.start_variables[var_name]

    def __is_in_comment(self, start_index: int) -> bool:
        for comment in self.comments:
            if comment.start <= start_index <= comment.stop:
                return True
        return False

    def __replace_declaration(self, match: re.Match) -> None:
        var_name, original_value = match.groups()
        if self.config.remove_declaration:
            self.replacements.append(Replacement(match.start(), match.end(), ""))
            return  # Remove declaration

        if var_name not in self.user_variables:
            return  # No replacement needed

        replacement_value = str(self.final_variables.get(var_name, original_value))
        original_value = str(original_value)

        # Preserve original quotes
        if self.__is_string(original_value):
            quote_char = original_value[0]
            replacement_value = (
                f"{quote_char}{replacement_value.strip(quote_char)}{quote_char}"
            )

        # Preserve leading syntax
        relative_start = match.start(2) - match.start()
        declaration_prefix = match.group(0)[:relative_start]
        replacement = f"{declaration_prefix}{replacement_value}"

        self.replacements.append(Replacement(match.start(), match.end(), replacement))

    def __replace_declaration_usage(self, match: re.Match) -> None:
        var_name = match.group(1)
        if var_name in self.final_variables and not self.__is_in_comment(match.start()):
            value: str = self.final_variables[var_name]
            replacement = str(value) if str(value).isdigit() else value
            self.replacements.append(
                Replacement(match.start(), match.end(), replacement)
            )

    def __identify_variable_replacements(self) -> None:
        # Initialize replacements
        self.replacements = []

        declare_pattern = self.config.declare_pattern
        declare_usage_pattern = self.config.declare_usage_pattern

        # Process variable declarations
        if declare_pattern:
            for match in re.finditer(
                declare_pattern, self.input_sql, flags=re.IGNORECASE
            ):
                self.__replace_declaration(match)

        # Process variable usages
        if self.config.replace_all_declare_usages and declare_usage_pattern:
            for match in re.finditer(
                declare_usage_pattern, self.input_sql, flags=re.IGNORECASE
            ):
                self.__replace_declaration_usage(match)

        self.replacements.sort(key=lambda x: x.start, reverse=False)

    def __execute_variable_replacements(self) -> None:
        self.replacements.sort(key=lambda x: x.start, reverse=False)

        modified_sql = self.input_sql
        offset = 0

        for replacement in self.replacements:
            start_index = replacement.start + offset
            end_index = replacement.end + offset

            modified_sql = (
                modified_sql[:start_index]
                + replacement.replacement
                + modified_sql[end_index:]
            )
            offset += len(replacement.replacement) - (end_index - start_index)

        self.processing_sql = modified_sql

    ### Variable Extraction ###
    def __return_applicable_zones(
        self, query_start_index: int, query_end_index: int
    ) -> list[Region]:
        zones = self.__return_regions(region_type=ZONE)
        applicable_zones = []
        for zone in zones:
            if query_start_index <= zone.start < query_end_index:
                shifted_region = zone.copy()
                shifted_region.start -= query_start_index
                shifted_region.stop -= query_start_index
                applicable_zones.append(shifted_region)
        return applicable_zones

    def __append_query(
        self, query: str, query_start_index: int, query_end_index: int
    ) -> None:
        applicable_zones = self.__return_applicable_zones(
            query_start_index=query_start_index,
            query_end_index=query_end_index,
        )
        scanned_query = ScannedQuery(
            sql=query,
            start_index=query_start_index,
            end_index=query_end_index,
            zones=applicable_zones,
        )
        self.all_queries.append(scanned_query)

    def __split_into_queries(self, split_queries: bool = True) -> None:
        sql = self.processing_sql
        self.__sort_regions()
        splits = self.__return_regions(region_type=SPLIT)

        if not splits or not split_queries:
            self.__append_query(
                query=sql, query_start_index=0, query_end_index=len(sql)
            )
            return

        # Process Splits
        query_start_index = 0
        query_end_index = 0

        for split in splits:
            split_token = split.stop_token
            include_length = 0 if self.config.remove_split_token else len(split_token)
            skip_length = len(split_token) if self.config.remove_split_token else 0
            split_index = split.stop + include_length

            query = sql[query_start_index:split_index]
            query_end_index = query_start_index + len(query)
            self.__append_query(
                query=query,
                query_start_index=query_start_index,
                query_end_index=query_end_index,
            )
            query_start_index += len(query) + skip_length

        # Append Final Query
        query = sql[query_start_index:]
        query_end_index = len(sql)
        self.__append_query(
            query=query,
            query_start_index=query_start_index,
            query_end_index=query_end_index,
        )

    def __organise_queries(self) -> None:
        for query in self.all_queries:
            if query.contains_sql:
                self.queries.append(query)
            else:
                self.empty_queries.append(query)

    ### Analysis ###
    def get_differences(self) -> str:
        RED = "\033[31m"  # Deletions
        GREEN = "\033[32m"  # Additions
        BLUE = "\033[34m"  # Changes
        YELLOW = "\033[33m"  # New Query
        RESET = "\033[0m"  # Reset Colour

        input = self.input_sql
        output_lines = []
        query_count = 1
        for query in self.queries:
            output_lines.append(f"# Query {query_count} #")
            query_count += 1

            if query.sql.startswith("\n"):
                output_lines.append(query.sql[1:])
            else:
                output_lines.append(query.sql)
        output = "\n".join(line for line in output_lines)

        input_lines = input.splitlines()
        output_lines = output.splitlines()

        differences = difflib.ndiff(input_lines, output_lines)

        input_line = 1
        rebuild_diff = []
        space = " " * 8
        for line in differences:
            last_line = input_line - 1
            if line.startswith("+ # Query"):
                # New Query: Yellow
                rebuild_diff.append(f"{YELLOW}{space}{line[2:]}{RESET}")
            elif line.startswith("-"):
                # Deletion: Red
                rebuild_diff.append(f"{RED}[{input_line:3d}] {line}{RESET}")
                input_line += 1
            elif line.startswith("+"):
                # Addition: Green
                rebuild_diff.append(f"{GREEN}[{last_line:3d}] {line}{RESET}")
            elif line.startswith("?"):
                # Change indicator: Blue
                rebuild_diff.append(f"{BLUE}[{last_line:3d}] {line[:-1]}{RESET}")
            else:
                # Unchanged: No Colour
                rebuild_diff.append(f"[{input_line:3d}] {line}")
                input_line += 1

        return "\n".join(rebuild_diff)

    def print_differences(self) -> None:
        print(self.get_differences())

    def get_summary_report(self, return_report: bool = True):
        count_queries = len(self.queries)
        count_empty = len(self.empty_queries)
        count_variables = len(self.start_variables)
        count_user_variables = len(self.user_variables)
        count_replacements = len(self.replacements)

        summary_report = f"""
-----------------Start Summary Report-----------------

Configuration
--------------
Platform Set:          {self.config.platform}
Declaration Regex:     {self.config.declare_pattern}
Declare Usage Regex:   {self.config.declare_usage_pattern}
Replace In Situ Mode:  {self.config.replace_all_declare_usages}

Analysis
--------
Total Queries Found:   {count_queries} (+ {count_empty} empty queries discarded)
User Variables Set:    {count_variables}
SQL Variables Found:   {count_user_variables}
Variable Replacemnts:  {count_replacements}

Explore
-------
self.input_sql       for original sql
self.processing_sql  for sql with variable replacement
self.replacements    for variable replacements made
self.queries         for valid queries
self.empty_queries   for empty/discarded queries
self.regions         for region map

Tokens
------
Comments:   {self.config.comment_tokens}
Wrappers:   {self.config.wrapper_tokens}
Splits:     {self.config.split_tokens}

Differences
-----------
{self.get_differences()}

------------------End Summary Report------------------
"""
        self.__say(summary_report)
        self.summary_report = summary_report
        if return_report:
            return summary_report

    ### Utilisation ###
    def parse_sql(
        self,
        input_sql: str,
        user_variables: dict | None = None,
        split_queries: bool = True,
    ) -> None:
        # Prepare
        self.__load_sql(input_sql=input_sql)
        self.__set_user_variables(user_variables)

        # Process Variables
        self.__supress_comments()
        self.__extract_variables()
        self.__set_final_variables()
        self.__identify_variable_replacements()
        self.__execute_variable_replacements()

        # Identify Regions & Splits
        self.__attach_scanner()
        self.scanner.scan_sql()
        self.regions = self.scanner.regions
        self.__detach_scanner()

        # Split Queries
        self.__split_into_queries(split_queries=split_queries)
        self.__organise_queries()

        # Summary Feedback
        self.get_summary_report(return_report=False)

    def reset(self) -> None:
        type(self)(platform=self.config.platform, feedback=self.feedback)
