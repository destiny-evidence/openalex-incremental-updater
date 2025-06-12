"""Main module for the refresh requester job."""

from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from loguru import logger

from refresh_requester.blob_storage import blob_upload, check_previous_file_dates
from refresh_requester.config import get_settings
from refresh_requester.jobs import run_job

load_dotenv(override=True)


def main() -> None:
    """Run the refresh requester job."""
    fetch_date = (
        check_previous_file_dates()
        if not get_settings().fetch_date
        else get_settings().fetch_date
    )
    logger.info(f"RUNNING JOB - Fetching data for date: {fetch_date}")
    data = run_job(fetch_date, limit=get_settings().limit)

    date_today = datetime.now(ZoneInfo("UTC")).date()
    blob_upload(data, fetch_date, date_today)
    logger.info(
        f"JOB COMPLETED - Data fetched for date: {fetch_date}, uploaded {date_today}"
    )


if __name__ == "__main__":
    main()
