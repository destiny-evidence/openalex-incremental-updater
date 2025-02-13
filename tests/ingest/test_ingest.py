import pytest
import respx
from fastapi import status
from httpx import Response
from pytest_mock import MockerFixture

from openalex_incremental_updater.ingest import AsyncRetryClient


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize(
    "error_status",
    [
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT,
    ],
)
async def test_retry_on_server_error(mocker: MockerFixture, error_status: int) -> None:
    url = "https://a-test-url/"
    number_of_failures = 2
    expected_calls = number_of_failures + 1

    async with respx.mock:
        route = respx.get(url).mock(
            side_effect=[
                Response(error_status),
                Response(error_status),
                Response(status.HTTP_200_OK),
            ]
        )

        async with AsyncRetryClient(
            retries=expected_calls, backoff_factor=0
        ) as session:
            response = await session.get(url)

    assert response.status_code == status.HTTP_200_OK, "Expect a successful response."
    assert (
        route.call_count == expected_calls
    ), "Expect 3 calls to the URL, with the final one succeeding."


@pytest.mark.anyio
@respx.mock
async def test_no_retry_on_404_not_found() -> None:
    url = "https://a-test-url"

    async with respx.mock:
        route = respx.get(url).mock(
            side_effect=[
                Response(status.HTTP_404_NOT_FOUND),
                Response(status.HTTP_200_OK),
            ]
        )

        async with AsyncRetryClient(retries=3, backoff_factor=0) as session:
            response = await session.get(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND, "Expect a 404 response."
    assert route.call_count == 1, "Expect 1 call to the URL, with no retries."
