from http import HTTPStatus

import pytest
from requests.exceptions import JSONDecodeError, RequestException

from refresh_requester.token_utils import TokenRequestError, get_token


def test_get_token_success(mocker, test_settings):
    """Test get_token function returns a valid token."""
    test_token_value = "test_token"  # noqa: S105
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {"access_token": test_token_value}

    mocker.patch(
        "requests.Session.get",
        return_value=mock_response,
    )

    token = get_token(test_settings)

    assert token == test_token_value, "Check that the token is returned correctly"
    mock_response.json.assert_called_once()


def test_get_token_fail_empty_access_token(mocker, test_settings):
    """Test get_token function raises an error when access_token is empty."""
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {}

    mocker.patch(
        "requests.Session.get",
        return_value=mock_response,
    )

    with pytest.raises(TokenRequestError) as error_info:
        get_token(test_settings)

    assert "Token not found in the response" in str(
        error_info.value
    ), "Check that an error is raised when access_token is empty"


def test_get_token_fail_http_error(mocker, test_settings):
    """Test get_token function raises an error on HTTP error."""
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.NOT_FOUND

    mocker.patch(
        "requests.Session.get",
        return_value=mock_response,
        side_effect=RequestException("HTTP exception"),
    )

    with pytest.raises(TokenRequestError) as error_info:
        get_token(test_settings)

    assert "HTTP exception" in str(
        error_info.value
    ), "Check that an error is raised on HTTP error"


def test_get_token_fail_value_error_on_json_read(mocker, test_settings):
    """Test get_token function raises an error on ValueError."""
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.side_effect = ValueError("Value error")

    mocker.patch(
        "requests.Session.get",
        return_value=mock_response,
    )

    with pytest.raises(TokenRequestError) as error_info:
        get_token(test_settings)

    assert "Value error" in str(
        error_info.value
    ), "Check that an error is raised on ValueError"


def test_get_token_fail_json_decode_error_on_json_read(mocker, test_settings):
    """Test get_token function raises an error on ValueError."""
    error_message = "A JSON decode error"
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.side_effect = JSONDecodeError(error_message, "", 0)

    mocker.patch(
        "requests.Session.get",
        return_value=mock_response,
    )

    with pytest.raises(TokenRequestError) as error_info:
        get_token(test_settings)

    assert error_message in str(
        error_info.value
    ), "Check that an error is raised on JSONDecodeErrors"
