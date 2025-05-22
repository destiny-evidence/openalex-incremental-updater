import pytest
from msal import ConfidentialClientApplication
from pytest_mock import MockerFixture

from openalex_incremental_updater.core.auth import (
    AuthenticationError,
    generate_token,
    get_confidential_client_application,
    request_token,
)
from openalex_incremental_updater.core.config import get_settings


def test_get_confidential_client_application_fails_with_fake_variables(
    set_test_environment_variables: None,
) -> None:
    """
    Test the get_confidential_client_application function.

    This test checks if the function correctly creates a MSAL ConfidentialClientApplication
    instance using the provided settings.

    Args:
        set_test_environment_variables (None): Fixture to set environment variables.

    """
    settings = get_settings()
    expected_error_message = "Failed to create MSAL ConfidentialClientApplication"
    with pytest.raises(AuthenticationError) as auth_error:
        get_confidential_client_application(settings)
    assert expected_error_message in str(
        auth_error.value
    ), "Expected if we don't mock, we use fake values"


def test_get_confidential_client_application_success(
    mocker: MockerFixture,
    set_test_environment_variables: None,
) -> None:
    """
    Test the get_confidential_client_application function.

    This test checks if the function correctly returns a MSAL ConfidentialClientApplication using a mocked
    instance.
    This is a success case where the function should return a valid instance.

    Args:
        set_test_environment_variables (None): Fixture to set environment variables.

    """
    settings = get_settings()
    mocked_app_creation = mocker.patch(
        "openalex_incremental_updater.core.auth.msal.ConfidentialClientApplication",
    )
    app = get_confidential_client_application(settings)
    assert (
        app is not None
    ), "Expected a valid MSAL ConfidentialClientApplication instance"
    assert (
        mocked_app_creation.call_count == 1
    ), "Expected the MSAL app creation to be called once"


def test_request_token_success(
    mocked_msal_app: ConfidentialClientApplication,
    set_test_environment_variables: None,
) -> None:
    """
    Test the request_token function.

    This test checks if the function correctly raises an AuthenticationError when
    trying to acquire a token with fake variables.

    Args:
        set_test_environment_variables (None): Fixture to set environment variables.

    """
    settings = get_settings()
    settings.AZURE_AUTH_ENVIRONMENT_ID = "a-test-valid-scope"
    token = request_token(mocked_msal_app, settings)
    expected_content = "mocked_content"
    assert token["access_token"] == expected_content, "Expected a valid access token"


def test_request_token_fails_invalid_scope(
    mocked_msal_app: ConfidentialClientApplication,
    set_test_environment_variables: None,
) -> None:
    """
    Test the request_token function.

    This test checks if the function correctly raises an AuthenticationError when
    trying to acquire a token with fake variables.

    Args:
        set_test_environment_variables (None): Fixture to set environment variables.

    """
    settings = get_settings()
    settings.AZURE_AUTH_ENVIRONMENT_ID = "a-test-invalid-scope"
    with pytest.raises(AuthenticationError) as auth_error:
        request_token(mocked_msal_app, settings)
    assert "invalid_scope" in str(auth_error.value), "Expected an invalid scope error"


def test_generate_token_success(
    mocker: MockerFixture,
    mocked_msal_app: ConfidentialClientApplication,
    set_test_environment_variables: None,
) -> None:
    """
    Test the generate_token function.

    This test checks if the function correctly generates a token using the provided settings.

    Args:
        set_test_environment_variables (None): Fixture to set environment variables.

    """
    expected_type = "Bearer"
    expected_token_expiry_seconds = 3600
    expected_content = "mocked_content"
    settings = get_settings()
    settings.AZURE_AUTH_ENVIRONMENT_ID = "a-test-valid-scope"
    mocker.patch(
        "openalex_incremental_updater.core.auth.get_confidential_client_application",
        return_value=mocked_msal_app,
    )
    mocker.patch(
        "openalex_incremental_updater.core.auth.get_settings", return_value=settings
    )
    token = generate_token()
    assert token["token_type"] == expected_type, "Expected a Bearer token type"
    assert (
        token["expires_in"] == expected_token_expiry_seconds
    ), "Expected a valid expiration time"
    assert token["access_token"] == expected_content, "Expected a valid access token"
