"""Tests for the main module of the OpenAlex Incremental Updater."""

from fastapi import status
from fastapi.testclient import TestClient

from openalex_incremental_updater.main import app

client = TestClient(app)


def test_load_swagger_docs() -> None:
    """Test that the automatically generated Swagger documentation loads."""
    response = client.get("/docs")
    assert response.status_code == status.HTTP_200_OK
