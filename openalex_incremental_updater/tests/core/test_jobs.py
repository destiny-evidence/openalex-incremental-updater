from collections.abc import Generator
from datetime import date

import pytest
from fastapi import HTTPException, status
from freezegun import freeze_time
from pytest_mock import MockerFixture

from openalex_incremental_updater.core.job_state import JobManager
from openalex_incremental_updater.core.jobs import (
    openalex_works_ingest_date_range,
    openalex_works_ingest_open_filter,
    run_background_openalex_ingest_job,
    run_openalex_refresh_blob_upload_job,
)
from openalex_incremental_updater.ingest.openalex import (
    CreatedOrUpdated,
    UpstreamOpenAlexError,
)
from openalex_incremental_updater.models.destiny import DestinyOpenAlexWork


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ingest_type", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
@freeze_time("2025-08-18")
async def test_run_background_openalex_ingest_job(
    mocker: MockerFixture,
    set_test_environment_variables: Generator,
    ingest_type: CreatedOrUpdated,
):
    """Test running the background OpenAlex ingest job."""
    expected_blob_name = "test_blob"
    mocker.patch(
        "openalex_incremental_updater.core.jobs.openalex_works_ingest_date_range",
        return_value="test",
    )
    mocker.patch(
        "openalex_incremental_updater.core.jobs.run_openalex_refresh_blob_upload_job",
        return_value=expected_blob_name,
    )
    start_date = date.today()
    end_date = date.today()
    test_report = None
    job_manager = JobManager()

    job_id = job_manager.create(meta={"test_meta": "test_value"})
    await run_background_openalex_ingest_job(
        job_manager, job_id, test_report, start_date, end_date, ingest_type, limit=None
    )

    job = job_manager.get(job_id)
    assert job is not None
    assert job["status"] == "succeeded"
    assert job["result"] == expected_blob_name


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ingest_type", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
@freeze_time("2025-08-18")
async def test_run_background_openalex_ingest_job_fails_gracefully(
    mocker: MockerFixture,
    set_test_environment_variables: Generator,
    ingest_type: CreatedOrUpdated,
):
    """Test running the background OpenAlex ingest job."""
    mocker.patch(
        "openalex_incremental_updater.core.jobs.openalex_works_ingest_date_range",
        side_effect=UpstreamOpenAlexError("Test error"),
    )
    start_date = date.today()
    end_date = date.today()
    test_report = None
    job_manager = JobManager()

    job_id = job_manager.create(meta={"test_meta": "test_value"})
    with pytest.raises(HTTPException) as exc_info:
        await run_background_openalex_ingest_job(
            job_manager,
            job_id,
            test_report,
            start_date,
            end_date,
            ingest_type,
            limit=None,
        )
    assert exc_info.value.detail == "Test error"
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert job_manager.get(job_id).get("status") == "failed"


@pytest.mark.anyio
@freeze_time("2025-08-18")
@pytest.mark.parametrize(
    "ingest_type", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
async def test_openalex_works_ingest_date_range_success(
    mocker: MockerFixture,
    set_test_environment_variables: Generator,
    ingest_type: CreatedOrUpdated,
    single_destinyopenalex_work_response: dict,
    single_destiny_openalex_work_jsonl_string: str,
):
    """Test successful ingestion of OpenAlex works within a date range."""
    test_response = [
        DestinyOpenAlexWork.model_validate(single_destinyopenalex_work_response)
    ]
    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.build_range_query",
        return_value="test_query",
    )
    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_filter",
        return_value=test_response,
    )
    mocker.patch(
        "openalex_incremental_updater.ingest.data.convert_destinyworks_to_jsonl_string",
        return_value=single_destiny_openalex_work_jsonl_string,
    )
    test_report = None
    result = await openalex_works_ingest_date_range(
        test_report, date.today(), date.today(), ingest_type
    )
    assert next(result).decode("utf-8") == single_destiny_openalex_work_jsonl_string


@pytest.mark.anyio
@freeze_time("2025-08-18")
@pytest.mark.parametrize(
    "ingest_type", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
async def test_openalex_works_ingest_date_range_fails_upstream(
    mocker: MockerFixture,
    set_test_environment_variables: Generator,
    ingest_type: CreatedOrUpdated,
):
    """Test successful ingestion of OpenAlex works within a date range."""
    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.build_range_query",
        return_value="test_query",
    )
    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_filter",
        side_effect=UpstreamOpenAlexError("Test error"),
    )
    test_report = None

    with pytest.raises(UpstreamOpenAlexError) as exc_info:
        await openalex_works_ingest_date_range(
            test_report, date.today(), date.today(), ingest_type
        )
    assert str(exc_info.value) == "Test error"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ingest_type", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
async def test_openalex_works_ingest_open_filter(
    mocker: MockerFixture,
    ingest_type: CreatedOrUpdated,
    set_test_environment_variables: Generator,
    single_destinyopenalex_work_response: dict,
):
    """Test successful ingestion of OpenAlex works from a specific date."""
    expected_result = [
        DestinyOpenAlexWork.model_validate(single_destinyopenalex_work_response)
    ]
    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.build_query",
        return_value="test_query",
    )
    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_filter",
        return_value=expected_result,
    )
    test_query_string = "test_query_string"
    result = await openalex_works_ingest_open_filter(test_query_string, ingest_type)
    assert result == expected_result


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ingest_type", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
async def test_openalex_works_ingest_open_filter_fails_gracefully(
    mocker: MockerFixture,
    ingest_type: CreatedOrUpdated,
    set_test_environment_variables: Generator,
):
    """Test successful ingestion of OpenAlex works from a specific date."""
    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.build_query",
        return_value="test_query",
    )
    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_filter",
        side_effect=UpstreamOpenAlexError("Test error"),
    )
    test_query_string = "test_query_string"

    with pytest.raises(HTTPException) as exc_info:
        await openalex_works_ingest_open_filter(test_query_string, ingest_type)
    assert exc_info.value.detail == "Test error"
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.anyio
@freeze_time("2025-08-18")
async def test_run_openalex_refresh_blob_upload_job(mocker: MockerFixture):
    """Test the OpenAlex refresh blob upload job."""
    test_data = "test_data"
    test_fetch_date = date.today()
    test_stop_date = date.today()
    test_refresh_date = date.today()
    expected_blob_name = f"openalex_refresh_from_date_{test_fetch_date}_to_{test_stop_date}_refreshed_on_{test_refresh_date}.jsonl"
    mocker.patch(
        "openalex_incremental_updater.core.jobs.blob_upload",
        side_effect=lambda _, arg: arg,
    )
    result = await run_openalex_refresh_blob_upload_job(
        test_data, test_fetch_date, test_stop_date, test_refresh_date
    )
    assert result == expected_blob_name
