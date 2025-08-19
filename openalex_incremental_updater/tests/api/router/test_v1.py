"""Tests for the v1 API router of the OpenAlex Incremental Updater."""

import asyncio
from collections.abc import Generator
from datetime import date
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from freezegun import freeze_time
from httpx import AsyncClient
from pytest_mock import MockerFixture

from openalex_incremental_updater.core.job_state import JobManager, JobState
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


@freeze_time("2025-08-18")
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
    ingest_type: CreatedOrUpdated,
) -> None:
    """Check that the v1 router openalex_works_ingest endpoint returns a HTTP_200_OK response."""
    limit = 1
    test_id = str(uuid4())
    test_date = date.today()
    expected_response_content = {
        "job_id": test_id,
        "status_url": f"/jobs/{test_id}",
        "start_date": test_date.isoformat(),
        "end_date": test_date.isoformat(),
    }

    base_api_url = "/api/v1/openalex_works_ingest_date_range?"

    request_string = (
        base_api_url
        + f"start_date={test_date}&end_date={test_date}&ingest_type={ingest_type}&limit={limit}"
    )

    mock_job_create = mocker.patch(
        "openalex_incremental_updater.core.job_state.JobManager.create",
        return_value=test_id,
    )
    original_create_task = asyncio.create_task
    mock_create_task = mocker.patch(
        "asyncio.create_task", side_effect=lambda coro: original_create_task(coro)
    )
    response = await async_test_client.get(request_string)

    assert (
        response.status_code == status.HTTP_202_ACCEPTED
    ), "Expect a HTTP_202 response on success"
    assert (
        response.json() == expected_response_content
    ), "Expect the response content to match"

    mock_job_create.assert_called_once_with(
        meta={
            "start_date": test_date,
            "end_date": test_date,
            "ingest_type": ingest_type,
            "limit": limit,
        }
    )
    mock_create_task.assert_called_once()


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


@freeze_time("2025-08-18")
@pytest.mark.anyio
async def test_run_with_tracking_async(
    async_test_client: AsyncClient,
    mocker: MockerFixture,
) -> None:
    """Test the _run_with_tracking_async function."""
    from openalex_incremental_updater.api.routers.v1 import _run_with_tracking_async

    job_manager = JobManager()
    test_date = date.today()
    job_id = job_manager.create(
        meta={
            "start_date": test_date,
            "end_date": test_date,
            "ingest_type": "test",
            "limit": 999,
        }
    )

    async def mock_coro():
        pass

    mock_succeed = mocker.patch.object(
        job_manager, "succeed", wraps=job_manager.succeed
    )
    mocker.patch("openalex_incremental_updater.api.routers.v1.job_manager", job_manager)
    mock_fail = mocker.patch.object(job_manager, "fail", wraps=job_manager.fail)
    mock_cancel = mocker.patch.object(job_manager, "cancel", wraps=job_manager.cancel)

    await _run_with_tracking_async(job_id, mock_coro())

    assert (
        job_manager.get(job_id)["status"] == JobState.SUCCEEDED
    ), "Job state should be SUCCEEDED"
    assert mock_succeed.call_count == 1, "JobManager.succeed should be called once"
    assert mock_fail.call_count == 0, "JobManager.fail should not be called"
    assert mock_cancel.call_count == 0, "JobManager.cancel should not be called"


@pytest.mark.anyio
async def test_run_with_tracking_async_cancelled_job(
    async_test_client: AsyncClient,
    mocker: MockerFixture,
) -> None:
    """Test the _run_with_tracking_async function with a cancelled job."""
    from openalex_incremental_updater.api.routers.v1 import _run_with_tracking_async

    job_manager = JobManager()
    test_date = date.today()
    job_id = job_manager.create(
        meta={
            "start_date": test_date,
            "end_date": test_date,
            "ingest_type": "test",
            "limit": 999,
        }
    )

    async def mock_coro():
        raise asyncio.CancelledError

    mock_cancel = mocker.patch.object(job_manager, "cancel", wraps=job_manager.cancel)
    mocker.patch("openalex_incremental_updater.api.routers.v1.job_manager", job_manager)

    await _run_with_tracking_async(job_id, mock_coro())

    assert (
        job_manager.get(job_id)["status"] == JobState.CANCELLED
    ), "Job state should be CANCELLED"
    assert mock_cancel.call_count == 1, "JobManager.cancel should be called once"


@pytest.mark.anyio
async def test_run_with_tracking_async_exception_raised(
    async_test_client: AsyncClient,
    mocker: MockerFixture,
) -> None:
    """Test the _run_with_tracking_async function with a cancelled job."""
    from openalex_incremental_updater.api.routers.v1 import _run_with_tracking_async

    job_manager = JobManager()
    test_date = date.today()
    job_id = job_manager.create(
        meta={
            "start_date": test_date,
            "end_date": test_date,
            "ingest_type": "test",
            "limit": 999,
        }
    )

    async def mock_coro():
        raise Exception("Test exception")

    mock_fail = mocker.patch.object(job_manager, "fail", wraps=job_manager.fail)
    mocker.patch("openalex_incremental_updater.api.routers.v1.job_manager", job_manager)

    await _run_with_tracking_async(job_id, mock_coro())

    assert (
        job_manager.get(job_id)["status"] == JobState.FAILED
    ), "Job state should be FAILED"
    assert mock_fail.call_count == 1, "JobManager.fail should be called once"


def test_report_status(set_test_environment_variables: Generator):
    from openalex_incremental_updater.api.routers.v1 import report_status

    expected_progress_fields = {"status": "test", "progress": 100}
    job_manager = JobManager()
    job_id = job_manager.create(meta={})
    report_status(job_manager, job_id, expected_progress_fields)
    assert job_manager.get(job_id).get("progress") == expected_progress_fields


@pytest.mark.anyio
async def test_v1_get_job_running_success(
    mocker: MockerFixture, sync_test_client: TestClient
) -> None:
    from openalex_incremental_updater.api.routers.v1 import job_manager

    # patch global job_manager
    job_id = job_manager.create()
    job_manager.start(job_id)
    expected_response = {
        "job_id": job_id,
        "status": "running",
    }
    response = sync_test_client.get(f"/api/v1/jobs/{job_id}")
    assert (
        response.status_code == status.HTTP_202_ACCEPTED
    ), "Expected HTTP 202 ACCEPTED response"
    response_data = response.json()
    assert response_data["job_id"] == expected_response["job_id"]
    assert response_data["status"] == expected_response["status"]


@pytest.mark.anyio
async def test_v1_get_job_cancelled_success(
    mocker: MockerFixture, sync_test_client: TestClient
) -> None:
    from openalex_incremental_updater.api.routers.v1 import job_manager

    # patch global job_manager
    job_id = job_manager.create()
    job_manager.cancel(job_id)
    expected_response = {
        "job_id": job_id,
        "status": "cancelled",
    }
    response = sync_test_client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == status.HTTP_200_OK, "Expected HTTP 200 OK response"
    response_data = response.json()
    assert response_data["job_id"] == expected_response["job_id"]
    assert response_data["status"] == expected_response["status"]


@pytest.mark.anyio
async def test_v1_get_job_failed_success(
    mocker: MockerFixture, sync_test_client: TestClient
) -> None:
    from openalex_incremental_updater.api.routers.v1 import job_manager

    # patch global job_manager
    job_id = job_manager.create()
    test_error_message = "Test failure."
    job_manager.fail(job_id, Exception(test_error_message))
    expected_response = {
        "job_id": job_id,
        "status": "failed",
        "error": f"Exception: {test_error_message}",
    }
    response = sync_test_client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == status.HTTP_200_OK, "Expected HTTP 200 OK response"
    response_data = response.json()
    assert response_data["job_id"] == expected_response["job_id"]
    assert response_data["status"] == expected_response["status"]
    assert (
        response_data["error"] == expected_response["error"]
    ), "Error message should match"


@pytest.mark.anyio
async def test_v1_get_job_succeeded_success(
    mocker: MockerFixture, sync_test_client: TestClient
) -> None:
    from openalex_incremental_updater.api.routers.v1 import job_manager

    # patch global job_manager
    job_id = job_manager.create()
    job_manager.succeed(job_id)
    expected_response = {
        "job_id": job_id,
        "status": "succeeded",
    }
    response = sync_test_client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == status.HTTP_200_OK, "Expected HTTP 200 OK response"
    response_data = response.json()
    assert response_data["job_id"] == expected_response["job_id"]
    assert response_data["status"] == expected_response["status"]


@pytest.mark.anyio
async def test_v1_get_job_returns_404_job_not_found(
    mocker: MockerFixture, sync_test_client: TestClient
) -> None:
    # patch global job_manager
    job_id = "a-fake-test-id"
    expected_response_detail = "Job not found"
    response = sync_test_client.get(f"/api/v1/jobs/{job_id}")
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), "Expected HTTP 404 NOT FOUND response"
    response_data = response.json()
    assert response_data["detail"] == expected_response_detail


@pytest.mark.anyio
async def test_v1_cancel_job_success(
    mocker: MockerFixture, sync_test_client: TestClient
) -> None:
    from openalex_incremental_updater.api.routers.v1 import (
        _run_with_tracking_async,
        job_manager,
    )

    # patch global job_manager
    job_id = job_manager.create()

    async def mock_coro():
        pass

    tasks_mock = mocker.patch(
        "openalex_incremental_updater.api.routers.v1.TASKS",
        new_callable=mocker.MagicMock(),
    )
    tasks_mock.get.return_value = asyncio.create_task(
        _run_with_tracking_async(job_id, mock_coro)
    )
    response = sync_test_client.delete(f"/api/v1/jobs/{job_id}")
    assert (
        response.status_code == status.HTTP_204_NO_CONTENT
    ), "Expected HTTP 204 NO CONTENT response"
    assert response.json() == {"ok": True}


@pytest.mark.anyio
async def test_v1_cancel_job_fails_job_not_found(
    mocker: MockerFixture, sync_test_client: TestClient
) -> None:
    job_id = "a-fake-test-id"
    response = sync_test_client.delete(f"/api/v1/jobs/{job_id}")
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), "Expected HTTP 404 NOT FOUND when job not found"
    assert response.json() == {"detail": "Job not found"}, "Expect response to match."
