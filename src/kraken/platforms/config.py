from typing import Any

from kraken.platforms.integrity import DEFAULT_NAME, initialise_platform
from kraken.support.readout import readout

CONFIG_ARRAYSIZE_SUPPORT = "arraysize_support"
CONFIG_MULTIPLE_DB_SUPPORT = "multiple_db_support"
CONFIG_SQL_LIBRARY = "sql_library"
CONFIG_DEFAULT_SQL_DRIVER = "default_sql_driver"
CONFIG_ADDITIONAL_WRAPPER_TOKENS = "additional_wrapper_tokens"
CONFIG_ADDITIONAL_SPLIT_TOKENS = "additional_split_tokens"
CONFIG_DECLARE_PATTERN = "declare_pattern"
CONFIG_DECLARE_USAGE_PATTERN = "declare_usage_pattern"
CONFIG_REMOVE_DECLARATION = "remove_declaration"
CONFIG_REPLACE_ALL_DECLARE_USAGES = "replace_all_declare_usages"
CONFIG_REMOVE_SPLIT_TOKEN = "remove_split_token"
CONFIG_FAST_EXECUTEMANY = "fast_executemany_support"

F_SLASH_SPLIT_TOKEN = r"/\s*(?:\n|$)"
WS = "\\s+"
WS_OPTIONAL = "\\s*"

_initialised_platforms = set()


def expand_whitespace(string: str, ws_regex: str = WS) -> str:
    return string.replace(" ", ws_regex)


platforms = {
    "oracle": {
        CONFIG_ARRAYSIZE_SUPPORT: True,
        CONFIG_MULTIPLE_DB_SUPPORT: False,
        CONFIG_DEFAULT_SQL_DRIVER: "oracledb",
        CONFIG_DECLARE_PATTERN: r"DEFINE\s+(\w+)\s*=\s*(.+)",
        CONFIG_DECLARE_USAGE_PATTERN: r"&([a-zA-Z][\w$#]*)",
        CONFIG_REMOVE_DECLARATION: True,
        CONFIG_REPLACE_ALL_DECLARE_USAGES: True,
        CONFIG_ADDITIONAL_SPLIT_TOKENS: [
            (F_SLASH_SPLIT_TOKEN, None),
            ("DECLARE", F_SLASH_SPLIT_TOKEN),
            ("BEGIN", F_SLASH_SPLIT_TOKEN),
            (expand_whitespace("CREATE PROCEDURE"), F_SLASH_SPLIT_TOKEN),
            (expand_whitespace("CREATE OR REPLACE PROCEDURE"), F_SLASH_SPLIT_TOKEN),
            (expand_whitespace("CREATE PACKAGE"), F_SLASH_SPLIT_TOKEN),
            (expand_whitespace("CREATE OR REPLACE PACKAGE"), F_SLASH_SPLIT_TOKEN),
            (expand_whitespace("CREATE TRIGGER"), F_SLASH_SPLIT_TOKEN),
            (expand_whitespace("CREATE OR REPLACE TRIGGER"), F_SLASH_SPLIT_TOKEN),
        ],
        CONFIG_REMOVE_SPLIT_TOKEN: True,
    },
    "mssql": {
        CONFIG_DECLARE_PATTERN: r"DECLARE\s+@(\w+)\s+[\w\(\)]+?\s*=\s*(.+)",
        CONFIG_DECLARE_USAGE_PATTERN: r"@(\w+)",
        CONFIG_ADDITIONAL_WRAPPER_TOKENS: [("[", "]")],
        CONFIG_FAST_EXECUTEMANY: True,
    },
    "informix": {CONFIG_SQL_LIBRARY: "pyodbc"},
    "cache": {CONFIG_SQL_LIBRARY: "pyodbc", CONFIG_REMOVE_SPLIT_TOKEN: True},
    "iris": {CONFIG_SQL_LIBRARY: "pyodbc", CONFIG_REMOVE_SPLIT_TOKEN: True},
    "postgresql": {
        CONFIG_DEFAULT_SQL_DRIVER: "postgresql",
        CONFIG_ADDITIONAL_SPLIT_TOKENS: [(r"\$\$", expand_whitespace(r"\$\$\s*;"))],
    },
    "mariadb": {
        CONFIG_DEFAULT_SQL_DRIVER: "mariadb",
        CONFIG_MULTIPLE_DB_SUPPORT: False,
        CONFIG_ADDITIONAL_WRAPPER_TOKENS: [("`", "`")],
    },
    "mysql": {
        CONFIG_DEFAULT_SQL_DRIVER: "mysql",
        CONFIG_MULTIPLE_DB_SUPPORT: False,
        CONFIG_ADDITIONAL_WRAPPER_TOKENS: [("`", "`")],
    },
    "duckdb": {
        CONFIG_DEFAULT_SQL_DRIVER: "duckdb",
        CONFIG_MULTIPLE_DB_SUPPORT: False,
        CONFIG_ADDITIONAL_WRAPPER_TOKENS: [("`", "`")],
    },
}


class PlatformConfig:
    def __init__(
        self, platform: str | None = DEFAULT_NAME, warn_if_unknown: bool = False
    ) -> None:
        self.platform: str = DEFAULT_NAME
        self.arraysize_support: bool = False
        self.multiple_db_support: bool = True
        self.sql_library: str = "sqlalchemy"
        self.default_sql_driver: str = "pyodbc"
        self.comment_tokens: list[tuple[str, ...]] = [
            ("--", "\n"),
            ("/*", "*/"),
        ]
        self.wrapper_tokens: list[tuple[str, ...]] = [
            ("'", "'"),
            ('"', '"'),
        ]
        self.additional_wrapper_tokens: list[tuple[str, ...]] | None = None
        self.split_tokens: list[tuple] = [(";", None)]
        self.additional_split_tokens: list[tuple[str, ...]] | None = None
        self.declare_pattern: str | None = None
        self.declare_usage_pattern: str | None = None
        self.remove_declaration: bool = False
        self.replace_all_declare_usages: bool = False
        self.remove_split_token: bool = False
        self.fast_executemany_support: bool = False

        if platform:
            self.__import_platform(platform, warn_if_unknown)
            self.__build_split_tokens()
            self.__build_wrapper_tokens()

    def __build_wrapper_tokens(self) -> None:
        if self.additional_wrapper_tokens:
            self.additional_wrapper_tokens = (
                self.additional_wrapper_tokens
                if isinstance(self.additional_wrapper_tokens, list)
                else [self.additional_wrapper_tokens]
            )
            self.wrapper_tokens.extend(self.additional_wrapper_tokens)

    def __build_split_tokens(self) -> None:
        if self.additional_split_tokens:
            self.additional_split_tokens = (
                self.additional_split_tokens
                if isinstance(self.additional_split_tokens, list)
                else [self.additional_split_tokens]
            )
            self.split_tokens.extend(self.additional_split_tokens)

    def __import_platform(self, platform: str, warn_if_unknown: bool = False) -> None:
        platform = platform.lower()
        platform_settings: dict[str, Any] = platforms.get(platform)  # type: ignore[assignment]
        if not platform_settings and warn_if_unknown:
            readout.warn(
                f"WARNING: Platform type '{platform}' unknown to Kraken. Parsers and connections will use default settings"
            )
            return

        if platform_settings:
            self.platform = platform
            for key, value in platform_settings.items():
                key = key.lower()
                if hasattr(self, key):
                    setattr(self, key, value)

        if platform not in _initialised_platforms:
            initialise_platform(platform)
            _initialised_platforms.add(platform)

    def __repr__(self) -> str:
        """
        Returns:
            str: A string representation of the PlatformConfig object.
        """
        return (
            f"PlatformConfig('{self.platform}'):"
            + "\n- "
            + "\n- ".join(
                [f"{attribute}: {value}" for attribute, value in self.__dict__.items()]
            )
        )


def get_platform_config(
    platform: str | None = DEFAULT_NAME, warn_if_unknown: bool = False
) -> PlatformConfig:
    return PlatformConfig(platform=platform, warn_if_unknown=warn_if_unknown)
