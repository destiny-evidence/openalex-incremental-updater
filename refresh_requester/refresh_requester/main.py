"""Main module for the refresh requester job."""

from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger

from refresh_requester.blob_storage import blob_upload, check_previous_file_dates
from refresh_requester.jobs import run_job


def main() -> None:
    """Run the refresh requester job."""
    fetch_date = check_previous_file_dates()
    logger.info(f"RUNNING JOB - Fetching data for date: {fetch_date}")
    data = run_job(fetch_date, limit=5)

    date_today = datetime.now(ZoneInfo("UTC")).date()
    blob_upload(data, date_today)
    logger.info(
        f"JOB COMPLETED - Data fetched for date: {fetch_date}, uploaded {date_today}"
    )


if __name__ == "__main__":
    main()
