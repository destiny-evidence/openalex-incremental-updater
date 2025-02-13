"""OpenAlex data ingestion module."""

import asyncio
from enum import StrEnum

import httpx
from fastapi import status
from loguru import logger


class CreatedOrUpdated(StrEnum):
    """Define the types of dates to filter by."""

    CREATED = "created"
    UPDATED = "updated"


class RetryTransport(httpx.AsyncHTTPTransport):
    """Define a requests.Session with retry capabilities."""

    def __init__(self, retries: int = 5, backoff_factor: float = 0.1) -> None:
        """Class constructor."""
        super().__init__()
        self.retries = retries
        self.backoff_factor = backoff_factor

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Define retry behaviour and attach to the session."""
        attempt = 0
        while attempt <= self.retries:
            try:
                response = await super().handle_async_request(request)
                try:
                    if not response.request:
                        response.request = request
                except RuntimeError:
                    response.request = request
                response.raise_for_status()
            except (httpx.HTTPStatusError, httpx.RequestError) as error:
                logger.warning(
                    f"Attempt {attempt+1}: Failed to fetch data from OpenAlex API: {error}"
                )
                if response.status_code == status.HTTP_404_NOT_FOUND:
                    return response
                if attempt == self.retries:
                    logger.error(
                        f"Failed to fetch data from OpenAlex API after {self.retries} attempts."
                    )
                    return httpx.Response(
                        status_code=response.status_code,
                        content=str(error),
                        request=request,
                    )
                await asyncio.sleep(self.backoff_factor * 2**attempt)
                attempt += 1
            else:
                return response
        return httpx.Response(
            status_code=500,
            content="Failed to fetch data from OpenAlex API.",
            request=request,
        )


class AsyncRetryClient(httpx.AsyncClient):
    """Async context manager for an httpx.AsyncClient with retry capabilities."""

    def __init__(self, retries: int = 5, backoff_factor: float = 0.1) -> None:
        """
        Class constructor.

        Args:
            retries (int, optional): Number of retries. Defaults to 5.
            backoff_factor (float, optional): Backoff factor for retrying. Defaults to 0.1.

        """
        super().__init__(
            transport=RetryTransport(retries=retries, backoff_factor=backoff_factor)
        )
