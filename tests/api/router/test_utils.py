"""Tests for the common utilities used by the OpenAlex Incremental Updater API routers."""

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from openalex_incremental_updater.api.routers.utils import router as utils_router


def test_health_check(set_test_environment_variables: None) -> None:
    """
    Test the health check endpoint returns a HTTP_200_OK response.

    We don't import app from main.py because we want to test the router in isolation.
    """
    app = FastAPI()
    app.include_router(utils_router)

    client = TestClient(app)
    response = client.get("/health-check")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
