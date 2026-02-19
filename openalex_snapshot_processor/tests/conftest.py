"""Pytest configuration file."""

import logging
from collections.abc import Generator
from typing import Any

import pytest
from loguru import logger

from openalex_snapshot_processor.config import Settings, get_settings

pytest_plugins = [
    "tests.fixtures.file_processing",
]


@pytest.fixture
def caplog(caplog: pytest.LogCaptureFixture) -> Generator[pytest.LogCaptureFixture]:
    class PropagateHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), format="{message}")
    yield caplog
    logger.remove(handler_id)


@pytest.fixture
def set_test_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Set test environment variables."""
    monkeypatch.setenv("SNAPSHOT_ROOT", "/fake/snapshot/root")
    monkeypatch.setenv("BLOB_BATCH_SIZE", "10000")
    monkeypatch.setenv("STORAGE_BLOB_ACCOUNT", "a-fake-blob-account")
    monkeypatch.setenv("STORAGE_BLOB_CONTAINER", "a-fake-blob-container")
    monkeypatch.setenv(
        "STORAGE_BLOB_ACCOUNT_KEY", "a-fake-blob-account-key"
    )  # pragma: allowlist secret
    monkeypatch.setenv(
        "REPOSITORY_ENDPOINT", "https://fake-destiny-repository-endpoint.com"
    )
    monkeypatch.setenv("TOKEN_ENDPOINT", "https://fake-token-endpoint.com")
    monkeypatch.setenv("APP_REGISTRATION_APP_ID", "a-fake-app-registration-app-id")
    monkeypatch.setenv(
        "APP_REGISTRATION_SECRET", "a-fake-app-registration-secret"
    )  # pragma: allowlist secret
    monkeypatch.setenv("TENANT_ID", "a-fake-tenant-id")
    monkeypatch.setenv("API_ENDPOINT", "https://fake-api-endpoint.com")

    yield
    monkeypatch.delenv("SNAPSHOT_ROOT")
    monkeypatch.delenv("BLOB_BATCH_SIZE")
    monkeypatch.delenv("STORAGE_BLOB_ACCOUNT")
    monkeypatch.delenv("STORAGE_BLOB_CONTAINER")
    monkeypatch.delenv("STORAGE_BLOB_ACCOUNT_KEY")
    monkeypatch.delenv("REPOSITORY_ENDPOINT")
    monkeypatch.delenv("TOKEN_ENDPOINT")
    monkeypatch.delenv("APP_REGISTRATION_APP_ID")
    monkeypatch.delenv("APP_REGISTRATION_SECRET")
    monkeypatch.delenv("TENANT_ID")
    monkeypatch.delenv("API_ENDPOINT")


@pytest.fixture(scope="session", autouse=True)
def anyio_backend() -> tuple[str, dict[str, Any]]:
    """Specify the anyio backend for async tests."""
    return "asyncio", {"use_uvloop": True}


@pytest.fixture
def test_settings(set_test_environment_variables) -> Settings:
    return get_settings()
