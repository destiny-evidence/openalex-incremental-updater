"""Module for requesting a refresh from the OpenAlex Incremental Ingestion API."""

from datetime import date
from json.decoder import JSONDecodeError

from loguru import logger
from requests.exceptions import RequestException

from refresh_requester.config import Settings, get_retry_session


class OpenAlexRefreshError(Exception):
    """OpenAlex Refresh Error."""


def poll_job_status(settings: Settings, job_submission_id: str) -> dict:
    """
    Poll the status of the refresh job.

    Args:
        settings (Settings): The settings to use for the job.
        job_submission_id (str): The ID of the job submission to poll.

    Returns:
        dict: The JSON response from the API containing job status.

    """
    try:
        session = get_retry_session()
        url = str(settings.API_ENDPOINT) + f"/api/v1/jobs/{job_submission_id}"

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
        return response_json


def request_refresh(
    settings: Settings,
    created_from_date: date,
    stop_date: date,
    limit: int | None = None,
) -> dict:
    """
    Request a refresh from the OpenAlex Incremental Ingestion API.

    Args:
        settings (Settings): Pydantic settings
        created_from_date (date): The date to request a refresh from (inclusive)
        stop_date (date): The date to request a refresh to (inclusive)
        limit (int | None): The maximum number of records to return
    Raises:
        OpenAlexRefreshError: A descriptive error message

    Returns:
        dict: The response from the API

    """
    try:
        session = get_retry_session()
        url = (
            str(settings.API_ENDPOINT)
            + "/api/v1/openalex_works_ingest_date_range"
            + f"?start_date={created_from_date}&end_date={stop_date}&ingest_type=created"
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
        return response_json
