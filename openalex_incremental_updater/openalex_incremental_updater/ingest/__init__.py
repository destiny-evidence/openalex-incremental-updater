"""OpenAlex data ingestion module."""

import asyncio
from enum import StrEnum

import httpx
from fastapi import status
from loguru import logger
from requests.exceptions import ReadTimeout


class CreatedOrUpdated(StrEnum):
    """Define the types of dates to filter by."""

    CREATED = "created"
    UPDATED = "updated"


class RetryTransport(httpx.AsyncHTTPTransport):
    """Define a an async client with retry capabilities."""

    def __init__(self, retries: int = 5, backoff_factor: float = 0.1) -> None:
        """Class constructor."""
        super().__init__()
        self.retries = retries
        self.backoff_factor = backoff_factor

    async def handle_async_request(
        self, request: httpx.Request, **kwargs: dict
    ) -> httpx.Response:
        """Define retry behaviour and attach to the session."""
        attempt = 0
        while attempt <= self.retries:
            try:
                logger.debug(f"request was {request}")
                url = request.url
                full_url = httpx.URL(url).copy_merge_params(kwargs.get("params", {}))
                logger.debug(f"Requesting {full_url}")
                response = await super().handle_async_request(request, **kwargs)
                response.request = request
                response.raise_for_status()
            except ReadTimeout as timeout_error:
                logger.warning(
                    f"Attempt {attempt+1}: ReadTimeout error occurred: {timeout_error}"
                )
                if attempt == self.retries:
                    logger.error(
                        f"Failed to fetch data from OpenAlex API after {self.retries} attempts."
                    )
                    return httpx.Response(
                        status_code=status.HTTP_408_REQUEST_TIMEOUT,
                        content=str(timeout_error),
                    )
                await asyncio.sleep(self.backoff_factor * 2**attempt)
                attempt += 1
            except (httpx.HTTPStatusError, httpx.RequestError) as error:
                logger.warning(
                    f"Attempt {attempt+1}: Failed to fetch data from OpenAlex API: {error}"
                )
                error_status_code_exists = (
                    error.response is not None
                    and getattr(error.response, "status_code", None) is not None
                )
                if (
                    error_status_code_exists
                    and error.response.status_code == status.HTTP_404_NOT_FOUND
                ):
                    return httpx.Response(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content=str(error),
                    )
                if attempt == self.retries:
                    logger.error(
                        f"Failed to fetch data from OpenAlex API after {self.retries} attempts."
                    )
                    return httpx.Response(
                        status_code=error.response.status_code
                        if error_status_code_exists
                        else 500,
                        content=str(error),
                    )
                await asyncio.sleep(self.backoff_factor * 2**attempt)
                attempt += 1
            else:
                return response
        return httpx.Response(
            status_code=500,
            content="Failed to fetch data from OpenAlex API.",
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
