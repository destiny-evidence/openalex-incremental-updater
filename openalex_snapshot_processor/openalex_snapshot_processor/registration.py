"""Register uploaded blobs with the DESTINY Repository."""

from pathlib import Path
from uuid import UUID

from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from requests import HTTPError

from openalex_snapshot_processor.config import get_settings
from refresh_requester.blob_storage import DestinyBlobStorageClient
from refresh_requester.repository import (
    DestinyRepositoryContentUploader,
    DestinyRepositoryImportError,
    ImportSourceType,
)


class RepositoryRegistrationError(Exception):
    """Repository Registration Error."""


class ProgressLoadError(Exception):
    """Custom exception for errors encountered while loading registration progress."""


class RegistrationReport(BaseModel):
    """Report model for tracking the status of the import process."""

    import_record_id: UUID = Field(
        ...,
        description=(
            "The import record ID created in the DESTINY Repository for this import."
        ),
    )
    import_batch_ids: list[UUID] = Field(
        ...,
        description=(
            "A list of the IDs of the import batches created in the DESTINY Repository for this import process."
        ),
    )
    batch_count: int = Field(
        ...,
        description=(
            "The number of import batches created in the DESTINY Repository for this import process."
        ),
    )


class RegistrationSummary(BaseModel):
    """Summary model for the overall registration process."""

    total_files: int = Field(
        ...,
        description=("The total number of files that were processed for registration."),
    )
    completed_count: int = Field(
        ...,
        description=(
            "The number of files that were successfully registered with the DESTINY Repository."
        ),
    )
    skipped_count: int = Field(
        ...,
        description=("Number of files skipped as already marked as completed."),
    )
    total_batches_registered: int = Field(
        ...,
        description=(
            "Total number of import batches registered across all files (included already completed)."
        ),
    )
    results: list[RegistrationReport] = Field(
        ...,
        description=(
            "A list of RegistrationReport objects containing details about each file's registration outcome."
        ),
    )


class RegistrationProgress(BaseModel):
    """Model to track the progress of the registration process for a file's blobs."""

    completed: list[str] = []


def _load_progress(progress_file: Path) -> RegistrationProgress:
    """
    Load the registration progress from a JSON file.

    Return empty progress if the file does not exist or is invalid.

    Args:
        progress_file (Path): The path to the JSON file containing the registration progress.

    Returns:
        RegistrationProgress: The loaded registration progress.

    """
    if progress_file.exists():
        try:
            logger.info(f"Resuming from progress file {progress_file}")
            return RegistrationProgress.model_validate_json(progress_file.read_text())
        except ValidationError as json_parse_error:
            error_message = (
                f"Failed to parse progress file {progress_file}: {json_parse_error}"
            )
            logger.warning(
                f"Failed to parse JSON within progress file: {progress_file}"
            )
            raise ProgressLoadError(error_message) from json_parse_error
    return RegistrationProgress()


def _save_progress(progress_file: Path, progress: RegistrationProgress) -> None:
    """
    Write registration progress to file.

    Args:
        progress_file (Path): Path to the JSON file where progress should be saved.
        progress (RegistrationProgress): Current progress state.

    """
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    progress_file.write_text(progress.model_dump_json(indent=2))


def _register_single_file(
    uploader: DestinyRepositoryContentUploader,
    blob_storage_client: DestinyBlobStorageClient,
    base_blob_name: str,
    poll_interval: int,
    max_poll_attempts: int,
) -> RegistrationReport:
    """
    Register all blobs for a single file and poll until batches complete.

    This is designed to be run in serial to avoid overloading the
    DESTINY Repository ingest queue with import batches.

    It will look for blobs matching the base name, register them
    and poll the import batches until completion before returning.

    Progress is saved to file after each batch completes
    to allow resumption in case of failure.

    Args:
        uploader (DestinyRepositoryContentUploader): Destiny Repository uploader.
        blob_storage_client (DestinyBlobStorageClient): Azure Blob Storage client.
        base_blob_name (str): Prefix of the blob names to register.
        poll_interval (int): Seconds between polling attempts.
        max_poll_attempts (int): Maximum number of polling attempts before giving up.

    Returns:
        RegistrationReport: Summary with import record ID and import batch IDs.

    """
    try:
        uploader.refresh_token()
    except DestinyRepositoryImportError:
        logger.exception("Failed to refresh token")
        raise

    blob_url_pairs = blob_storage_client.get_all_blob_url_pairs(base_blob_name)
    if len(blob_url_pairs) == 0:
        logger.warning(f"No blobs found to register for {base_blob_name}")
    logger.info(f"Found {len(blob_url_pairs)} blobs to register for {base_blob_name}")

    try:
        import_record = uploader.register_new_import(
            source_type=ImportSourceType.OPEN_ALEX
        )
    except DestinyRepositoryImportError as new_import_registration_error:
        error_message = (
            f"Failed to register new import for {base_blob_name}"
            f": {new_import_registration_error}"
        )
        logger.exception(error_message)
        raise RepositoryRegistrationError(
            error_message
        ) from new_import_registration_error
    logger.info(f"Created ImportRecord {import_record.id} for {base_blob_name}")

    import_batch_ids: list[UUID] = []
    try:
        for pair in blob_url_pairs:
            batch = uploader.register_import_batch_for_single_blob(
                pair.get("blob_name", ""), pair.get("sas_url", ""), import_record
            )
            import_batch_ids.append(batch.id)
    except HTTPError as batch_registration_error:
        error_message = f"Failed to register import batch for {base_blob_name}: {batch_registration_error}"
        logger.exception(error_message)
        raise RepositoryRegistrationError(error_message) from batch_registration_error

    try:
        uploader.finalise_import_record(import_record.id)
    except HTTPError as finalise_error:
        error_message = (
            f"Failed to finalise ImportRecord {import_record.id}: {finalise_error}"
        )
        logger.exception(error_message)
        raise RepositoryRegistrationError(error_message) from finalise_error
    logger.info(f"Finalised ImportRecord {import_record.id}.")
    logger.info(f"Polling {len(import_batch_ids)} batches...")

    try:
        uploader.poll_import_batches_for_completion(
            import_record_id=import_record.id,
            import_batch_ids=import_batch_ids,
            retry_time_seconds=poll_interval,
            max_retries=max_poll_attempts,
        )
    except HTTPError as polling_error:
        error_message = (
            f"Error while polling import batches for {base_blob_name}: {polling_error}"
        )
        logger.exception(error_message)
        raise RepositoryRegistrationError(error_message) from polling_error

    return RegistrationReport(
        import_record_id=import_record.id,
        import_batch_ids=import_batch_ids,
        batch_count=len(import_batch_ids),
    )


def register_all_blobs_in_serial(
    processed_files: list[dict],
    progress_file: Path,
) -> RegistrationSummary:
    """
    Register all processed files with the DESTINY repository.

    This cannot be done in parallel and must avoid overloading the ingest
    queue.

    Polls each file import progress to completion before moving to the next.
    Updates progress to file after each file completion to the process
    can be resumed in case of pauses or failures.

    Args:
        processed_files (list[dict]): A list of processed file metadata dicts.
        progress_file (Path): Path to the progress file.

    Returns:
        RegistrationSummary: Summary of the entire registration process.

    """
    settings = get_settings()
    progress = _load_progress(progress_file)
    uploader = DestinyRepositoryContentUploader(settings=settings)
    blob_storage_client = DestinyBlobStorageClient()

    total_files_to_register = len(processed_files)
    skipped_files = 0
    total_batches_registered = 0
    results = []

    for n, processed_file in enumerate(processed_files, start=1):
        completed = set(progress.completed)

        base_blob_name = processed_file.get("base_blob_name", "")
        if base_blob_name in completed:
            logger.info(
                f"[{n}/{total_files_to_register}] Skipping {base_blob_name} - already registered."
            )
            skipped_files += 1
            continue

        logger.info(
            f"[{n}/{total_files_to_register}] Registering file {base_blob_name}"
        )
        result = _register_single_file(
            uploader=uploader,
            blob_storage_client=blob_storage_client,
            base_blob_name=base_blob_name,
            poll_interval=settings.POLL_INTERVAL_SECONDS,
            max_poll_attempts=settings.MAX_POLL_ATTEMPTS,
        )
        total_batches_registered += result.batch_count
        results.append(result)

        progress.completed.append(base_blob_name)
        _save_progress(progress_file, progress)

        progress_message = (
            f"{n}/{total_files_to_register} registered ({skipped_files} skipped)"
        )

        logger.info(progress_message)

    completed_count = len(progress.completed)
    logger.success(
        f"Registration complete: {completed_count}/{total_files_to_register} files registered"
        f"{skipped_files} skipped, {total_batches_registered} total batches."
    )
    return RegistrationSummary(
        total_files=total_files_to_register,
        completed_count=completed_count,
        skipped_count=skipped_files,
        total_batches_registered=total_batches_registered,
        results=results,
    )
