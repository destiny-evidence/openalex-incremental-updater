"""Tests for the common utilities used by the OpenAlex Incremental Updater API routers."""

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from openalex_incremental_updater.routers.utils import router as utils_router


def test_health_check() -> None:
    """Test the health check endpoint returns a HTTP_200_OK response."""
    app = FastAPI()
    app.include_router(utils_router)

    client = TestClient(app)
    response = client.get("/health-check")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
