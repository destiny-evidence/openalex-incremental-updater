"""Tests for the v1 API router of the OpenAlex Incremental Updater."""

import pytest
from fastapi import status
from httpx import AsyncClient
from pytest_mock import MockerFixture

from openalex_incremental_updater.ingest import CreatedOrUpdated
from openalex_incremental_updater.models.auth import DestinyRepoToken


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ingest_type",
    [
        CreatedOrUpdated("created"),
        CreatedOrUpdated("updated"),
    ],
)
async def test_v1_openalex_works_ingest_from_date_success(
    async_test_client: AsyncClient,
    mocker: MockerFixture,
    single_destinyopenalex_work_response: dict,
    ingest_type: CreatedOrUpdated,
) -> None:
    """Check that the v1 router openalex_works_ingest endpoint returns a HTTP_200_OK response."""
    limit = 1

    expected_response = single_destinyopenalex_work_response
    test_date = next(
        item["content"]["created_date"]
        for item in expected_response.get("enhancements", [])
        if item["enhancement_type"] == "bibliographic"
    )

    base_api_url = "/api/v1/openalex_works_ingest_from_date?"

    request_string = (
        base_api_url + f"fetch_date={test_date}&ingest_type={ingest_type}&limit={limit}"
    )
    mocked_openalex_call = mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_filter",
        return_value=[expected_response],
    )
    test_openalex_query = f"from_{ingest_type.value}_date:{test_date}"
    response = await async_test_client.get(request_string)
    response_content = response.json()
    mocked_openalex_call.assert_called_once_with(
        openalex_filter=test_openalex_query,
        works_retrieved_limit=limit,
    )

    assert (
        response.status_code == status.HTTP_200_OK
    ), "Expect a HTTP_200 response on success"
    assert len(response_content) == 1, "Expect a single result in the response"
    assert (
        response_content[0] == expected_response
    ), "Expect the response to match the expected response"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ingest_type",
    [
        CreatedOrUpdated("created"),
        CreatedOrUpdated("updated"),
    ],
)
async def test_v1_openalex_works_ingest_date_range_success(
    async_test_client: AsyncClient,
    mocker: MockerFixture,
    single_destinyopenalex_work_response: dict,
    ingest_type: CreatedOrUpdated,
) -> None:
    """Check that the v1 router openalex_works_ingest endpoint returns a HTTP_200_OK response."""
    limit = 1

    expected_response = single_destinyopenalex_work_response
    test_date = next(
        item["content"]["created_date"]
        for item in expected_response.get("enhancements", [])
        if item["enhancement_type"] == "bibliographic"
    )

    base_api_url = "/api/v1/openalex_works_ingest_date_range?"

    request_string = (
        base_api_url
        + f"start_date={test_date}&end_date={test_date}&ingest_type={ingest_type}&limit={limit}"
    )
    mocked_openalex_call = mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_filter",
        return_value=[expected_response],
    )
    test_openalex_query = f"from_{ingest_type.value}_date:{test_date}&to_{ingest_type.value}_date:{test_date}"
    response = await async_test_client.get(request_string)
    response_content = response.json()
    mocked_openalex_call.assert_called_once_with(
        openalex_filter=test_openalex_query,
        works_retrieved_limit=limit,
    )

    assert (
        response.status_code == status.HTTP_200_OK
    ), "Expect a HTTP_200 response on success"
    assert len(response_content) == 1, "Expect a single result in the response"
    assert (
        response_content[0] == expected_response
    ), "Expect the response to match the expected response"


@pytest.mark.anyio
async def test_v1_openalex_works_ingest_open_filter(
    async_test_client: AsyncClient,
    mocker: MockerFixture,
    single_destinyopenalex_work_response: dict,
) -> None:
    """Check that the v1 router openalex_works_ingest endpoint returns a HTTP_200_OK response for the updated mode."""
    limit = 5

    expected_response = single_destinyopenalex_work_response

    test_date = next(
        item["content"]["created_date"]
        for item in expected_response.get("enhancements", [])
        if item["enhancement_type"] == "bibliographic"
    )

    test_filter_string = f"from_created_date:{test_date}"

    base_request_url = "/api/v1/openalex_works_open_filter?"
    test_request_string = (
        base_request_url + f"openalex_query_string={test_filter_string}&limit={limit}"
    )

    mocked_openalex_call = mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_filter",
        return_value=[expected_response],
    )
    response = await async_test_client.get(test_request_string)
    response_content = response.json()
    mocked_openalex_call.assert_called_once_with(
        openalex_filter=test_filter_string,
        works_retrieved_limit=limit,
    )

    assert response.status_code == status.HTTP_200_OK, "Expect a HTTP_200 response."
    assert len(response_content) == 1, "Expect a single result in the response"
    assert (
        response_content[0] == expected_response
    ), "Expect the response to match the expected response"


@pytest.mark.anyio
async def test_v1_get_auth_token_success(
    mocker: MockerFixture,
    async_test_client: AsyncClient,
    mock_destiny_repo_token: DestinyRepoToken,
) -> None:
    """Check that the v1 router get_auth_token endpoint returns a HTTP_200_OK response."""
    expected_response = mock_destiny_repo_token.model_dump(mode="json")

    mocker.patch(
        "openalex_incremental_updater.api.routers.v1.generate_token",
        return_value=mock_destiny_repo_token,
    )
    test_request_url = "/api/v1/auth_token"

    response = await async_test_client.get(test_request_url)
    response_content = response.json()

    assert response.status_code == status.HTTP_200_OK, "Expect a HTTP_200 response."
    assert (
        response_content == expected_response
    ), "Expect the response to match the expected response"
