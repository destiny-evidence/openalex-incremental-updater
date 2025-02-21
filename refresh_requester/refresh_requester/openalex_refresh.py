"""Module for requesting a refresh from the OpenAlex Incremental Ingestion API."""

from datetime import date

from loguru import logger
from requests.exceptions import RequestException

from refresh_requester.config import Settings, get_retry_session, get_settings

settings = get_settings()


class OpenAlexRefreshError(Exception):
    """OpenAlex Refresh Error."""


def request_refresh(settings: Settings, created_from_date: date) -> dict:
    """Request a refresh from the OpenAlex Incremental Ingestion API."""
    try:
        session = get_retry_session()
        url = settings.API_ENDPOINT + f"?created_from_date={created_from_date}"
        response = session.get(url, timeout=settings.request_timeout)
        response.raise_for_status()
    except RequestException as http_exception:
        error_message = f"Error requesting refresh: {http_exception}"
        logger.error(error_message)
        raise OpenAlexRefreshError(error_message) from http_exception
    else:
        return response.json()
