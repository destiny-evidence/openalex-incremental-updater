from collections.abc import AsyncIterator, Generator
from datetime import date
from typing import Any

import pytest
from destiny_sdk.references import ReferenceFileInput
from fastapi import HTTPException, status
from freezegun import freeze_time
from pytest_mock import MockerFixture

from openalex_incremental_updater.core.config import Settings
from openalex_incremental_updater.core.job_state import JobManager
from openalex_incremental_updater.core.jobs import (
    openalex_works_ingest_date_range,
    run_background_openalex_ingest_job,
    run_openalex_refresh_blob_upload_job,
)
from openalex_incremental_updater.ingest.openalex import (
    CreatedOrUpdated,
    UpstreamOpenAlexError,
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ingest_type", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
@freeze_time("2025-08-18")
async def test_run_background_openalex_ingest_job(
    mocker: MockerFixture,
    set_test_environment_variables: Generator,
    ingest_type: CreatedOrUpdated,
    test_settings: Settings,
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
        test_settings,
        job_manager,
        job_id,
        test_report,
        start_date,
        end_date,
        ingest_type,
        limit=None,
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
    test_settings: Settings,
):
    async def fake_async_gen():
        if False:
            yield
        raise UpstreamOpenAlexError("Test error")

    def mock_func(*args: Any, **kwargs: Any) -> AsyncIterator:
        return fake_async_gen()

    mocker.patch(
        "openalex_incremental_updater.core.jobs.openalex_works_ingest_date_range",
        new=mock_func,
    )
    start_date = date.today()
    end_date = date.today()
    test_report = None
    job_manager = JobManager()

    job_id = job_manager.create(meta={"test_meta": "test_value"})
    with pytest.raises(HTTPException) as exc_info:
        await run_background_openalex_ingest_job(
            test_settings,
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
    test_settings: Settings,
):
    """Test successful ingestion of OpenAlex works within a date range."""
    test_response = [
        ReferenceFileInput.model_validate(single_destinyopenalex_work_response)
    ]
    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.build_range_query",
        return_value="test_query",
    )

    async def fake_fetch_works_filter(*args, **kwargs):
        if False:
            yield
        yield test_response

    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_filter",
        new=fake_fetch_works_filter,
    )

    async def fake_convert_destinyworks_to_jsonl_string(results):
        if False:
            yield
        yield single_destiny_openalex_work_jsonl_string.encode("utf-8")

    mocker.patch(
        "openalex_incremental_updater.ingest.data.convert_destinyworks_to_jsonl_string",
        new=fake_convert_destinyworks_to_jsonl_string,
    )
    test_report = None
    result_gen = openalex_works_ingest_date_range(
        test_settings, test_report, date.today(), date.today(), ingest_type
    )
    results = [item async for item in result_gen]
    assert all(
        result.decode("utf-8") == single_destiny_openalex_work_jsonl_string
        for result in results
    )


@pytest.mark.anyio
@freeze_time("2025-08-18")
@pytest.mark.parametrize(
    "ingest_type", [CreatedOrUpdated("created"), CreatedOrUpdated("updated")]
)
async def test_openalex_works_ingest_date_range_fails_upstream(
    mocker: MockerFixture,
    set_test_environment_variables: Generator,
    ingest_type: CreatedOrUpdated,
    test_settings: Settings,
):
    """Test successful ingestion of OpenAlex works within a date range."""
    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.build_range_query",
        return_value="test_query",
    )

    async def fake_fetch_works_filter(*args, **kwargs):
        if False:
            yield
        raise UpstreamOpenAlexError("Test error")

    mocker.patch(
        "openalex_incremental_updater.ingest.openalex.OpenAlexDataFetcher.fetch_works_filter",
        new=fake_fetch_works_filter,
    )
    test_report = None
    response = openalex_works_ingest_date_range(
        test_settings, test_report, date.today(), date.today(), ingest_type
    )
    with pytest.raises(UpstreamOpenAlexError) as exc_info:
        _result = [item async for item in response]
    assert str(exc_info.value) == "Test error"


@pytest.mark.anyio
@freeze_time("2025-08-18")
async def test_run_openalex_refresh_blob_upload_job(
    mocker: MockerFixture, test_settings: Settings
):
    """Test the OpenAlex refresh blob upload job."""
    test_data = "test_data"
    test_fetch_date = date.today()
    test_stop_date = date.today()
    test_refresh_date = date.today()
    expected_base_name = f"openalex_refresh_from_date_{test_fetch_date}_to_{test_stop_date}_refreshed_on_{test_refresh_date}"
    mocker.patch(
        "openalex_incremental_updater.core.jobs.blob_upload_multipart",
        return_value=[f"{expected_base_name}_part_001.jsonl"],
    )
    result = await run_openalex_refresh_blob_upload_job(
        test_settings, test_data, test_fetch_date, test_stop_date, test_refresh_date
    )
    assert result == expected_base_name
