from collections.abc import Generator
from datetime import date

import httpx
import pytest
import respx
from fastapi import status
from freezegun import freeze_time

from openalex_incremental_updater.ingest import CreatedOrUpdated
from openalex_incremental_updater.ingest.openalex import (
    OpenAlexDataFetcher,
    UpstreamOpenAlexError,
)
from openalex_incremental_updater.models.destiny import convert_openalex_to_destiny


@pytest.mark.anyio
@pytest.mark.parametrize(
    "created_or_updated", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
async def test_fetch_works_filter_date_range_call_success(
    double_openalex_work_response: list[dict], created_or_updated: CreatedOrUpdated
) -> None:
    fetcher = OpenAlexDataFetcher(retries=0)
    expected_response = {
        "meta": {
            "count": 1,
            "next_cursor": None,
        },
        "results": double_openalex_work_response,
    }
    test_date = double_openalex_work_response[0]["publication_date"]
    mock_url = "https://api.openalex.org/works"

    openalex_query = OpenAlexDataFetcher.build_range_query(
        test_date, test_date, created_or_updated
    )

    with respx.mock:
        mocked_call = respx.get(mock_url).mock(
            return_value=httpx.Response(status.HTTP_200_OK, json=expected_response)
        )

        response = fetcher.fetch_works_filter(
            openalex_filter=openalex_query,
        )
        results = [item async for item in response]
        flat_results = [work for batch in results for work in batch]
        assert mocked_call.call_count == 1
        assert flat_results == [
            convert_openalex_to_destiny(work) for work in double_openalex_work_response
        ]


@pytest.mark.anyio
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
async def test_fetch_works_filter_date_range_call_openalex_error(
    double_openalex_work_response: list[dict],
    created_or_updated: CreatedOrUpdated,
    test_error_status_code: int,
) -> None:
    fetcher = OpenAlexDataFetcher(retries=0)
    expected_response = {
        "meta": {
            "count": 1,
            "next_cursor": None,
        },
        "results": double_openalex_work_response,
    }
    test_date = double_openalex_work_response[0]["publication_date"]
    mock_url = "https://api.openalex.org/works"

    test_openalex_query = OpenAlexDataFetcher.build_range_query(
        test_date, test_date, created_or_updated
    )

    with respx.mock:
        respx.get(mock_url).mock(
            return_value=httpx.Response(test_error_status_code, json=expected_response)
        )
        response = fetcher.fetch_works_filter(
            openalex_filter=test_openalex_query,
        )
        with pytest.raises(UpstreamOpenAlexError) as invalid_url_error:
            _result = [item async for item in response]

        assert isinstance(invalid_url_error.value, UpstreamOpenAlexError)
        assert str(test_error_status_code) in str(
            invalid_url_error.value
        ), "Check that the error message contains the expected status code."


@freeze_time("2025-08-19")
@pytest.mark.parametrize(
    "ingest_type", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
def test_build_range_query(
    ingest_type: CreatedOrUpdated, set_test_environment_variables: Generator
):
    test_start_date = date.today()
    test_end_date = test_start_date
    fetcher = OpenAlexDataFetcher()
    expected_output = f"from_{ingest_type.value}_date:{test_start_date.isoformat()},to_{ingest_type.value}_date:{test_end_date.isoformat()}"
    query = fetcher.build_range_query(test_start_date, test_end_date, ingest_type)

    assert query == expected_output
