import httpx
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


@pytest.mark.anyio
async def test_session_get_readtimeout_is_not_retried(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that a ReadTimeout error raised by session.get is not retried in the handle_async_request method.

    ReadTimeout handling, retry logic and logging is handled by the
    `get_json_with_retry` method, which is tested separately.
    """
    url = "https://a-test-url"
    expected_calls = 1
    expected_warning_logs = 0

    async with respx.mock:
        with caplog.at_level("WARNING"):
            route = respx.get(url).mock(
                side_effect=httpx.ReadTimeout(
                    "ReadTimeout error simulated for testing."
                )
            )

            async with AsyncRetryClient(retries=3, backoff_factor=0) as session:
                with pytest.raises(httpx.ReadTimeout):
                    await session.get(url)

            assert (
                route.call_count == expected_calls
            ), "Expect 1 call to the URL, with no retries at the session.get level."
            assert (
                len(caplog.records) == expected_warning_logs
            ), "Expect no warning logs for ReadTimeout at the session.get level."


@pytest.mark.anyio
async def test_get_json_with_retry_retries_request_time_readtimeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    url = "https://a-test-url"
    number_of_failures = 2
    configured_retries = 3
    test_cursor = "a-test-cursor"
    expected_calls = number_of_failures + 1
    expected_payload = {
        "meta": {"count": 1, "next_cursor": None},
        "results": [],
    }

    async with respx.mock:
        with caplog.at_level("WARNING"):
            route = respx.get(url).mock(
                side_effect=[
                    httpx.ReadTimeout("ReadTimeout error simulated for testing."),
                    httpx.ReadTimeout("ReadTimeout error simulated for testing."),
                    Response(status.HTTP_200_OK, json=expected_payload),
                ]
            )

            async with AsyncRetryClient(
                retries=configured_retries, backoff_factor=0
            ) as session:
                response_json = await session.get_json_with_retry(
                    url,
                    instance_id="test1234",
                    cursor=test_cursor,
                )

    assert (
        route.call_count == expected_calls
    ), "Expect to see retries due to ReadTimeoutError with the final call succeeding."
    assert (
        response_json == expected_payload
    ), "Expect the final response to be the expected payload."
    assert f"ReadTimeout while fetching cursor {test_cursor}" in str(caplog.text)


@pytest.mark.anyio
async def test_http_status_error_with_response_is_handled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    url = "https://a-test-url"

    dummy_request = httpx.Request("GET", url)
    dummy_response = Response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, request=dummy_request
    )
    http_status_exc = httpx.HTTPStatusError(
        "HTTP error simulated for testing.",
        request=dummy_request,
        response=dummy_response,
    )

    async with respx.mock:
        with caplog.at_level("WARNING"):
            respx.get(url).mock(
                side_effect=[
                    http_status_exc,
                    Response(status.HTTP_200_OK),
                ]
            )

            async with AsyncRetryClient(retries=2, backoff_factor=0) as session:
                response = await session.get(url)

    assert "HTTP error simulated for testing" in str(
        caplog.text
    ), "Expect HTTPStatusError to be logged."
    assert response.status_code == status.HTTP_200_OK, "Expect a successful response."


@pytest.mark.anyio
async def test_get_json_with_retry_retries_parse_time_readtimeout(
    mocker: MockerFixture,
) -> None:
    expected_payload = {
        "meta": {"count": 1, "next_cursor": None},
        "results": [],
    }
    configured_retries = 1
    expected_get_calls = configured_retries + 1

    first_response = mocker.Mock(spec=httpx.Response)
    first_response.raise_for_status.return_value = None
    first_response.json.side_effect = httpx.ReadTimeout(
        "ReadTimeout error simulated for testing."
    )

    second_response = mocker.Mock(spec=httpx.Response)
    second_response.raise_for_status.return_value = None
    second_response.json.return_value = expected_payload

    async with AsyncRetryClient(
        retries=configured_retries, backoff_factor=0
    ) as session:
        mocked_get = mocker.patch.object(
            session,
            "get",
            new=mocker.AsyncMock(side_effect=[first_response, second_response]),
        )

        result = await session.get_json_with_retry(
            "https://a-test-url",
            instance_id="test1234",
            cursor="*",
        )

    assert result == expected_payload
    assert mocked_get.call_count == expected_get_calls
