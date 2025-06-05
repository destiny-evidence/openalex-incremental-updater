"""Define the job to request a refresh from OpenAlex."""

from datetime import date

from loguru import logger

from refresh_requester.blob_storage import blob_upload
from refresh_requester.config import get_settings
from refresh_requester.openalex_refresh import request_refresh


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

    jsonl_response = request_refresh(settings, fetch_date, limit)
    logger.info(f"Refresh request successful for date {fetch_date}")
    return jsonl_response


def run_blob_upload_job(data: str, fetch_date: date, refresh_date: date) -> None:
    """
    Run the blob upload job.

    Args:
        data (str): The response from the API, converted to JSON-lines
        fetch_date (date): The date at which the data was fetched
        refresh_date (date): The date at which the data was refreshed

    """
    blob_upload(data, fetch_date, refresh_date)
    logger.info(
        f"Data uploaded to blob storage for date: {fetch_date}, uploaded {refresh_date}"
    )


def run_repository_data_ingestion(fetch_date: date, refresh_date: date) -> None:
    """
    Run the repository data ingestion job.

    Args:
        fetch_date (date): The date at which the data was fetched
        refresh_date (date): The date at which the data was refreshed

    """
    from refresh_requester.repository import DestinyRepositoryContentUploader

    uploader = DestinyRepositoryContentUploader(get_settings())
    uploader.ingest_data(fetch_date, refresh_date)
    logger.info(
        f"Repository data ingestion completed for fetch date: {fetch_date}, refresh date: {refresh_date}"
    )
