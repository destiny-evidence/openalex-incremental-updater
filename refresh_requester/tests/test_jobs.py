import json
from datetime import date
from http import HTTPStatus

import pytest
import requests

from refresh_requester.jobs import (
    run_ingestion_metadata_blob_upload_job,
    run_refresh_job,
)
from refresh_requester.openalex_refresh import OpenAlexRefreshError


def test_run_refresh_job_success(mocker, test_settings):
    """Test a successful job run."""
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mocked_api_return_value = [
        {"key1": "value1", "key2": "value2"},
        {"key3": "value3", "key4": "value4"},
    ]
    expected_jsonl_response = "\n".join(
        [json.dumps(record) for record in mocked_api_return_value]
    )

    mock_response.json.return_value = mocked_api_return_value

    mocker.patch("requests.Session.get", return_value=mock_response)

    test_date = date(2025, 3, 1)
    result = run_refresh_job(
        test_settings, test_date, test_date, limit=len(mocked_api_return_value)
    )
    assert result == expected_jsonl_response


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
