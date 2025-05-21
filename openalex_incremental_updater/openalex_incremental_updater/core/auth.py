"""Module to handle Azure authentication for repository ingestion."""

import msal
from loguru import logger

from openalex_incremental_updater.core.config import get_settings


def generate_token() -> dict:
    """
    Generate an access token for the OpenAlex API using Azure AD authentication.

    Returns:
        dict: A dictionary containing the access token and its expiration time.

    """
    settings = get_settings()

    authority = f"https://login.microsoftonline.com/{settings.TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        settings.APP_REGISTRATION_APP_ID,
        authority=authority,
        client_credential=settings.APP_REGISTRATION_SECRET.get_secret_value(),
    )
    result = app.acquire_token_for_client(
        scopes=[f"api://{settings.AZURE_AUTH_ENVIRONMENT_ID}/.default"]
    )
    if "access_token" in result:
        logger.debug("Access token generated successfully.")
        return result
    logger.error("Failed to generate access token.")
    raise ValueError(result.get("error_description", "Unknown error"))
