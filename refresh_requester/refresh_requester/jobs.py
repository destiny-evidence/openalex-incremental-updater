"""Define the job to request a refresh from OpenAlex."""

from datetime import date

from loguru import logger

from refresh_requester.config import get_settings
from refresh_requester.openalex_refresh import OpenAlexRefreshError, request_refresh


def run_refresh_job(fetch_date: date, limit: int | None) -> str:
    """
    Run the refresh requester job.

    Args:
        fetch_date (date): The date to request a refresh from
        limit (int | None): The maximum number of records to return

    Returns:
        str: JSONL-ified response from the API.

    """
    settings = get_settings()
    try:
        jsonl_response = request_refresh(settings, fetch_date, limit)
        logger.info(f"Refresh request successful for date {fetch_date}")
    except OpenAlexRefreshError as refresh_error:
        error_message = f"Error when requesting refresh: {refresh_error}"
        logger.error(error_message)
        return error_message

    return jsonl_response
