import json
from datetime import date
from http import HTTPStatus
from json.decoder import JSONDecodeError
from uuid import uuid4

import pytest
import requests
from time_machine import travel

from refresh_requester.openalex_refresh import (
    OpenAlexRefreshError,
    create_composite_url,
    poll_job_status,
    request_refresh,
)


@travel("2025-08-18T12:00:00+00")
def test_request_refresh_success(mocker, test_settings):
    """Test successful request refresh."""
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

    fetch_date = date(2025, 3, 1)
    stop_date = fetch_date
    result = request_refresh(
        test_settings, fetch_date, stop_date, limit=len(mocked_api_return_value)
    )
    assert result == mocked_api_return_value


def test_refresh_request_http_error_failure(mocker, test_settings):
    """Test failed request refresh due to HTTP error."""
    fetch_date = date(2025, 3, 1)
    stop_date = fetch_date
    mocker.patch(
        "requests.Session.get", side_effect=requests.HTTPError("Internal Server Error")
    )

    with pytest.raises(OpenAlexRefreshError) as error:
        request_refresh(test_settings, fetch_date, stop_date)
    assert "HTTP exception" in str(error.value)


@pytest.mark.parametrize(
    ("base_url", "url_path", "expected_url"),
    [
        (
            "https://api.example.com/",
            "/api//v1/resource",
            "https://api.example.com/api/v1/resource",
        ),
        (
            "https://api.example.com",
            "api/v1/resource",
            "https://api.example.com/api/v1/resource",
        ),
        (
            "https://api.example.com////",
            "///api/v1/resource",
            "https://api.example.com/api/v1/resource",
        ),
        (
            "https://api.example.com////",
            "/////api//v1//resource",
            "https://api.example.com/api/v1/resource",
        ),
    ],
)
def test_create_composite_url(base_url, url_path, expected_url):
    """Test create_composite_url function."""
    result = create_composite_url(base_url, url_path)
    assert result == expected_url


def test_refresh_request_invalid_json_response_failure(mocker, test_settings):
    """Test failed request refresh due to HTTP error."""
    fetch_date = date(2025, 3, 1)
    stop_date = fetch_date
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.side_effect = json.JSONDecodeError(
        "Expecting value", "{invalid_json}", 0
    )
    mocker.patch("requests.Session.get", return_value=mock_response)

    with pytest.raises(OpenAlexRefreshError) as error:
        request_refresh(test_settings, fetch_date, stop_date)
    assert "Response was not valid JSON - error decoding" in str(error.value)


def test_poll_job_status_succeeded(mocker, test_settings):
    """Test polling job status."""
    settings = test_settings.model_copy(deep=True)
    job_id = uuid4()
    mocker.patch(
        "requests.Session.get",
        return_value=mocker.Mock(
            status_code=HTTPStatus.OK, json=lambda: {"status": "succeeded"}
        ),
    )

    result = poll_job_status(settings, job_id)
    assert result == {"status": "succeeded"}


@pytest.mark.parametrize(
    ("base_url"),
    [
        ("ht!tp://invalid-url"),
        ("https: //api.example.com"),
        ("httpsapi.example.com"),
        ("foo"),
        ("foo://bar"),
    ],
)
def test_poll_job_status_failed_url_validation(mocker, test_settings, base_url):
    """Test polling job status."""
    settings = test_settings.model_copy(deep=True)
    job_id = uuid4()
    settings.API_ENDPOINT = base_url
    with pytest.raises(OpenAlexRefreshError) as error:
        poll_job_status(settings, job_id)
    assert "Invalid URL constructed" in str(error.value)


def test_poll_job_status_failed_request_exception(mocker, test_settings):
    """Test polling job status."""
    settings = test_settings.model_copy(deep=True)
    job_id = uuid4()
    mocker.patch(
        "requests.Session.get",
        side_effect=requests.RequestException("HTTP error occurred"),
    )

    with pytest.raises(OpenAlexRefreshError) as error:
        poll_job_status(settings, job_id)
    assert "HTTP error occurred" in str(error.value)


def test_poll_job_status_failed_json_decode_error(mocker, test_settings):
    """Test polling job status."""
    settings = test_settings.model_copy(deep=True)
    job_id = uuid4()
    mocker.patch(
        "requests.Session.get",
        side_effect=JSONDecodeError("JSON Decode Error", "invalid_json", 0),
    )

    with pytest.raises(OpenAlexRefreshError) as error:
        poll_job_status(settings, job_id)
    assert "Response was not valid JSON" in str(error.value)
