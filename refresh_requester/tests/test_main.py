from datetime import date, timedelta

from freezegun import freeze_time

from refresh_requester.main import main


@freeze_time("2025-06-12")
def test_main_success_no_fetch_date_set(mocker, test_settings) -> None:
    """
    Test the main function of the refresh requester job.

    Tests the case where no fetch date is set in the settings.
    """
    settings = test_settings.model_copy(deep=True)
    settings.fetch_date = None
    date_today = date.today()  # noqa: DTZ011
    date_yesterday = date_today - timedelta(days=1)
    test_latest_blob_date = date_yesterday
    test_data = "test_data"
    test_blob = "test_blob"
    check_prev_dates_mock = mocker.patch(
        "refresh_requester.main.check_previous_file_dates",
        return_value=test_latest_blob_date,
    )
    run_refresh_job_mock = mocker.patch(
        "refresh_requester.main.run_refresh_job", return_value=test_data
    )
    run_blob_upload_job_mock = mocker.patch(
        "refresh_requester.main.run_blob_upload_job", return_value=test_blob
    )
    upload_blob_storage_mock = mocker.patch(
        "refresh_requester.main.upload_blob_storage_contents_to_repository"
    )

    assert settings.fetch_date is None, "fetch_date should be None in test settings"
    main(settings)

    (
        check_prev_dates_mock.assert_called_once(),
        "check_previous_file_dates should be called once",
    )
    (
        run_refresh_job_mock.assert_called_once_with(test_latest_blob_date, limit=None),
        "run_refresh_job should be called with the correct date and no limit set",
    )
    (
        run_blob_upload_job_mock.assert_called_once_with(
            test_data, test_latest_blob_date, date_today
        ),
        "run_blob_upload_job should be called with the correct data, date, and today's date",
    )
    (
        upload_blob_storage_mock.assert_called_once_with(
            settings, blob_to_upload=test_blob
        ),
        "should be called with the correct settings, max_retries, and blob to upload",
    )


@freeze_time("2025-06-12")
def test_main_success_fetch_date_set_in_settings(mocker, test_settings) -> None:
    """
    Test the main function of the refresh requester job.

    Tests the case where a fetch date is set in the settings.
    """
    settings = test_settings.model_copy(deep=True)
    date_today = date.today()  # noqa: DTZ011
    date_yesterday = date_today - timedelta(days=1)
    settings.fetch_date = date_yesterday
    test_data = "test_data"
    test_blob = "test_blob"
    check_prev_dates_mock = mocker.patch(
        "refresh_requester.main.check_previous_file_dates",
        return_value=test_settings.fetch_date,
    )
    run_refresh_job_mock = mocker.patch(
        "refresh_requester.main.run_refresh_job", return_value=test_data
    )
    run_blob_upload_job_mock = mocker.patch(
        "refresh_requester.main.run_blob_upload_job", return_value=test_blob
    )
    upload_blob_storage_mock = mocker.patch(
        "refresh_requester.main.upload_blob_storage_contents_to_repository"
    )

    main(settings)

    assert (
        check_prev_dates_mock.call_count == 0
    ), "check_previous_file_dates should not be called"
    (
        run_refresh_job_mock.assert_called_once_with(settings.fetch_date, limit=None),
        "run_refresh_job should be called with the correct date and no limit set",
    )
    (
        run_blob_upload_job_mock.assert_called_once_with(
            test_data, settings.fetch_date, date_today
        ),
        "run_blob_upload_job should be called with the correct data, date, and today's date",
    )
    (
        upload_blob_storage_mock.assert_called_once_with(
            settings, blob_to_upload=test_blob
        ),
        "should be called with the correct settings, max_retries, and blob to upload",
    )
