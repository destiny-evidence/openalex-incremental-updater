"""Define the job to request a refresh from OpenAlex."""

import json
import sys
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from loguru import logger

from refresh_requester.blob_storage import blob_upload
from refresh_requester.config import Settings
from refresh_requester.openalex_refresh import (
    OpenAlexRefreshError,
    poll_job_status,
    request_refresh,
)
from refresh_requester.repository import (
    ImportSourceType,
    upload_blob_storage_contents_to_repository,
)
from refresh_requester.utils import format_metadata_blob_name, get_fetch_date


def run_refresh_job(
    settings: Settings, fetch_date: date, stop_date: date, limit: int | None
) -> dict:
    """
    Run the refresh requester job.

    Args:
        fetch_date (date): The date to request a refresh from (inclusive)
        stop_date (date): The date to request a refresh to (inclusive)
        limit (int | None): The maximum number of records to return

    Returns:
        dict: JSON response from the API.

    """
    json_response = request_refresh(settings, fetch_date, stop_date, limit)
    logger.info(f"Refresh request submitted for dates {fetch_date} to {stop_date}")
    return json_response


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
    polling_interval = settings.polling_interval
    fetch_date = get_fetch_date(settings)
    stop_date = settings.stop_date if settings.stop_date else fetch_date

    date_today = datetime.now(ZoneInfo("UTC")).date()
    data_source = ImportSourceType.OPEN_ALEX.value

    logger.info(f"RUNNING JOB - Fetching data from {fetch_date} to {stop_date}")
    try:
        job_submission = run_refresh_job(
            settings, fetch_date, stop_date, limit=settings.limit
        )
    except OpenAlexRefreshError as refresh_error:
        error_message = f"Error when requesting refresh: {refresh_error}"
        logger.error(error_message)
        sys.exit(1)
    job_submission_id = job_submission.get("job_id")
    job_complete = False
    job_status_json = poll_job_status(settings, job_submission_id)
    while not job_complete:
        job_status_json = poll_job_status(settings, job_submission_id)
        logger.info(f"Job Progress: {job_status_json.get('progress')}")
        if job_status_json.get("status").upper() == "SUCCEEDED":
            job_complete = True
        elif job_status_json.get("status").upper() == "FAILED":
            error_message = f"Job failed: {job_status_json.get('error_message')}"
            logger.error(error_message)
            sys.exit(1)
        elif job_status_json.get("status").upper() == "CANCELLED":
            logger.warning("Job was cancelled.")
            sys.exit(1)
        time.sleep(polling_interval)
    uploaded_blob = job_status_json.get("result")
    if not uploaded_blob:
        logger.error("No data returned from job.")
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
    logger.info("Uploading ingestion metadata to blob storage.")
    uploaded_path = run_ingestion_metadata_blob_upload_job(
        metadata_output, data_source, fetch_date, stop_date
    )

    logger.success(
        f"Metadata for ingestion uploaded to blob storage: {settings.STORAGE_BLOB_CONTAINER}/{uploaded_path}"
    )
