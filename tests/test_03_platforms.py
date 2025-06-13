import pytest

from kraken.platforms.config import PlatformConfig


def test_split_tokens_extension():
    """
    Tests that additional split tokens are correctly added to the
    `split_tokens` attribute for the `oracle` platform.
    """
    config = PlatformConfig("oracle")
    additional_split = config.additional_split_tokens
    assert additional_split is not None
    assert len(additional_split) > 0
    assert config.split_tokens[-1][0] == additional_split[-1][0]


def test_wrapper_tokens_extension():
    """
    Tests that additional wrapper tokens are correctly added to the
    `wrapper_tokens` attribute for the `mssql` platform.
    """
    config = PlatformConfig("mssql")
    additional_wrapper = config.additional_wrapper_tokens
    assert additional_wrapper == [("[", "]")]


if __name__ == "__main__":
    pytest.main([__file__])
