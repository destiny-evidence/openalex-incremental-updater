"""Tests for the config module, part of the core functionality of the app."""

import pytest
from pydantic import HttpUrl, ValidationError

from openalex_incremental_updater.core.config import Settings, get_settings


def test_get_settings(set_test_environment_variables: None) -> None:
    """
    Test the get_settings function.

    Args:
        set_test_environment_variables (None): Pytest fixture to test environment variables.

    """
    expected_cors_origin = "http://test-host/"
    expected_project_name = "Test project name"

    settings = get_settings()
    cors_origin_string = str(settings.cors_origins[0])
    retrieved_project_name = settings.PROJECT_NAME

    assert len(settings.cors_origins) == 1, "Check only one CORS origin is set"
    assert (
        cors_origin_string == expected_cors_origin
    ), "Check CORS origin environment variable is set correctly from fixture"
    assert (
        retrieved_project_name == expected_project_name
    ), "Check project name environment variable is set correctly from fixture"


def test_cors_origins_valid_list(set_test_environment_variables: None) -> None:
    """Test setting CORS origins from a valid list of URLs."""
    test_urls_string_list = ["https://example.com", "https://another.com"]
    test_urls_httpurl_list = [HttpUrl(url) for url in test_urls_string_list]

    settings = Settings(cors_origins=test_urls_string_list)

    assert (
        settings.cors_origins == test_urls_httpurl_list
    ), "Check CORS origins are valid after setting from test URL list of strings"


def test_cors_origins_valid_comma_string(set_test_environment_variables: None) -> None:
    """Test setting CORS origins from a comma-separated string of valid URLs."""
    test_urls_comma_separated_string = "https://example.com,https://another.com"

    test_list_from_comma_separated_string = test_urls_comma_separated_string.split(",")
    test_httpurl_list = [HttpUrl(url) for url in test_list_from_comma_separated_string]
    settings = Settings(cors_origins=test_urls_comma_separated_string)

    assert (
        settings.cors_origins == test_httpurl_list
    ), "Check CORS origins are valid after setting from comma-separated string"


def test_cors_origins_entire_invalid_string() -> None:
    """Test setting CORS origins from a string of entirely invalid URLs."""
    test_invalid_string_urls = "not_a_url"
    with pytest.raises(ValidationError) as invalid_url_error:
        Settings(cors_origins=test_invalid_string_urls)
    assert "Input should be a valid URL" in str(
        invalid_url_error.value
    ), "Check invalid URL string raises validation error"


def test_cors_origins_string_contains_invalid_url() -> None:
    """Test setting CORS origins from a string containing a mixture of valid and invalid URLs."""
    test_invalid_string_urls = "http://valid_url,not_a_url"
    with pytest.raises(ValidationError) as invalid_url_error:
        Settings(cors_origins=test_invalid_string_urls)
    assert "Input should be a valid URL" in str(
        invalid_url_error.value
    ), "Check invalid URL string raises validation error"


def test_cors_origins_invalid_json() -> None:
    """Test setting CORS origins from a JSON-like string of invalid URLs."""
    test_json_invalid_url = '["not_a_url"]'
    with pytest.raises(ValidationError) as invalid_json_url_error:
        Settings(cors_origins=test_json_invalid_url)
    assert "Input should be a valid URL" in str(
        invalid_json_url_error.value
    ), "Check invalid URL in JSON raises validation error"
