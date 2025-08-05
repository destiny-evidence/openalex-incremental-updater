"""Main module for the refresh requester job."""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger

from refresh_requester.blob_storage import BlobUploadError
from refresh_requester.config import Settings, get_settings
from refresh_requester.jobs import (
    run_ingestion_metadata_blob_upload_job,
    run_openalex_refresh_blob_upload_job,
    run_refresh_job,
)
from refresh_requester.openalex_refresh import OpenAlexRefreshError
from refresh_requester.repository import (
    ImportSourceType,
    upload_blob_storage_contents_to_repository,
)
from refresh_requester.utils import get_fetch_date


def main(settings: Settings) -> None:
    """Run the refresh requester job."""
    fetch_date = get_fetch_date(settings)

    date_today = datetime.now(ZoneInfo("UTC")).date()
    data_source = ImportSourceType.OPEN_ALEX.value

    logger.info(f"RUNNING JOB - Fetching data for date: {fetch_date}")
    try:
        data = run_refresh_job(settings, fetch_date, limit=settings.limit)
    except OpenAlexRefreshError as refresh_error:
        error_message = f"Error when requesting refresh: {refresh_error}"
        logger.error(error_message)
        sys.exit(1)
    logger.info("Data fetched successfully, preparing to upload to blob storage.")
    try:
        uploaded_blob = run_openalex_refresh_blob_upload_job(
            data, fetch_date, date_today
        )
    except BlobUploadError as upload_error:
        logger.error(f"Error uploading data to blob storage: {upload_error}")
        sys.exit(1)
    logger.info(f"Data fetched for date: {fetch_date}, uploaded {date_today}")
    logger.info("Ingesting blob storage contents to repository")
    ingestion_metadata = upload_blob_storage_contents_to_repository(
        settings, blob_to_upload=uploaded_blob
    )
    logger.info(
        f"Data ingestion for {fetch_date} started for {len(ingestion_metadata.get("import_batch_ids"))} blobs."
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
        metadata_output, data_source, fetch_date
    )

    logger.success(
        f"Metadata for ingestion uploaded to blob storage: {settings.STORAGE_BLOB_CONTAINER}/{uploaded_path}"
    )


if __name__ == "__main__":
    main(get_settings())
