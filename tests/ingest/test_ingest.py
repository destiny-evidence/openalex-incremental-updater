import pytest
import responses
from fastapi import status

from openalex_incremental_updater.ingest import RetrySession


@pytest.mark.parametrize(
    "error_status",
    [
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT,
    ],
)
@responses.activate
def test_retry_on_server_error(error_status: int) -> None:
    url = "https://a-test-url"
    number_of_failures = 2
    expected_calls = number_of_failures + 1

    for _ in range(number_of_failures):
        responses.add(responses.GET, url, status=error_status)
    responses.add(responses.GET, url, status=status.HTTP_200_OK)

    session = RetrySession(retries=expected_calls, backoff_factor=0)
    response = session.get(url)

    assert response.status_code == status.HTTP_200_OK, "Expect a successful response."
    assert (
        len(responses.calls) == expected_calls
    ), "Expect 3 calls to the URL, with the final one succeeding."


@responses.activate
def test_no_retry_on_404_not_found() -> None:
    url = "https://a-test-url"
    # Throw a 404 not found error, and do not retry
    responses.add(responses.GET, url, status=status.HTTP_404_NOT_FOUND)
    responses.add(responses.GET, url, status=status.HTTP_200_OK)

    session = RetrySession(retries=3, backoff_factor=0)
    response = session.get(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND, "Expect a 404 response."
    assert len(responses.calls) == 1, "Expect 1 call to the URL, with no retries."
