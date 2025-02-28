"""Main module for the refresh requester job."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from loguru import logger

from refresh_requester.blob_storage import blob_upload, check_previous_file_dates
from refresh_requester.config import get_settings
from refresh_requester.openalex_refresh import OpenAlexRefreshError, request_refresh


def run_job(fetch_date: date) -> dict:
    """
    Run the refresh requester job.

    Args:
        fetch_date (date): The date to request a refresh from

    Returns:
        dict: The response from the API

    """
    settings = get_settings()
    try:
        json_response = request_refresh(settings, fetch_date)
        logger.info(f"Refresh request successful for date {fetch_date}")
    except OpenAlexRefreshError as refresh_error:
        error_message = f"Error requesting refresh: {refresh_error}"
        logger.error(error_message)
        return {"error": error_message}
    return json_response


def main() -> None:
    """Run the refresh requester job."""
    fetch_date = check_previous_file_dates()
    data = run_job(fetch_date)

    date_today = datetime.now(ZoneInfo("UTC")).date()
    blob_upload(data, date_today)


if __name__ == "__main__":
    main()
