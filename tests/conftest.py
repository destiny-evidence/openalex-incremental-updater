"""Pytest configuration file."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def set_test_environment_variables() -> Generator[None, None, None]:
    """Set test environment variables."""
    os.environ["CORS_ORIGINS"] = '["http://test-host"]'
    os.environ["USER_EMAIL"] = "test@test"
    os.environ["PROJECT_NAME"] = "Test project name"
    yield
    os.environ.pop("CORS_ORIGINS")
    os.environ.pop("PROJECT_NAME")
    os.environ.pop("USER_EMAIL")


@pytest.fixture(scope="session")
def sync_test_client(
    set_test_environment_variables: None,
) -> Generator[TestClient, None, None]:
    """Create a test client for synchronous tests."""
    from openalex_incremental_updater.main import app

    client = TestClient(app)
    yield client
    client.close()
