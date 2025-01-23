"""Pytest configuration file."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest_plugins = ["tests.fixtures.routers"]


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

    def get_app() -> FastAPI:
        """
        Return the FastAPI application.

        Returns:
            app (FastAPI): The FastAPI application.

        """
        from openalex_incremental_updater.main import app

        return app

    client = TestClient(get_app())
    yield client
    client.close()
