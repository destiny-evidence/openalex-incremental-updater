"""OpenAlex data ingestion module."""

import asyncio
from enum import StrEnum
from types import TracebackType

import httpx
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
        while attempt < self.retries:
            try:
                response = await super().handle_async_request(request)
                response.raise_for_status()
            except (httpx.HTTPStatusError, httpx.RequestError) as error:
                logger.warning(
                    f"Attempt {attempt+1}: Failed to fetch data from OpenAlex API: {error}"
                )
                if attempt == self.retries - 1:
                    logger.error(
                        f"Failed to fetch data from OpenAlex API after {self.retries} attempts."
                    )
                    return httpx.Response(status_code=500, content=str(error))
                await asyncio.sleep(self.backoff_factor * 2**attempt)
                attempt += 1
            return response

        return httpx.Response(
            status_code=500,
            content=f"Failed to fetch data from OpenAlex API after {self.retries} retries",
        )


class AsyncRetryClient:
    """Async context manager for an httpx.AsyncClient with retry capabilities."""

    def __init__(self, retries: int = 5, backoff_factor: float = 0.1) -> None:
        """
        Class constructor.

        Args:
            retries (int, optional): Number of retries. Defaults to 5.
            backoff_factor (float, optional): Backoff factor for retrying. Defaults to 0.1.

        """
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.transport = RetryTransport(
            retries=self.retries, backoff_factor=self.backoff_factor
        )
        self.client = httpx.AsyncClient(transport=self.transport)

    async def __aenter__(self) -> httpx.AsyncClient:
        """
        Initalise the client in context manager.

        Returns:
            httpx.AsyncClient: An httpx.AsyncClient with retry capabilities.

        """
        return httpx.AsyncClient(
            transport=RetryTransport(
                retries=self.retries, backoff_factor=self.backoff_factor
            )
        )

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the client in context manager."""
        await self.client.aclose()
