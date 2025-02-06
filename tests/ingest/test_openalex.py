import pytest
import requests_mock
from fastapi import status

from openalex_incremental_updater.ingest import CreatedOrUpdated
from openalex_incremental_updater.ingest.openalex import (
    OpenAlexDataFetcher,
    UpstreamOpenAlexError,
)


def test_open_filter_call_success(double_openalex_work_response: list[dict]) -> None:
    fetcher = OpenAlexDataFetcher()
    expected_response = {
        "meta": {
            "count": 1,
            "next_cursor": None,
        },
        "results": double_openalex_work_response,
    }
    test_date = double_openalex_work_response[0]["publication_date"]
    test_filter = f"from_created_date:{test_date}"

    with requests_mock.Mocker() as mocked_openalex_call:
        mocked_openalex_call.register_uri(
            "GET", "https://api.openalex.org/works", json=expected_response
        )
        response = fetcher.fetch_works_open_filter(
            openalex_filter=test_filter, works_retrieved_limit=1
        )

    assert mocked_openalex_call.call_count == 1
    assert response == double_openalex_work_response


@pytest.mark.parametrize(
    "test_error_status_code",
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT,
    ],
)
def test_open_filter_call_openalex_error(
    double_openalex_work_response: list[dict], test_error_status_code: int
) -> None:
    fetcher = OpenAlexDataFetcher()
    expected_response = {
        "meta": {
            "count": 1,
            "next_cursor": None,
        },
        "results": double_openalex_work_response,
    }
    test_date = double_openalex_work_response[0]["publication_date"]
    test_filter = f"from_created_date:{test_date}"

    with requests_mock.Mocker() as mocked_openalex_call:
        mocked_openalex_call.register_uri(
            "GET",
            "https://api.openalex.org/works",
            json=expected_response,
            status_code=test_error_status_code,
        )
        with pytest.raises(UpstreamOpenAlexError) as invalid_url_error:
            fetcher.fetch_works_open_filter(
                openalex_filter=test_filter, works_retrieved_limit=1
            )

    assert isinstance(invalid_url_error.value, UpstreamOpenAlexError)
    assert str(test_error_status_code) in str(
        invalid_url_error.value
    ), "Check that the error message contains the expected status code."


@pytest.mark.parametrize(
    "created_or_updated", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
def test_fetch_works_from_date_call_success(
    double_openalex_work_response: list[dict], created_or_updated: CreatedOrUpdated
) -> None:
    fetcher = OpenAlexDataFetcher()
    expected_response = {
        "meta": {
            "count": 1,
            "next_cursor": None,
        },
        "results": double_openalex_work_response,
    }
    test_date = double_openalex_work_response[0]["publication_date"]

    with requests_mock.Mocker() as mocked_openalex_call:
        mocked_openalex_call.register_uri(
            "GET", "https://api.openalex.org/works", json=expected_response
        )
        response = fetcher.fetch_works_from_date(
            fetch_date=test_date,
            created_or_updated=created_or_updated,
            works_retrieved_limit=1,
        )

    assert mocked_openalex_call.call_count == 1
    assert response == double_openalex_work_response


@pytest.mark.parametrize(
    "created_or_updated", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
@pytest.mark.parametrize(
    "test_error_status_code",
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT,
    ],
)
def test_fetch_works_from_date_call_openalex_error(
    double_openalex_work_response: list[dict],
    created_or_updated: CreatedOrUpdated,
    test_error_status_code: int,
) -> None:
    fetcher = OpenAlexDataFetcher()
    expected_response = {
        "meta": {
            "count": 1,
            "next_cursor": None,
        },
        "results": double_openalex_work_response,
    }
    test_date = double_openalex_work_response[0]["publication_date"]

    with requests_mock.Mocker() as mocked_openalex_call:
        mocked_openalex_call.register_uri(
            "GET",
            "https://api.openalex.org/works",
            json=expected_response,
            status_code=test_error_status_code,
        )
        with pytest.raises(UpstreamOpenAlexError) as invalid_url_error:
            fetcher.fetch_works_from_date(
                fetch_date=test_date,
                created_or_updated=created_or_updated,
                works_retrieved_limit=1,
            )

    assert isinstance(invalid_url_error.value, UpstreamOpenAlexError)
    assert str(test_error_status_code) in str(
        invalid_url_error.value
    ), "Check that the error message contains the expected status code."


def test_fetch_works_free_tier_success(
    double_openalex_work_response: list[dict],
) -> None:
    fetcher = OpenAlexDataFetcher()
    expected_response = {
        "meta": {
            "count": 1,
            "next_cursor": None,
        },
        "results": double_openalex_work_response,
    }

    with requests_mock.Mocker() as mocked_openalex_call:
        mocked_openalex_call.register_uri(
            "GET", "https://api.openalex.org/works", json=expected_response
        )
        response = fetcher.fetch_works_free_tier()

    assert mocked_openalex_call.call_count == 1
    assert response == double_openalex_work_response


@pytest.mark.parametrize(
    "test_error_status_code",
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT,
    ],
)
def test_fetch_works_free_tier_openalex_error(
    double_openalex_work_response: list[dict], test_error_status_code: int
) -> None:
    fetcher = OpenAlexDataFetcher()
    expected_response = {
        "meta": {
            "count": 1,
            "next_cursor": None,
        },
        "results": double_openalex_work_response,
    }

    with requests_mock.Mocker() as mocked_openalex_call:
        mocked_openalex_call.register_uri(
            "GET",
            "https://api.openalex.org/works",
            json=expected_response,
            status_code=test_error_status_code,
        )
        with pytest.raises(UpstreamOpenAlexError) as invalid_url_error:
            fetcher.fetch_works_free_tier()

    assert isinstance(invalid_url_error.value, UpstreamOpenAlexError)
    assert str(test_error_status_code) in str(
        invalid_url_error.value
    ), "Check that the error message contains the expected status code."
