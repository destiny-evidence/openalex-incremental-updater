import logging
from collections.abc import Generator

import pytest
from destiny_sdk.imports import ImportBatchRead, ImportRecordRead, ImportResultRead
from loguru import logger

from refresh_requester.config import Settings, get_settings


def pytest_configure():
    """
    Configure Pytest settings for the test suite.

    Currently just ignores any local .env files to ensure
    that tests don't pull in any unexpected environment variables.
    """
    Settings.model_config["env_file"] = ""

    # These models have circular forward references, so Pydantic defers schema building.
    # Rebuilding here ensures schemas are cached before any @freeze_time block
    # replaces datetime.datetime:

    ImportRecordRead.model_rebuild()
    ImportBatchRead.model_rebuild()
    ImportResultRead.model_rebuild()


@pytest.fixture
def caplog(caplog):
    class PropagateHandler(logging.Handler):
        def emit(self, record) -> None:
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), format="{message}")
    yield caplog
    logger.remove(handler_id)


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
    """Return Settings object with test environment variables."""
    return get_settings()
