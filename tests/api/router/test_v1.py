"""Tests for the v1 API router of the OpenAlex Incremental Updater."""

from datetime import datetime

from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from openalex_incremental_updater.ingest import CreatedOrUpdated


def test_v1_router_health_check(sync_test_client: TestClient) -> None:
    """Check that the v1 router health check endpoint returns a HTTP_200_OK response for the created mode."""
    expected_response = {"status": "ok"}
    response = sync_test_client.get("/api/v1/health-check")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == expected_response


def test_v1_openalex_works_ingest_created_success(
    sync_test_client: TestClient,
    mocker: MockerFixture,
    single_openalex_work_response: dict,
) -> None:
    """Check that the v1 router openalex_works_ingest endpoint returns a HTTP_200_OK response."""
    ingest_type = CreatedOrUpdated("created")
    limit = 1

    expected_response = single_openalex_work_response
    test_date = datetime.strptime(
        single_openalex_work_response["updated_date"][:10], "%Y-%m-%d"
    ).date()

    base_api_url = "/api/v1/openalex_works_ingest_from_date?"

    request_string = (
        base_api_url + f"fetch_date={test_date}&ingest_type={ingest_type}&limit={limit}"
    )
    mocked_openalex_call = mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_from_date",
        return_value=[expected_response],
    )

    response = sync_test_client.get(request_string)
    response_content = response.json()
    mocked_openalex_call.assert_called_once_with(
        fetch_date=test_date,
        created_or_updated=ingest_type,
        works_retrieved_limit=limit,
    )

    assert (
        response.status_code == status.HTTP_200_OK
    ), "Expect a HTTP_200 response on success"
    assert len(response_content) == 1, "Expect a single result in the response"
    assert (
        response_content[0] == expected_response
    ), "Expect the response to match the expected response"


def test_v1_openalex_works_ingest_updated_success(
    sync_test_client: TestClient,
    mocker: MockerFixture,
    single_openalex_work_response: dict,
) -> None:
    """Check that the v1 router openalex_works_ingest endpoint returns a HTTP_200_OK response for the updated mode."""
    ingest_type = CreatedOrUpdated("updated")
    limit = 1

    expected_response = single_openalex_work_response

    test_date = datetime.strptime(
        single_openalex_work_response["updated_date"][:10], "%Y-%m-%d"
    ).date()

    base_api_url = "/api/v1/openalex_works_ingest_from_date?"
    request_string = (
        base_api_url + f"fetch_date={test_date}&ingest_type={ingest_type}&limit={limit}"
    )
    mocked_openalex_call = mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_from_date",
        return_value=[expected_response],
    )

    response = sync_test_client.get(request_string)
    response_content = response.json()
    mocked_openalex_call.assert_called_once_with(
        fetch_date=test_date,
        created_or_updated=ingest_type,
        works_retrieved_limit=limit,
    )

    assert response.status_code == status.HTTP_200_OK, "Expect a HTTP_200 response."
    assert len(response_content) == 1, "Expect a single result in the response"
    assert (
        response_content[0] == expected_response
    ), "Expect the response to match the expected response"


def test_v1_openalex_works_ingest_open_filter(
    sync_test_client: TestClient,
    mocker: MockerFixture,
    single_openalex_work_response: dict,
) -> None:
    """Check that the v1 router openalex_works_ingest endpoint returns a HTTP_200_OK response for the updated mode."""
    limit = 1

    expected_response = single_openalex_work_response

    test_date = datetime.strptime(
        single_openalex_work_response["updated_date"][:10], "%Y-%m-%d"
    ).date()

    test_filter_string = f"from_created_date:{test_date}"

    base_request_url = "/api/v1/openalex_works_open_filter?"
    test_request_string = (
        base_request_url + f"openalex_query_string={test_filter_string}&limit={limit}"
    )

    mocked_openalex_call = mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_open_filter",
        return_value=[expected_response],
    )
    response = sync_test_client.get(test_request_string)
    response_content = response.json()
    mocked_openalex_call.assert_called_once_with(
        openalex_filter=test_filter_string,
        works_retrieved_limit=1,
    )

    assert response.status_code == status.HTTP_200_OK, "Expect a HTTP_200 response."
    assert len(response_content) == 1, "Expect a single result in the response"
    assert (
        response_content[0] == expected_response
    ), "Expect the response to match the expected response"
