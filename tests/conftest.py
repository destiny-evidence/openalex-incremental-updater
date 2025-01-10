"""Pytest configuration file."""

from collections.abc import AsyncIterator, Generator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

pytest_plugins = ["tests.fixtures.routers"]

pytest_plugins = ["tests.fixtures.routers"]


def get_app() -> FastAPI:
    """
    Return the FastAPI application.

    Returns:
        app (FastAPI): The FastAPI application.

    """
    from openalex_incremental_updater.main import app

    return app


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
) -> Generator[None, None, None]:
    """Set test environment variables."""
    monkeypatch.setenv("CORS_ORIGINS", '["http://test-host"]')
    monkeypatch.setenv("USER_EMAIL", "test@test")
    monkeypatch.setenv("PROJECT_NAME", "Test project name")
    monkeypatch.setenv("OPENALEX_API_KEY", "a-fake-key")  # pragma: allowlist secret
    yield
    monkeypatch.delenv("CORS_ORIGINS")
    monkeypatch.delenv("USER_EMAIL")
    monkeypatch.delenv("PROJECT_NAME")
    monkeypatch.delenv("OPENALEX_API_KEY")


@pytest.fixture
def sync_test_client(
    set_test_environment_variables: Generator[None, None, None],
) -> Generator[TestClient, None, None]:
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
    set_test_environment_variables: Generator[None, None, None],
) -> AsyncIterator[AsyncClient]:
    """Create a test client for synchronous tests."""
    app_instance = get_app()
    async with AsyncClient(
        transport=ASGITransport(app=app_instance), base_url="http://test"
    ) as client:
        yield client
