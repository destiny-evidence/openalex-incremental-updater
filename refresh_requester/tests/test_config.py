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

    settings = get_settings()

    retrieved_api_endpoint = str(settings.API_ENDPOINT)
    retrieved_storage_blob_account = settings.STORAGE_BLOB_ACCOUNT
    retrieved_storage_blob_container = settings.STORAGE_BLOB_CONTAINER

    assert (
        retrieved_api_endpoint == expected_api_endpoint
    ), "Check API endpoint environment variable is set correctly from fixture"
    assert (
        retrieved_storage_blob_account == expected_storage_blob_account
    ), "Check storage blob account environment variable is set correctly from fixture"
    assert (
        retrieved_storage_blob_container == expected_storage_blob_container
    ), "Check storage blob container environment variable is set correctly from fixture"
