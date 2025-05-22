"""Module to handle Azure authentication for repository ingestion."""

import msal
from loguru import logger

from openalex_incremental_updater.core.config import Settings, get_settings


class AuthenticationError(Exception):
    """Custom exception for authentication errors."""


def get_confidential_client_application(
    settings: Settings,
) -> msal.ConfidentialClientApplication:
    """
    Get a MSAL ConfidentialClientApplication instance.

    Args:
        settings (Settings): The settings object containing Azure AD configuration.

    Returns:
        msal.ConfidentialClientApplication: An instance of the MSAL ConfidentialClientApplication.

    """
    authority = f"https://login.microsoftonline.com/{settings.TENANT_ID}"
    try:
        app = msal.ConfidentialClientApplication(
            settings.APP_REGISTRATION_APP_ID,
            authority=authority,
            client_credential=settings.APP_REGISTRATION_SECRET.get_secret_value(),
        )
    except ValueError as msal_app_value_error:
        error_message = f"Failed to create MSAL ConfidentialClientApplication: {msal_app_value_error}"
        logger.error(error_message)
        raise AuthenticationError(error_message) from msal_app_value_error
    return app


def request_token(app: msal.ConfidentialClientApplication, settings: Settings) -> dict:
    """
    Request an access token from Azure AD.

    This function uses the MSAL library to acquire a token for the specified scope.

    Args:
        app (msal.ConfidentialClientApplication): The MSAL application instance.
        settings (Settings): The settings object containing Azure AD configuration.

    Raises:
        AuthenticationError: If there is an error acquiring the token.

    Returns:
        dict: A dictionary containing the access token and its expiration time.

    """
    try:
        result = app.acquire_token_for_client(
            scopes=[f"api://{settings.AZURE_AUTH_ENVIRONMENT_ID}/.default"]
        )
    except ValueError as msal_app_value_error:
        error_message = f"Failed to acquire token: {msal_app_value_error}"
        logger.error(error_message)
        raise AuthenticationError(error_message) from msal_app_value_error
    if "access_token" in result:
        logger.debug("Access token generated successfully.")
        return result
    logger.error("Failed to generate access token.")
    error_message = f"Token Error: {result.get("error")}. Unknown token type returned."
    raise AuthenticationError(error_message)


def generate_token() -> dict:
    """
    Generate an access token for the OpenAlex API using Azure AD authentication.

    Returns:
        dict: A dictionary containing the access token and its expiration time.

    """
    settings = get_settings()
    app = get_confidential_client_application(settings)
    return request_token(app, settings)
