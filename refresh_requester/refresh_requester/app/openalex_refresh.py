"""Module for requesting a refresh from the OpenAlex Incremental Ingestion API."""

import requests
from loguru import logger
from requests.adapters import Retry

from refresh_requester.app.config import get_settings

settings = get_settings()


class OpenAlexRefreshError(Exception):
    """OpenAlex Refresh Error."""


def get_retry_session() -> requests.Session:
    """
    Return a requests session with retry settings enabled.

    Returns:
        requests.Session: A requests session with retry settings enabled.

    """
    session = requests.Session()
    retries = Retry(
        total=settings.retry_total,
        backoff_factor=settings.retry_backoff_factor,
        status_forcelist=settings.retry_status_list,
    )

    session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))
    return session


def request_refresh() -> None:
    """Request a refresh from the OpenAlex Incremental Ingestion API."""
    try:
        session = get_retry_session()
        response = session.get(settings.API_ENDPOINT, timeout=settings.request_timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as http_exception:
        error_message = f"Error requesting refresh: {http_exception}"
        logger.error(error_message)
        raise OpenAlexRefreshError(error_message) from http_exception
    else:
        return response.json()
