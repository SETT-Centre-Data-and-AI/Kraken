from typing import Iterator

import keyring
import pytest
from support.config import MAIN_TEST_ALIAS, OTHER_TEST_ALIAS, config

from kraken.credentials.integrity import DEFAULT_USERNAME_TOKEN


# Check Helpers
def check_for_remaining_test_credentials() -> str:
    # ensure main test credentials have been removed
    errors = []
    main_test = config.main_test
    if not main_test.fallback:
        for token in [main_test.username, DEFAULT_USERNAME_TOKEN]:
            if keyring.get_password(MAIN_TEST_ALIAS, token):
                errors.append(("Main Test", MAIN_TEST_ALIAS, token))

    # ensure secondary test credentials have been removed
    secondary_tests = config.secondary_tests
    for _platform, tests in secondary_tests.items():
        for test in tests:
            alias = OTHER_TEST_ALIAS.format(suffix=test.alias)
            username = test.username
            for token in [username, DEFAULT_USERNAME_TOKEN]:
                if keyring.get_password(alias, token):
                    errors.append(("Secondary Test", alias, token))

    remaining = (
        "Test credentials appear not to have been cleaned up:"
        + " - "
        + "\n - ".join(
            f"{test_type}: '{username}@{alias}'"
            for test_type, alias, username in errors
        )
        if errors
        else ""
    )
    return remaining


def check_for_deleted_source_credentials() -> str:
    errors = []

    # ensure main credentials intact
    main_test = config.main_test
    if not main_test.fallback:
        for token in [main_test.username, DEFAULT_USERNAME_TOKEN]:
            if not keyring.get_password(main_test.alias, token):
                errors.append(("Main Test", main_test.alias, token))

    # ensure secondary credentials intact
    secondary_tests = config.secondary_tests
    for _platform, tests in secondary_tests.items():
        for test in tests:
            if not keyring.get_password(test.alias, test.username):
                errors.append(("Secondary Test", test.alias, test.username))
                pass
    missing = (
        "Source credentials appear to be deleted:"
        + " - "
        + "\n - ".join(
            f"{test_type}:' {username}@{alias}'"
            for test_type, alias, username in errors
        )
        if errors
        else ""
    )
    return missing


# Cleanup once all tests complete
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_credentials() -> Iterator[None]:
    """
    Cleanup once all tests complete
    """
    # No startup

    yield

    # Cleanup & checks
    config.cleanup()
    errors: list[str] = []
    remaining = check_for_remaining_test_credentials()
    missing = check_for_deleted_source_credentials()

    for issue in [remaining, missing]:
        if issue:
            errors.append(issue)

    assert not errors, "Errors in cleanup:\n" + "\n".join(errors)
