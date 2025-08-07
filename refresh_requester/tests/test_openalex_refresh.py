import json
from datetime import date
from http import HTTPStatus

import pytest
import requests

from refresh_requester.config import get_settings
from refresh_requester.openalex_refresh import OpenAlexRefreshError, request_refresh


def test_request_refresh_success(mocker, test_settings):
    """Test successful request refresh."""
    mocked_api_return_value = [{"key1": "value1", "key2": "value2"}]
    expected_jsonl_response = '{"key1": "value1", "key2": "value2"}'

    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = mocked_api_return_value
    mocker.patch("requests.Session.get", return_value=mock_response)

    fetch_date = date(2025, 3, 1)
    stop_date = fetch_date
    result = request_refresh(
        test_settings, fetch_date, stop_date, limit=len(mocked_api_return_value)
    )
    assert result == expected_jsonl_response


def test_refresh_request_http_error_failure(mocker, test_settings):
    """Test failed request refresh due to HTTP error."""
    settings = get_settings()
    fetch_date = date(2025, 3, 1)
    stop_date = fetch_date
    mocker.patch(
        "requests.Session.get", side_effect=requests.HTTPError("Internal Server Error")
    )

    with pytest.raises(OpenAlexRefreshError) as error:
        request_refresh(settings, fetch_date, stop_date)
    assert "HTTP exception" in str(error.value)


def test_refresh_request_invalid_json_response_failure(mocker, test_settings):
    """Test failed request refresh due to HTTP error."""
    settings = get_settings()
    fetch_date = date(2025, 3, 1)
    stop_date = fetch_date
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.side_effect = json.JSONDecodeError(
        "Expecting value", "{invalid_json}", 0
    )
    mocker.patch("requests.Session.get", return_value=mock_response)

    with pytest.raises(OpenAlexRefreshError) as error:
        request_refresh(settings, fetch_date, stop_date)
    assert "Response was not valid JSON - error decoding" in str(error.value)
