"""Define the job to request a refresh from OpenAlex."""

import json
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from loguru import logger

from refresh_requester.blob_storage import BlobUploadError, blob_upload
from refresh_requester.config import Settings
from refresh_requester.openalex_refresh import OpenAlexRefreshError, request_refresh
from refresh_requester.repository import (
    ImportSourceType,
    upload_blob_storage_contents_to_repository,
)
from refresh_requester.utils import format_metadata_blob_name, get_fetch_date


def run_refresh_job(
    settings: Settings, fetch_date: date, stop_date: date, limit: int | None
) -> str:
    """
    Run the refresh requester job.

    Args:
        fetch_date (date): The date to request a refresh from (inclusive)
        stop_date (date): The date to request a refresh to (inclusive)
        limit (int | None): The maximum number of records to return

    Returns:
        str: JSONL-ified response from the API.

    """
    jsonl_response = request_refresh(settings, fetch_date, stop_date, limit)
    logger.info(f"Refresh request successful for date {fetch_date}")
    return jsonl_response


def run_openalex_refresh_blob_upload_job(
    data: str, fetch_date: date, stop_date: date, refresh_date: date
) -> str:
    """
    Run the blob upload job.

    Args:
        data (str): The response from the API, converted to JSON-lines
        fetch_date (date): The date at which the data was fetched
        stop_date (date): The date at which the data was fetched until (inclusive)
        refresh_date (date): The date at which the data was refreshed

    Returns:
        str: The filename of the uploaded blob

    """
    blob_name = f"openalex_refresh_from_date_{fetch_date}_to_{stop_date}_refreshed_on_{refresh_date}.jsonl"
    uploaded_blob = blob_upload(data, blob_name)
    logger.info(
        f"Data uploaded to blob storage from {fetch_date} to {stop_date}, uploaded {refresh_date}"
    )
    logger.info(f"Uploaded blob: {uploaded_blob}")
    return uploaded_blob


def run_ingestion_metadata_blob_upload_job(
    metadata: dict, data_source: str, fetch_date: date, stop_date: date | None = None
) -> str:
    """
    Run the metadata blob upload job.

    Args:
        metadata (dict): The metadata to upload, including:
        data_source (str): The source of the metadata, e.g., "openalex", "solr"
        fetch_date (date): The from_created_date of the metadata
        stop_date (date | None): The to_created_date of the metadata, if applicable

    Returns:
        str: The path of the uploaded blob

    """
    blob_name = format_metadata_blob_name(data_source, fetch_date, stop_date)
    uploaded_blob = blob_upload(json.dumps(metadata), blob_name)
    logger.info(f"Uploaded destiny repository ingestion metadata: {uploaded_blob}")
    return uploaded_blob


def run_full_pipeline(settings: Settings) -> None:
    """
    Run the full refresh requester job pipeline.

    Args:
        settings (Settings): The settings to use for the job.

    """
    fetch_date = get_fetch_date(settings)
    stop_date = (
        settings.stop_date
        if settings.stop_date
        else datetime.now(ZoneInfo("UTC")).date()
    )

    date_today = datetime.now(ZoneInfo("UTC")).date()
    data_source = ImportSourceType.OPEN_ALEX.value

    logger.info(f"RUNNING JOB - Fetching data from {fetch_date} to {stop_date}")
    try:
        data = run_refresh_job(settings, fetch_date, stop_date, limit=settings.limit)
    except OpenAlexRefreshError as refresh_error:
        error_message = f"Error when requesting refresh: {refresh_error}"
        logger.error(error_message)
        sys.exit(1)
    logger.info("Data fetched successfully, preparing to upload to blob storage.")
    try:
        uploaded_blob = run_openalex_refresh_blob_upload_job(
            data, fetch_date, stop_date, date_today
        )
    except BlobUploadError as upload_error:
        logger.error(f"Error uploading data to blob storage: {upload_error}")
        sys.exit(1)
    logger.info(f"Data fetched for date: {fetch_date}, uploaded {date_today}")
    logger.info("Ingesting blob storage contents to repository")
    ingestion_metadata = upload_blob_storage_contents_to_repository(
        settings, blob_to_upload=uploaded_blob
    )
    number_of_blobs = len(ingestion_metadata.get("import_batch_ids"))
    logger.info(
        f"Data ingestion from {fetch_date} to {stop_date} started for {number_of_blobs} blobs."
    )

    metadata_output = {
        "blob_name": uploaded_blob,
        "import_record": ingestion_metadata.get("import_record").model_dump(mode="json")
        if ingestion_metadata.get("import_record")
        else None,
        "import_batch_id": str(next(iter(ingestion_metadata["import_batch_ids"])))
        if ingestion_metadata.get("import_batch_ids")
        else None,
    }
    uploaded_path = run_ingestion_metadata_blob_upload_job(
        metadata_output, data_source, fetch_date, stop_date
    )

    logger.success(
        f"Metadata for ingestion uploaded to blob storage: {settings.STORAGE_BLOB_CONTAINER}/{uploaded_path}"
    )
