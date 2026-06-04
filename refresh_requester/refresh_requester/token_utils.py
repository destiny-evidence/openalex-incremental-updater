"""Obtain a token for the DESTINY Repository API from the openalex-incremental-updater API."""

import requests

from refresh_requester.config import Settings, get_retry_session


class TokenRequestError(Exception):
    """Custom exception for token request errors."""


def get_token(settings: Settings) -> str:
    """
    Get a token for the DESTINY Repository API.

    Args:
        settings (Settings): Pydantic settings object containing configuration.

    Raises:
        TokenRequestError: An error occurred while requesting the token, with a descriptive message.

    Returns:
        str: The access token retrieved from the DESTINY Repository API.

    """
    session = get_retry_session(settings)

    url = str(settings.TOKEN_ENDPOINT)
    try:
        response = session.get(url, timeout=settings.request_timeout)
        response.raise_for_status()
        token = response.json().get("access_token", None)
        if not token:
            message = "Token not found in the response"
            raise TokenRequestError(message)
    except requests.RequestException as http_exception:
        error_message = f"HTTP exception: {http_exception}"
        raise TokenRequestError(error_message) from http_exception
    except ValueError as value_error:
        error_message = f"Value error: {value_error}"
        raise TokenRequestError(error_message) from value_error
    return token
