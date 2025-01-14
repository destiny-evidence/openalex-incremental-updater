"""Tests for the main module of the OpenAlex Incremental Updater."""

from fastapi import status
from fastapi.testclient import TestClient


def test_load_swagger_docs(sync_test_client: TestClient) -> None:
    """Test that the automatically generated Swagger documentation loads."""
    response = sync_test_client.get("/docs")
    assert response.status_code == status.HTTP_200_OK
