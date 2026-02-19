"""Register uploaded blobs with the DESTINY Repository."""

from uuid import UUID

from destiny_sdk.imports import ImportRecordRead
from loguru import logger
from pydantic import BaseModel, Field

from openalex_snapshot_processor.config import get_settings
from refresh_requester.repository import (
    DestinyRepositoryImportError,
    ImportSourceType,
    upload_blob_storage_contents_to_repository,
)


class ImportReport(BaseModel):
    """Report model for tracking the status of the import process."""

    import_record: ImportRecordRead = Field(
        ...,
        description=(
            "The import record created in the DESTINY Repository for this import process."
        ),
    )
    import_batch_ids: list[UUID] = Field(
        ...,
        description=(
            "A list of the IDs of the import batches created in the DESTINY Repository for this import process."
        ),
    )


def register_file_blobs(base_blob_name: str) -> ImportReport:
    """
    Register uploaded blobs with the DESTINY Repository.

    Uses functionality from refresh_requester
    which handles: SAS token generation, ImportRecord creation, one ImportBatch
    per blob, and finalisation in a single call.

    The function will look for blobs in blob storage matching the base name and
    register them with the DESTINY Repository.

    Args:
        base_blob_name (str): The base blob name used to identify
            blobs to be registered.

    Returns:
        ImportReport: Information on the status of the import process.

    """
    settings = get_settings()
    logger.info(f"Registering blobs with base name {base_blob_name}")

    try:
        result = upload_blob_storage_contents_to_repository(
            settings=settings,
            blob_to_upload=base_blob_name,
            blob_content_source=ImportSourceType.OPEN_ALEX,
        )
    except DestinyRepositoryImportError as import_error:
        logger.error(f"Error during import: {import_error}")
        raise

    report = ImportReport.model_validate(result)
    logger.info(
        f"Registered ImportRecord {report.import_record.id} with {len(report.import_batch_ids)} batches."
    )
    return report
