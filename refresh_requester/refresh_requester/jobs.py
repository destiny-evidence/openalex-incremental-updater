"""Define the job to request a refresh from OpenAlex."""

import json
from datetime import date

from loguru import logger

from refresh_requester.blob_storage import blob_upload
from refresh_requester.config import Settings
from refresh_requester.openalex_refresh import request_refresh


def run_refresh_job(settings: Settings, fetch_date: date, limit: int | None) -> str:
    """
    Run the refresh requester job.

    Args:
        fetch_date (date): The date to request a refresh from
        limit (int | None): The maximum number of records to return

    Returns:
        str: JSONL-ified response from the API.

    """
    jsonl_response = request_refresh(settings, fetch_date, limit)
    logger.info(f"Refresh request successful for date {fetch_date}")
    return jsonl_response


def run_openalex_refresh_blob_upload_job(
    data: str, fetch_date: date, refresh_date: date
) -> str:
    """
    Run the blob upload job.

    Args:
        data (str): The response from the API, converted to JSON-lines
        fetch_date (date): The date at which the data was fetched
        refresh_date (date): The date at which the data was refreshed

    Returns:
        str: The filename of the uploaded blob

    """
    blob_name = (
        f"openalex_refresh_from_date_{fetch_date}_refreshed_on_{refresh_date}.jsonl"
    )
    uploaded_blob = blob_upload(data, blob_name)
    logger.info(
        f"Data uploaded to blob storage for date: {fetch_date}, uploaded {refresh_date}"
    )
    logger.info(f"Uploaded blob: {uploaded_blob}")
    return uploaded_blob


def run_ingestion_metadata_blob_upload_job(
    metadata: dict, data_source: str, refresh_date: date
) -> str:
    """
    Run the metadata blob upload job.

    Args:
        metadata (dict): The metadata to upload, including:
        data_source (str): The source of the metadata, e.g., "openalex", "solr"
        refresh_date (date): The date at which the data was refreshed

    Returns:
        str: The path of the uploaded blob

    """
    blob_name = f"ingestion_metadata/destiny_repository_{data_source}_ingestion_batch_{refresh_date}.jsonl"
    uploaded_blob = blob_upload(json.dumps(metadata), blob_name)
    logger.info(f"Uploaded destiny repository ingestion metadata: {uploaded_blob}")
    return uploaded_blob
