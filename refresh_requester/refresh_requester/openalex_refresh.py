"""Module for requesting a refresh from the OpenAlex Incremental Ingestion API."""

from datetime import date
from json.decoder import JSONDecodeError

from loguru import logger
from requests.exceptions import RequestException

from refresh_requester.config import Settings, get_retry_session
from refresh_requester.data import convert_json_to_jsonl


class OpenAlexRefreshError(Exception):
    """OpenAlex Refresh Error."""


def request_refresh(
    settings: Settings, created_from_date: date, limit: int | None = None
) -> str:
    """
    Request a refresh from the OpenAlex Incremental Ingestion API.

    Args:
        settings (Settings): Pydantic settings
        created_from_date (date): The date to request a refresh from
        limit (int | None): The maximum number of records to return
    Raises:
        OpenAlexRefreshError: A descriptive error message

    Returns:
        list[dict]: The response from the API

    """
    try:
        session = get_retry_session()
        url = (
            str(settings.API_ENDPOINT)
            + f"?fetch_date={created_from_date}&ingest_type=created"
        )
        if limit:
            url += f"&limit={limit}"
        response = session.get(url, timeout=settings.request_timeout)
        response.raise_for_status()
        response_json = response.json()
    except RequestException as http_exception:
        error_message = f"HTTP exception: {http_exception}"
        logger.error(error_message)
        raise OpenAlexRefreshError(error_message) from http_exception
    except JSONDecodeError as json_decode_error:
        error_message = (
            f"Response was not valid JSON - error decoding: {json_decode_error}"
        )
        logger.error(error_message)
        raise OpenAlexRefreshError(error_message) from json_decode_error
    else:
        return convert_json_to_jsonl(response_json)
