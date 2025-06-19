"""Tests for the config module, part of the core functionality of the app."""

from refresh_requester.config import get_settings


def test_get_settings(set_test_environment_variables: None) -> None:
    """
    Test the get_settings function.

    Args:
        set_test_environment_variables (None): Pytest fixture to test environment variables.

    """
    expected_api_endpoint = "http://test-host/"
    expected_storage_blob_account = "Test account name"
    expected_storage_blob_container = "Test container name"
    expected_token_endpoint = "http://test-host/auth_token"  # noqa: S105
    expected_storage_blob_account_key = "This-is-a-test-key"  # pragma: allowlist secret

    settings = get_settings()

    retrieved_api_endpoint = str(settings.API_ENDPOINT)
    retrieved_storage_blob_account = settings.STORAGE_BLOB_ACCOUNT
    retrieved_storage_blob_container = settings.STORAGE_BLOB_CONTAINER
    retrieved_token_endpoint = str(settings.TOKEN_ENDPOINT)
    retrieved_storage_blob_account_key = (
        settings.STORAGE_BLOB_ACCOUNT_KEY.get_secret_value()
    )

    assert (
        retrieved_api_endpoint == expected_api_endpoint
    ), "Check API endpoint environment variable is set correctly from fixture"
    assert (
        retrieved_storage_blob_account == expected_storage_blob_account
    ), "Check storage blob account environment variable is set correctly from fixture"
    assert (
        retrieved_storage_blob_container == expected_storage_blob_container
    ), "Check storage blob container environment variable is set correctly from fixture"
    assert (
        retrieved_token_endpoint == expected_token_endpoint
    ), "Check token endpoint environment variable is set correctly from fixture"
    assert (
        retrieved_storage_blob_account_key == expected_storage_blob_account_key
    ), "Check storage blob account key environment variable is set correctly from fixture"
