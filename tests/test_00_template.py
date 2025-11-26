import pytest  # noqa
from support import integrity  # noqa
from support.config import config  # noqa
from typing import Any


# Fixtures
@pytest.fixture(params=[None, "xxx"], ids=["test_none", "test_xxx"])
def arg_name_xxx(request: pytest.FixtureRequest) -> Any:
    return request.param


# Helpers
def helper_xxx() -> None:
    pass


### ====================== ###
### ---------TESTS---------###
### ====================== ###


def test_template() -> None:
    # with setup_test_credentials(alias=XXX, username=XXX) as credentials:
    #     pass
    pass


def test_with_params(arg_name_xxx: Any) -> None:  # with params
    pass


def test_template_main() -> None:
    # with setup_main_test_credentials() as credentials:
    #     connector = get_main_test_connector()
    pass


if __name__ == "__main__":
    pytest.main([__file__])
