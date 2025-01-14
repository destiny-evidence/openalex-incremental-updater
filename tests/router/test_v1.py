"""Tests for the v1 API router of the OpenAlex Incremental Updater."""

from fastapi import status
from fastapi.testclient import TestClient

from openalex_incremental_updater.routers.v1 import router as v1_router


def test_v1_router_health_check() -> None:
    """Check that the v1 router health check endpoint returns a HTTP_200_OK response."""
    expected_response = {"status": "ok"}
    client = TestClient(v1_router)
    response = client.get("/api/v1/health-check")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == expected_response
