from collections.abc import Generator

import pytest

from refresh_requester.config import Settings, get_settings


@pytest.fixture
def set_test_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Set test environment variables."""
    monkeypatch.setenv("API_ENDPOINT", "http://test-host")
    monkeypatch.setenv(
        "STORAGE_BLOB_CONNECTION_STRING", "DefaultEndpointsProtocol=https;Test"
    )
    monkeypatch.setenv("STORAGE_BLOB_ACCOUNT", "Test account name")
    monkeypatch.setenv("STORAGE_BLOB_CONTAINER", "Test container name")
    yield
    monkeypatch.delenv("API_ENDPOINT")
    monkeypatch.delenv("STORAGE_BLOB_CONNECTION_STRING")
    monkeypatch.delenv("STORAGE_BLOB_ACCOUNT")
    monkeypatch.delenv("STORAGE_BLOB_CONTAINER")


@pytest.fixture
def test_settings(set_test_environment_variables) -> Settings:
    return get_settings()
