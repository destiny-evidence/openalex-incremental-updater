"""Tests for the common utilities used by the OpenAlex Incremental Updater API routers."""

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from openalex_incremental_updater.api.routers.utils import router as utils_router


@pytest.mark.anyio
async def test_health_check(
    set_test_environment_variables: None, async_test_client: AsyncClient
) -> None:
    """
    Test the health check endpoint returns a HTTP_200_OK response.

    We don't import app from main.py because we want to test the router in isolation.
    """
    app = FastAPI()
    app.include_router(utils_router)
    response = await async_test_client.get("/health-check/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
