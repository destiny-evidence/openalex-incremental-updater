import uuid
from datetime import date, timedelta

import pytest
from destiny_sdk.imports import ImportRecordRead
from freezegun import freeze_time

from refresh_requester.jobs import run_full_pipeline
from refresh_requester.openalex_refresh import (
    OpenAlexRefreshError,
)


@freeze_time("2025-06-12")
def test_run_full_pipeline_success_no_fetch_date_set_no_stop_date_set(
    mocker, test_settings
) -> None:
    """
    Test the run_full_pipeline function of the refresh requester job.

    Tests the case where no fetch date is set in the settings.
    """
    settings = test_settings.model_copy(deep=True)
    settings.fetch_date = None
    settings.polling_interval = 0.001
    date_today = date.today()
    date_yesterday = date_today - timedelta(days=1)
    test_latest_blob_date = date_yesterday
    test_stop_date = date_yesterday

    test_blob = "test_blob"
    test_id = uuid.uuid4()
    test_response = {
        "job_id": str(test_id),
        "status_url": f"/jobs/{test_id}",
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(),
    }
    test_batch_ids = [uuid.uuid4()]

    test_import_record = ImportRecordRead(
        id=test_id,
        processor_name="test_processor",
        processor_version="1.0.0",
        expected_reference_count=-1,
        source_name="test_source",
        status="completed",
        created_at=date_today,
        updated_at=date_today,
        fetch_date=test_latest_blob_date,
        refresh_date=date_today,
    )
    get_fetch_date_mock = mocker.patch(
        "refresh_requester.jobs.get_fetch_date",
        return_value=test_latest_blob_date,
    )
    run_refresh_job_mock = mocker.patch(
        "refresh_requester.jobs.run_refresh_job", return_value=test_response
    )
    poll_job_status_mocked_results = [
        {"status": "running", "progress": 0},
        {"status": "running", "progress": 50},
        {"status": "running", "progress": 75},
        {"status": "succeeded", "result": test_blob},
    ]
    poll_job_status_mock = mocker.patch(
        "refresh_requester.jobs.poll_job_status",
        side_effect=poll_job_status_mocked_results,
    )
    upload_blob_storage_contents_to_repository_mock = mocker.patch(
        "refresh_requester.jobs.upload_blob_storage_contents_to_repository",
        return_value={
            "import_record": test_import_record,
            "import_batch_ids": test_batch_ids,
        },
    )
    run_ingestion_metadata_blob_upload_job_mock = mocker.patch(
        "refresh_requester.jobs.run_ingestion_metadata_blob_upload_job",
        return_value=f"ingestion_metadata/{test_id}.jsonl",
    )

    assert settings.fetch_date is None, "fetch_date should be None in test settings"
    run_full_pipeline(settings)

    (
        get_fetch_date_mock.assert_called_once(),
        "date fetching should be called once",
    )
    (
        run_refresh_job_mock.assert_called_once_with(
            settings, test_latest_blob_date, test_stop_date, limit=None
        ),
        "run_refresh_job should be called with the correct date and no limit set",
    )
    assert poll_job_status_mock.call_count == len(
        poll_job_status_mocked_results
    ), "poll_job_status should be called the same number of times as the mocked results"
    (
        upload_blob_storage_contents_to_repository_mock.assert_called_once_with(
            settings, blob_to_upload=test_blob
        ),
        "should be called with the correct settings, max_retries, and blob to upload",
    )

    assert (
        run_ingestion_metadata_blob_upload_job_mock.call_count == 1
    ), "run_ingestion_metadata_blob_upload_job should be called once at the end of the job"
    metadata_arg = run_ingestion_metadata_blob_upload_job_mock.call_args[0][0]
    assert (
        "import_batch_ids" in metadata_arg
    ), "metadata should use plural import_batch_ids key"
    assert metadata_arg["import_batch_ids"] == [str(bid) for bid in test_batch_ids]


@freeze_time("2025-06-12")
def test_run_full_pipeline_success_fetch_date_set_stop_date_unset(
    mocker, test_settings
) -> None:
    """
    Test the run_full_pipeline function of the refresh requester job.

    Tests the case where a fetch date is set in the settings.
    """
    settings = test_settings.model_copy(deep=True)
    settings.polling_interval = 0.001
    date_today = date.today()
    date_yesterday = date_today - timedelta(days=1)
    settings.fetch_date = date_yesterday
    test_stop_date = date_yesterday
    test_blob = "test_blob"

    test_id = uuid.uuid4()
    test_batch_ids = [uuid.uuid4()]

    test_response = {
        "job_id": str(test_id),
        "status_url": f"/jobs/{test_id}",
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(),
    }
    test_import_record = ImportRecordRead(
        id=test_id,
        processor_name="test_processor",
        processor_version="1.0.0",
        expected_reference_count=-1,
        source_name="test_source",
        status="completed",
        created_at=date_today,
        updated_at=date_today,
        fetch_date=settings.fetch_date,
        refresh_date=date_today,
    )

    determine_next_fetch_date_mock = mocker.patch(
        "refresh_requester.utils.determine_next_fetch_date",
    )
    run_refresh_job_mock = mocker.patch(
        "refresh_requester.jobs.run_refresh_job", return_value=test_response
    )
    poll_job_status_mocked_results = [
        {"status": "running", "progress": 0},
        {"status": "running", "progress": 50},
        {"status": "running", "progress": 75},
        {"status": "succeeded", "result": test_blob},
    ]
    poll_job_status_mock = mocker.patch(
        "refresh_requester.jobs.poll_job_status",
        side_effect=poll_job_status_mocked_results,
    )
    upload_blob_storage_contents_to_repository_mock = mocker.patch(
        "refresh_requester.jobs.upload_blob_storage_contents_to_repository",
        return_value={
            "import_record": test_import_record,
            "import_batch_ids": test_batch_ids,
        },
    )
    run_ingestion_metadata_blob_upload_job_mock = mocker.patch(
        "refresh_requester.jobs.run_ingestion_metadata_blob_upload_job",
        return_value=f"ingestion_metadata/{test_id}.jsonl",
    )

    run_full_pipeline(settings)

    assert (
        determine_next_fetch_date_mock.call_count == 0
    ), "this should not be called when fetch_date is set in settings"
    (
        run_refresh_job_mock.assert_called_once_with(
            settings, date_yesterday, test_stop_date, limit=None
        ),
        "run_refresh_job should be called with the correct date and no limit set",
    )
    assert poll_job_status_mock.call_count == len(
        poll_job_status_mocked_results
    ), "poll_job_status should be called the same number of times as the mocked results"
    (
        upload_blob_storage_contents_to_repository_mock.assert_called_once_with(
            settings, blob_to_upload=test_blob
        ),
        "should be called with the correct settings, max_retries, and blob to upload",
    )
    assert (
        run_ingestion_metadata_blob_upload_job_mock.call_count == 1
    ), "run_ingestion_metadata_blob_upload_job should be called once at the end of the job"


@freeze_time("2025-06-12")
def test_run_full_pipeline_success_fetch_date_set_stop_date_set(
    mocker, test_settings
) -> None:
    """
    Test the run_full_pipeline function of the refresh requester job.

    Tests the case where a fetch date is set in the settings.
    """
    settings = test_settings.model_copy(deep=True)
    settings.polling_interval = 0.001
    date_today = date.today()
    date_yesterday = date_today - timedelta(days=1)
    settings.stop_date = date_yesterday
    settings.fetch_date = date_yesterday
    test_blob = "test_blob"

    test_id = uuid.uuid4()
    test_batch_ids = [uuid.uuid4()]
    test_response = {
        "job_id": str(test_id),
        "status_url": f"/jobs/{test_id}",
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(),
    }
    test_import_record = ImportRecordRead(
        id=test_id,
        processor_name="test_processor",
        processor_version="1.0.0",
        expected_reference_count=-1,
        source_name="test_source",
        status="completed",
        created_at=date_today,
        updated_at=date_today,
        fetch_date=settings.fetch_date,
        refresh_date=date_today,
    )

    determine_next_fetch_date_mock = mocker.patch(
        "refresh_requester.utils.determine_next_fetch_date",
    )
    run_refresh_job_mock = mocker.patch(
        "refresh_requester.jobs.run_refresh_job", return_value=test_response
    )
    poll_job_status_mocked_results = [
        {"status": "running", "progress": 0},
        {"status": "running", "progress": 50},
        {"status": "running", "progress": 75},
        {"status": "succeeded", "result": test_blob},
    ]
    poll_job_status_mock = mocker.patch(
        "refresh_requester.jobs.poll_job_status",
        side_effect=poll_job_status_mocked_results,
    )
    upload_blob_storage_contents_to_repository_mock = mocker.patch(
        "refresh_requester.jobs.upload_blob_storage_contents_to_repository",
        return_value={
            "import_record": test_import_record,
            "import_batch_ids": test_batch_ids,
        },
    )
    run_ingestion_metadata_blob_upload_job_mock = mocker.patch(
        "refresh_requester.jobs.run_ingestion_metadata_blob_upload_job",
        return_value=f"ingestion_metadata/{test_id}.jsonl",
    )

    run_full_pipeline(settings)

    assert (
        determine_next_fetch_date_mock.call_count == 0
    ), "should not be called when fetch_date is set in settings"
    (
        run_refresh_job_mock.assert_called_once_with(
            settings, settings.fetch_date, settings.stop_date, limit=None
        ),
        "run_refresh_job should be called with the correct date and no limit set",
    )
    assert poll_job_status_mock.call_count == len(
        poll_job_status_mocked_results
    ), "poll_job_status should be called the same number of times as the mocked results"
    (
        upload_blob_storage_contents_to_repository_mock.assert_called_once_with(
            settings, blob_to_upload=test_blob
        ),
        "should be called with the correct settings, max_retries, and blob to upload",
    )
    assert (
        run_ingestion_metadata_blob_upload_job_mock.call_count == 1
    ), "run_ingestion_metadata_blob_upload_job should be called once at the end of the job"


@freeze_time("2026-05-20")
def test_run_full_pipeline_exits_cleanly_when_fetch_date_after_stop_date(
    mocker, caplog, test_settings
):
    """
    Test that the pipeline exits cleanly (code 0) when fetch_date > stop_date.

    This guards against the case where:

    - the fetch date check returns a fetch date later than the stop date
    e.g., last run had stop_date=today, so next fetch_date = tomorrow
    - meanwhile, get_stop_date() caps at yesterday — resulting in an
    invalid range that yields blank results from OpenAlex.
    """
    settings = test_settings.model_copy(deep=True)
    date_tomorrow = date.today() + timedelta(days=1)
    date_yesterday = date.today() - timedelta(days=1)
    settings.fetch_date = date_tomorrow
    settings.stop_date = date_yesterday

    mocked_sys_exit = mocker.patch(
        "refresh_requester.jobs.sys.exit", side_effect=SystemExit(0)
    )
    run_refresh_job_mock = mocker.patch("refresh_requester.jobs.run_refresh_job")

    with caplog.at_level("WARNING"), pytest.raises(SystemExit) as exc_info:
        run_full_pipeline(settings)

    assert exc_info.value.code == 0
    assert "No data to fetch. Exiting" in caplog.text
    mocked_sys_exit.assert_called_once_with(0)
    run_refresh_job_mock.assert_not_called()


@freeze_time("2026-05-20")
def test_run_full_pipeline_fails_openalex_refresh_error(mocker, caplog, test_settings):
    """
    Test the run_full_pipeline function of the refresh requester job.

    Tests the case where the OpenAlex API returns an error.
    """
    settings = test_settings.model_copy(deep=True)
    date_today = date.today()
    mocker.patch(
        "refresh_requester.utils.determine_next_fetch_date",
        return_value=date_today + timedelta(days=-1),
    )
    run_refresh_job_mock = mocker.patch(
        "refresh_requester.jobs.run_refresh_job",
        side_effect=OpenAlexRefreshError("A test error."),
    )
    mocked_sys_exit = mocker.patch(
        "refresh_requester.jobs.sys.exit", side_effect=SystemExit(1)
    )
    with caplog.at_level("ERROR"), pytest.raises(SystemExit):
        run_full_pipeline(settings)

        assert "Error when requesting refresh: A test error." in caplog.text
    run_refresh_job_mock.assert_called_once(), "run_refresh_job should be called once"
    (
        mocked_sys_exit.assert_called_once_with(1),
        "sys.exit should be called with exit code 1",
    )


def test_run_full_pipeline_fails_well_job_failed_status(mocker, caplog, test_settings):
    """
    Test the run_full_pipeline function of the refresh requester job.

    Tests the case where the job status is 'failed'.
    """
    settings = test_settings.model_copy(deep=True)
    settings.polling_interval = 0.001
    date_today = date.today()
    date_yesterday = date_today - timedelta(days=1)
    settings.stop_date = date_yesterday
    settings.fetch_date = date_yesterday

    test_id = uuid.uuid4()
    test_response = {
        "job_id": str(test_id),
        "status_url": f"/jobs/{test_id}",
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(),
    }
    mocker.patch(
        "refresh_requester.utils.determine_next_fetch_date",
    )
    mocker.patch("refresh_requester.jobs.run_refresh_job", return_value=test_response)
    poll_job_status_mocked_results = [
        {"status": "running", "progress": 0},
        {"status": "running", "progress": 50},
        {"status": "running", "progress": 75},
        {"status": "failed", "result": None, "error_message": "A test error."},
    ]
    poll_job_status_mock = mocker.patch(
        "refresh_requester.jobs.poll_job_status",
        side_effect=poll_job_status_mocked_results,
    )
    mocked_sys_exit = mocker.patch(
        "refresh_requester.jobs.sys.exit", side_effect=SystemExit(1)
    )

    with caplog.at_level("ERROR"), pytest.raises(SystemExit):
        run_full_pipeline(settings)

    assert "Job failed: A test error." in caplog.text
    assert poll_job_status_mock.call_count == len(
        poll_job_status_mocked_results
    ), "poll_job_status should be called once for each status update"
    (
        mocked_sys_exit.assert_called_once_with(1),
        "sys.exit should be called with exit code 1",
    )


def test_run_full_pipeline_fails_well_job_cancelled_status(
    mocker, caplog, test_settings
):
    """
    Test the run_full_pipeline function of the refresh requester job.

    Tests the case where the job status is 'cancelled'.
    """
    settings = test_settings.model_copy(deep=True)
    settings.polling_interval = 0.001
    date_today = date.today()
    date_yesterday = date_today - timedelta(days=1)
    settings.stop_date = date_yesterday
    settings.fetch_date = date_yesterday

    test_id = uuid.uuid4()
    test_response = {
        "job_id": str(test_id),
        "status_url": f"/jobs/{test_id}",
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(),
    }
    mocker.patch(
        "refresh_requester.utils.determine_next_fetch_date",
    )
    mocker.patch("refresh_requester.jobs.run_refresh_job", return_value=test_response)
    poll_job_status_mocked_results = [
        {"status": "running", "progress": 0},
        {"status": "running", "progress": 50},
        {"status": "running", "progress": 75},
        {"status": "cancelled", "result": None},
    ]
    poll_job_status_mock = mocker.patch(
        "refresh_requester.jobs.poll_job_status",
        side_effect=poll_job_status_mocked_results,
    )
    mocked_sys_exit = mocker.patch(
        "refresh_requester.jobs.sys.exit", side_effect=SystemExit(1)
    )

    with caplog.at_level("WARNING"), pytest.raises(SystemExit):
        run_full_pipeline(settings)

    assert "Job was cancelled." in caplog.text
    assert poll_job_status_mock.call_count == len(
        poll_job_status_mocked_results
    ), "poll_job_status should be called once for each status update"
    (
        mocked_sys_exit.assert_called_once_with(1),
        "sys.exit should be called with exit code 1",
    )


def test_run_full_pipeline_fails_well_no_uploaded_blob_returned(
    mocker, caplog, test_settings
):
    """
    Test the run_full_pipeline function of the refresh requester job.

    Tests the case where no uploaded blob is returned.
    """
    settings = test_settings.model_copy(deep=True)
    settings.polling_interval = 0.001
    date_today = date.today()
    date_yesterday = date_today - timedelta(days=1)
    settings.stop_date = date_yesterday
    settings.fetch_date = date_yesterday

    test_id = uuid.uuid4()
    test_response = {
        "job_id": str(test_id),
        "status_url": f"/jobs/{test_id}",
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(),
    }
    mocker.patch(
        "refresh_requester.utils.determine_next_fetch_date",
    )
    mocker.patch("refresh_requester.jobs.run_refresh_job", return_value=test_response)
    poll_job_status_mocked_results = [
        {"status": "running", "progress": 0},
        {"status": "running", "progress": 50},
        {"status": "running", "progress": 75},
        {"status": "succeeded", "result": None},
    ]
    poll_job_status_mock = mocker.patch(
        "refresh_requester.jobs.poll_job_status",
        side_effect=poll_job_status_mocked_results,
    )
    mocked_sys_exit = mocker.patch(
        "refresh_requester.jobs.sys.exit", side_effect=SystemExit(1)
    )

    with caplog.at_level("ERROR"), pytest.raises(SystemExit):
        run_full_pipeline(settings)

    assert "No data returned from job." in caplog.text
    assert poll_job_status_mock.call_count == len(
        poll_job_status_mocked_results
    ), "poll_job_status should be called once for each status update"
    (
        mocked_sys_exit.assert_called_once_with(1),
        "sys.exit should be called with exit code 1",
    )
