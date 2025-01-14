"""Pytest configuration file."""

import os

import pytest


@pytest.fixture(scope="session")
def set_test_environment_variables() -> None:
    """Set test environment variables."""
    os.environ["CORS_ORIGINS"] = '["http://test-host"]'
    os.environ["PROJECT_NAME"] = "Test project name"
