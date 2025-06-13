"""Main module for the refresh requester job."""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from loguru import logger

from refresh_requester.blob_storage import BlobUploadError, check_previous_file_dates
from refresh_requester.config import Settings, get_settings
from refresh_requester.jobs import run_blob_upload_job, run_refresh_job
from refresh_requester.openalex_refresh import OpenAlexRefreshError
from refresh_requester.repository import upload_blob_storage_contents_to_repository


def main(settings: Settings) -> None:
    """Run the refresh requester job."""
    fetch_date = (
        check_previous_file_dates() if not settings.fetch_date else settings.fetch_date
    )

    date_today = datetime.now(ZoneInfo("UTC")).date()

    logger.info(f"RUNNING JOB - Fetching data for date: {fetch_date}")
    try:
        data = run_refresh_job(fetch_date, limit=get_settings().limit)
    except OpenAlexRefreshError as refresh_error:
        error_message = f"Error when requesting refresh: {refresh_error}"
        logger.error(error_message)
        sys.exit(1)
    logger.info("Data fetched successfully, preparing to upload to blob storage.")
    try:
        uploaded_blob = run_blob_upload_job(data, fetch_date, date_today)
    except BlobUploadError as upload_error:
        logger.error(f"Error uploading data to blob storage: {upload_error}")
        sys.exit(1)

    logger.info("Uploading blob storage contents to repository")
    upload_blob_storage_contents_to_repository(
        settings, max_retries=5, blob_to_upload=uploaded_blob
    )
    logger.success(
        f"JOB COMPLETED - Data fetched for date: {fetch_date}, uploaded {date_today}"
    )


if __name__ == "__main__":
    load_dotenv(override=True)
    main(get_settings())
