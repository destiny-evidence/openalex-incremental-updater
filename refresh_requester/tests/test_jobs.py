import json
from datetime import date
from http import HTTPStatus
from uuid import uuid4

import pytest
import requests
from freezegun import freeze_time

from refresh_requester.jobs import (
    check_stop_date_not_before_fetch_date,
    run_ingestion_metadata_blob_upload_job,
    run_refresh_job,
)
from refresh_requester.openalex_refresh import OpenAlexRefreshError


@freeze_time("2025-08-18")
def test_run_refresh_job_success(mocker, test_settings):
    """Test a successful job run."""
    test_id = uuid4()
    mocked_api_return_value = {
        "job_id": str(test_id),
        "status_url": f"/jobs/{test_id}",
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(),
    }
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.ACCEPTED

    mock_response.json.return_value = mocked_api_return_value

    mocker.patch("requests.Session.get", return_value=mock_response)

    test_date = date(2025, 3, 1)
    result = run_refresh_job(
        test_settings, test_date, test_date, limit=len(mocked_api_return_value)
    )
    assert result == mocked_api_return_value


def test_run_refresh_job_request_exception_failure(mocker, test_settings):
    """Test a failed job run throws the relevant errors."""
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError(
        "Internal Server Error"
    )
    mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR

    mocker.patch("requests.Session.get", return_value=mock_response)

    test_date = date(2025, 3, 1)
    with pytest.raises(OpenAlexRefreshError) as error_info:
        run_refresh_job(test_settings, test_date, test_date, limit=None)
    assert "HTTP exception: Internal Server Error" in str(
        error_info.value
    ), "Should see an HTTP exception error message"


def test_run_ingestion_metadata_blob_upload_job(mocker, test_settings):
    """Test the ingestion metadata blob upload job."""
    fetch_date = date(2025, 3, 1)
    stop_date = date(2025, 3, 31)
    data_source = "openalex"
    expected_blob_name = (
        "ingestion_metadata/destiny_repository_"
        f"{data_source}_ingestion_batch_from_{fetch_date}_to_{stop_date}.jsonl"
    )

    mock_blob_upload = mocker.patch(
        "refresh_requester.jobs.blob_upload", return_value=expected_blob_name
    )
    metadata = {"key": "value"}

    result = run_ingestion_metadata_blob_upload_job(
        metadata, data_source, fetch_date, stop_date
    )

    mock_blob_upload.assert_called_once_with(json.dumps(metadata), expected_blob_name)
    assert result == mock_blob_upload.return_value


def test_check_stop_date_not_before_fetch_date_success(mocker):
    """Test that check_stop_date_not_before_fetch_date does nothing when stop date is after fetch date."""
    fetch_date = date(2025, 3, 1)
    stop_date = date(2025, 3, 31)

    result = check_stop_date_not_before_fetch_date(stop_date, fetch_date)
    assert result is None


def test_check_stop_date_not_before_fetch_date_logs_warning_and_exits(mocker):
    """Test that check_stop_date_not_before_fetch_date logs a warning and exits when stop date is before fetch date."""
    mock_exit = mocker.patch("sys.exit")
    mock_logger_warning = mocker.patch("refresh_requester.jobs.logger.warning")

    fetch_date = date(2025, 3, 31)
    stop_date = date(2025, 3, 1)

    check_stop_date_not_before_fetch_date(stop_date, fetch_date)

    expected_warning_message = (
        f"Fetch date {fetch_date} is after stop date {stop_date}. "
        "No data to fetch. Exiting."
    )
    mock_logger_warning.assert_called_once_with(expected_warning_message)
    mock_exit.assert_called_once_with(0)
