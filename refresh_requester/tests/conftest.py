from collections.abc import Generator

import pytest

from refresh_requester.config import Settings, get_settings


@pytest.fixture
def set_test_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Set test environment variables."""
    monkeypatch.setenv("API_ENDPOINT", "http://test-host")
    monkeypatch.setenv("STORAGE_BLOB_ACCOUNT", "Test account name")
    monkeypatch.setenv("STORAGE_BLOB_ACCOUNT_KEY", "This-is-a-test-key")
    monkeypatch.setenv("STORAGE_BLOB_CONTAINER", "Test container name")
    monkeypatch.setenv("TOKEN_ENDPOINT", "http://test-host/auth_token")
    monkeypatch.setenv("REPOSITORY_ENDPOINT", "http://test-host/repository-api")
    yield
    monkeypatch.delenv("API_ENDPOINT")
    monkeypatch.delenv("STORAGE_BLOB_ACCOUNT")
    monkeypatch.delenv("STORAGE_BLOB_ACCOUNT_KEY")
    monkeypatch.delenv("STORAGE_BLOB_CONTAINER")
    monkeypatch.delenv("TOKEN_ENDPOINT")
    monkeypatch.delenv("REPOSITORY_ENDPOINT")


@pytest.fixture
def test_settings(set_test_environment_variables) -> Settings:
    return get_settings()
