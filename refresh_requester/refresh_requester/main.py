"""Main module for the refresh requester job."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger

from refresh_requester.config import get_settings
from refresh_requester.openalex_refresh import OpenAlexRefreshError, request_refresh


def run_job() -> dict:
    """Run the refresh requester job."""
    yesterday = datetime.now(tz=ZoneInfo("UTC")).date() - timedelta(days=1)
    settings = get_settings()
    try:
        response = request_refresh(settings)
        logger.info(f"Refresh request successful for date {yesterday}")
        return response.json()
    except OpenAlexRefreshError as refresh_error:
        error_message = f"Error requesting refresh: {refresh_error}"
        logger.error(error_message)
        return {"error": error_message}


if __name__ == "__main__":
    run_job()
