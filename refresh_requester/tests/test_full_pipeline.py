import uuid
from datetime import date, timedelta

from destiny_sdk.imports import ImportRecordRead
from freezegun import freeze_time

from refresh_requester.jobs import run_full_pipeline


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
    date_today = date.today()  # noqa: DTZ011
    date_yesterday = date_today - timedelta(days=1)
    test_latest_blob_date = date_yesterday
    test_stop_date = date_yesterday
    test_data = "test_data"
    test_blob = "test_blob"
    test_id = uuid.uuid4()
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
        "refresh_requester.jobs.run_refresh_job", return_value=test_data
    )
    run_openalex_refresh_blob_upload_job_mock = mocker.patch(
        "refresh_requester.jobs.run_openalex_refresh_blob_upload_job",
        return_value=test_blob,
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
        "check_previous_file_dates should be called once",
    )
    (
        run_refresh_job_mock.assert_called_once_with(
            settings, test_latest_blob_date, test_stop_date, limit=None
        ),
        "run_refresh_job should be called with the correct date and no limit set",
    )
    (
        run_openalex_refresh_blob_upload_job_mock.assert_called_once_with(
            test_data, test_latest_blob_date, test_stop_date, date_today
        ),
        "run_openalex_refresh_blob_upload_job should be called with the correct data, date, and today's date",
    )
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
def test_run_full_pipeline_success_fetch_date_set_stop_date_unset(
    mocker, test_settings
) -> None:
    """
    Test the run_full_pipeline function of the refresh requester job.

    Tests the case where a fetch date is set in the settings.
    """
    settings = test_settings.model_copy(deep=True)
    date_today = date.today()  # noqa: DTZ011
    date_yesterday = date_today - timedelta(days=1)
    settings.fetch_date = date_yesterday
    test_stop_date = date_yesterday
    test_data = "test_data"
    test_blob = "test_blob"

    test_id = uuid.uuid4()
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
        fetch_date=settings.fetch_date,
        refresh_date=date_today,
    )

    check_previous_file_dates_mock = mocker.patch(
        "refresh_requester.utils.check_previous_file_dates",
    )
    run_refresh_job_mock = mocker.patch(
        "refresh_requester.jobs.run_refresh_job", return_value=test_data
    )
    run_openalex_refresh_blob_upload_job_mock = mocker.patch(
        "refresh_requester.jobs.run_openalex_refresh_blob_upload_job",
        return_value=test_blob,
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
        check_previous_file_dates_mock.call_count == 0
    ), "check_previous_file_dates should not be called when fetch_date is set in settings"
    (
        run_refresh_job_mock.assert_called_once_with(
            settings, date_yesterday, test_stop_date, limit=None
        ),
        "run_refresh_job should be called with the correct date and no limit set",
    )
    (
        run_openalex_refresh_blob_upload_job_mock.assert_called_once_with(
            test_data, settings.fetch_date, test_stop_date, date_today
        ),
        "run_openalex_refresh_blob_upload_job should be called with the correct data, date, and today's date",
    )

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
    date_today = date.today()  # noqa: DTZ011
    date_yesterday = date_today - timedelta(days=1)
    settings.stop_date = date_yesterday
    settings.fetch_date = date_yesterday
    test_data = "test_data"
    test_blob = "test_blob"

    test_id = uuid.uuid4()
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
        fetch_date=settings.fetch_date,
        refresh_date=date_today,
    )

    check_previous_file_dates_mock = mocker.patch(
        "refresh_requester.utils.check_previous_file_dates",
    )
    run_refresh_job_mock = mocker.patch(
        "refresh_requester.jobs.run_refresh_job", return_value=test_data
    )
    run_openalex_refresh_blob_upload_job_mock = mocker.patch(
        "refresh_requester.jobs.run_openalex_refresh_blob_upload_job",
        return_value=test_blob,
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
        check_previous_file_dates_mock.call_count == 0
    ), "check_previous_file_dates should not be called when fetch_date is set in settings"
    (
        run_refresh_job_mock.assert_called_once_with(
            settings, settings.fetch_date, settings.stop_date, limit=None
        ),
        "run_refresh_job should be called with the correct date and no limit set",
    )
    (
        run_openalex_refresh_blob_upload_job_mock.assert_called_once_with(
            test_data, settings.fetch_date, settings.stop_date, date_today
        ),
        "run_openalex_refresh_blob_upload_job should be called with the correct data, date, and today's date",
    )

    (
        upload_blob_storage_contents_to_repository_mock.assert_called_once_with(
            settings, blob_to_upload=test_blob
        ),
        "should be called with the correct settings, max_retries, and blob to upload",
    )
    assert (
        run_ingestion_metadata_blob_upload_job_mock.call_count == 1
    ), "run_ingestion_metadata_blob_upload_job should be called once at the end of the job"
