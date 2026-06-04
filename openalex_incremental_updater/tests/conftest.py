"""Pytest configuration file."""

import logging
from collections.abc import AsyncIterator, Generator
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from freezegun import freeze_time
from httpx import ASGITransport, AsyncClient
from loguru import logger

from openalex_incremental_updater.core.config import Settings, get_settings
from openalex_incremental_updater.core.job_state import JobManager, report_status
from openalex_incremental_updater.ingest import CreatedOrUpdated

pytest_plugins = [
    "tests.fixtures.routers",
    "tests.fixtures.destiny_schema",
    "tests.fixtures.openalex_schema",
    "tests.fixtures.auth",
    "tests.fixtures.models",
]


@pytest.fixture
def caplog(caplog: pytest.LogCaptureFixture) -> Generator[pytest.LogCaptureFixture]:
    class PropagateHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), format="{message}")
    yield caplog
    logger.remove(handler_id)


def get_app() -> FastAPI:
    """
    Return the FastAPI application.

    Returns:
        app (FastAPI): The FastAPI application.

    """
    from openalex_incremental_updater.main import app

    return app


@pytest.fixture
def set_test_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Set test environment variables."""
    monkeypatch.setenv("CORS_ORIGINS", '["http://test-host"]')
    monkeypatch.setenv("USER_EMAIL", "test@test")
    monkeypatch.setenv("PROJECT_NAME", "Test project name")
    monkeypatch.setenv("OPENALEX_API_KEY", "a-fake-key")  # pragma: allowlist secret
    monkeypatch.setenv("AZURE_AUTH_ENVIRONMENT_ID", "a-fake-id")
    monkeypatch.setenv("APP_REGISTRATION_APP_ID", "a-fake-id")
    monkeypatch.setenv(
        "APP_REGISTRATION_SECRET", "a-fake-secret"
    )  # pragma: allowlist secret
    monkeypatch.setenv("TENANT_ID", "a-fake-id")
    monkeypatch.setenv("STORAGE_BLOB_ACCOUNT", "a-fake-blob-account")
    monkeypatch.setenv("STORAGE_BLOB_CONTAINER", "a-fake-blob-container")
    yield
    monkeypatch.delenv("CORS_ORIGINS")
    monkeypatch.delenv("USER_EMAIL")
    monkeypatch.delenv("PROJECT_NAME")
    monkeypatch.delenv("OPENALEX_API_KEY")
    monkeypatch.delenv("AZURE_AUTH_ENVIRONMENT_ID")
    monkeypatch.delenv("APP_REGISTRATION_APP_ID")
    monkeypatch.delenv("APP_REGISTRATION_SECRET")
    monkeypatch.delenv("TENANT_ID")
    monkeypatch.delenv("STORAGE_BLOB_ACCOUNT")
    monkeypatch.delenv("STORAGE_BLOB_CONTAINER")


@pytest.fixture
def sync_test_client(
    set_test_environment_variables: Generator[None],
) -> Generator[TestClient]:
    """Create a test client for synchronous tests."""
    client = TestClient(get_app())
    yield client
    client.close()


@pytest.fixture(scope="session", autouse=True)
def anyio_backend() -> tuple[str, dict[str, Any]]:
    """Specify the anyio backend for async tests."""
    return "asyncio", {"use_uvloop": True}


@pytest.fixture
async def async_test_client(
    set_test_environment_variables: Generator[None],
) -> AsyncIterator[AsyncClient]:
    """Create a test client for synchronous tests."""
    app_instance = get_app()
    async with AsyncClient(
        transport=ASGITransport(app=app_instance), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def test_settings(set_test_environment_variables) -> Settings:
    return get_settings()


@pytest.fixture
@freeze_time("2025-08-18")
def job_report_dict() -> dict:
    """Fixture to create a job report function."""
    start_date = datetime.now(ZoneInfo("UTC")).date()
    end_date = datetime.now(ZoneInfo("UTC")).date()
    job_manager = JobManager()
    ingest_type = CreatedOrUpdated("created")
    job_id = job_manager.create(
        meta={
            "start_date": start_date,
            "end_date": end_date,
            "ingest_type": ingest_type,
            "limit": None,
        }
    )
    return {
        "job_manager": job_manager,
        "job_id": job_id,
        "report": report_status(job_manager, job_id),
    }
