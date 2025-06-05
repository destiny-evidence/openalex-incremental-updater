import json
from datetime import date
from http import HTTPStatus

import requests

from refresh_requester.jobs import run_refresh_job


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
    result = run_refresh_job(test_date, limit=len(mocked_api_return_value))
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
    result = run_refresh_job(test_date, limit=None)
    assert (
        result == "Error when requesting refresh: HTTP exception: Internal Server Error"
    ), "Should see an HTTP exception error message"
