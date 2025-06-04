from typing import cast

import pytest
from msal import ConfidentialClientApplication
from pytest_mock import MockerFixture

from openalex_incremental_updater.core.auth import get_confidential_client_application
from openalex_incremental_updater.core.config import get_settings
from openalex_incremental_updater.models.auth import DestinyRepoToken


@pytest.fixture
def mocked_msal_app(
    mocker: MockerFixture, set_test_environment_variables: None
) -> ConfidentialClientApplication:
    """Return an instance of the mocked msal.ConfidentialClientApplication class."""
    mock_app_class = mocker.patch(
        "openalex_incremental_updater.core.auth.msal.ConfidentialClientApplication"
    )
    mock_instance = cast(ConfidentialClientApplication, mock_app_class.return_value)

    def acquire_token_for_client(scopes: list[str]) -> dict:
        """Mock the acquire_token_for_client method to return a fake token."""
        if scopes == ["api://a-test-valid-scope/.default"]:
            return {
                "token_type": "Bearer",
                "expires_in": 3600,
                "ext_expires_in": 3600,
                "access_token": "mocked_content",
                "token_source": "mocked_token_source",
            }
        return {
            "error": "invalid_scope",
            "error_description": "The provided value for scope is not valid. Client credential flows must have a scope",
            "timestamp": "2025-01-01 14:00:00Z",
        }

    mock_instance.acquire_token_for_client.side_effect = acquire_token_for_client
    return get_confidential_client_application(get_settings())


@pytest.fixture
def mock_destiny_repo_token(set_test_environment_variables: None) -> DestinyRepoToken:
    """Return a mocked DestinyRepoToken."""
    return DestinyRepoToken(
        token_type="Bearer",  # noqa: S106
        expires_in=3600,
        ext_expires_in=3600,
        access_token="mocked_content",  # pragma: allowlist secret # noqa: S106
        token_source="mocked_token_source",  # noqa: S106
    )
