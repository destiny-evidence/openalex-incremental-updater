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

    expected_result = single_openalex_work_response
    test_date = datetime.strptime(
        single_openalex_work_response["created_date"], "%Y-%m-%d"
    ).date()
    expected_response = {
        "message": f"Data fetched from {test_date} with method: {ingest_type}. Ingested successfully.",
        "results": expected_result,
    }

    request_string = f"/api/v1/openalex_works_ingest?fetch_date={test_date}&ingest_type={ingest_type}&limit={limit}"
    mocked_openalex_call = mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_data_from_date",
        return_value=expected_result,
    )

    response = sync_test_client.get(request_string)
    response_content = response.json()
    mocked_openalex_call.assert_called_once_with(
        fetch_date=test_date,
        created_or_updated=ingest_type,
        works_retrieved_limit=limit,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response_content["message"] == expected_response["message"]
    assert response_content["results"] == expected_response["results"]


def test_v1_openalex_works_ingest_updated_success(
    sync_test_client: TestClient,
    mocker: MockerFixture,
    single_openalex_work_response: dict,
) -> None:
    """Check that the v1 router openalex_works_ingest endpoint returns a HTTP_200_OK response for the updated mode."""
    ingest_type = CreatedOrUpdated("updated")
    limit = 1

    expected_result = single_openalex_work_response

    test_date = datetime.strptime(
        single_openalex_work_response["updated_date"][:10], "%Y-%m-%d"
    ).date()
    expected_response = {
        "message": f"Data fetched from {test_date} with method: {ingest_type}. Ingested successfully.",
        "results": expected_result,
    }

    request_string = f"/api/v1/openalex_works_ingest?fetch_date={test_date}&ingest_type={ingest_type}&limit={limit}"
    mocked_openalex_call = mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_data_from_date",
        return_value=expected_result,
    )

    response = sync_test_client.get(request_string)
    response_content = response.json()
    mocked_openalex_call.assert_called_once_with(
        fetch_date=test_date,
        created_or_updated=ingest_type,
        works_retrieved_limit=limit,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response_content["message"] == expected_response["message"]
    assert response_content["results"] == expected_response["results"]
