"""Register uploaded blobs with the DESTINY Repository."""

import time
from pathlib import Path
from uuid import UUID

from destiny_sdk.imports import ImportBatchStatus, ImportBatchSummary
from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from requests import HTTPError

from openalex_snapshot_processor.config import get_settings
from refresh_requester.blob_storage import DestinyBlobStorageClient, blob_upload
from refresh_requester.repository import (
    DestinyRepositoryContentUploader,
    DestinyRepositoryImportError,
    ImportSourceType,
)

MAXIMUM_POLL_LIMIT_SECONDS = (
    21600  # 6 hour maximum poll limit for a single set of batches
)


class InProgressRecord(BaseModel):
    """Tracks in-flight registration for reconciliation in cause of pause/failure/cancellation."""

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
    retried_count: int = Field(
        ...,
        description=(
            "Number of files that were initially marked as failed but later completed upon retry."
        ),
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

    completed: dict[str, UUID] = Field(
        default_factory=dict,
        description=(
            "Base blob names that have been successfully registered, with corresponding import record ID."
        ),
    )
    in_progress: dict[str, InProgressRecord] = Field(
        default_factory=dict,
        description=(
            "A mapping of base blob names to their in-progress registration details."
        ),
    )
    failed: list[str] = Field(
        default_factory=list,
        description=("A list of base blob names that failed registration."),
    )
    retried_completed: dict[str, UUID] = Field(
        default_factory=dict,
        description=(
            "Base blob names and import record IDs that previously failed but later completed upon retry."
        ),
    )


def _has_exit_status(
    summary: ImportBatchSummary, status: ImportBatchStatus, import_batch_id: UUID
) -> bool:
    """
    Check the status of an import batch and raise an error if it has failed.

    Args:
        summary (ImportBatchSummary): The summary object for the import batch being checked.
        status (ImportBatchStatus): The current status of the import batch.
        import_batch_id (UUID): The ID of the import batch being checked.

    Returns:
        bool: True if the batch has reached a terminal state, False otherwise.

    Raises:
        RepositoryRegistrationError: If the batch has failed or partially failed.

    """
    if status == ImportBatchStatus.COMPLETED:
        success_message = f"Batch {import_batch_id} completed."
        logger.info(success_message)
        return True

    if status in {ImportBatchStatus.FAILED, ImportBatchStatus.PARTIALLY_FAILED}:
        details = summary.failure_details or []
        error_message = (
            f"Batch {import_batch_id} reached terminal state {status}. "
            f"Failure details: {details}"
        )
        logger.error(error_message)
        raise RepositoryRegistrationError(error_message)

    return False


def poll_registration_status(
    uploader: DestinyRepositoryContentUploader,
    import_record_id: UUID,
    import_batch_id: UUID,
    poll_interval: int,
    max_poll_limit_seconds: int = MAXIMUM_POLL_LIMIT_SECONDS,
) -> None:
    """
    Poll a single import batch until it reaches a terminal state.

    Uses ImportBatchSummary.import_batch_status (typed enum) so terminal
    failure states are detected immediately rather than exhausting retries.

    Args:
        uploader (DestinyRepositoryContentUploader): The uploader instance to use for polling.
        import_record_id (UUID): The ID of the import record to which the batch belongs.
        import_batch_id (UUID): The ID of the import batch to poll.
        poll_interval (int): The number of seconds to wait between polling attempts.
        max_poll_limit_seconds (int): The maximum allowable time spent polling, used to avoid polling endlessly.
            Defaults to MAXIMUM_POLL_LIMIT_SECONDS.

    Raises:
        RepositoryRegistrationError: If the batch fails or partially fails.

    """
    if poll_interval <= 0:
        poll_interval = 1
    maximum_poll_limit_number = max_poll_limit_seconds // poll_interval
    times_polled = 0

    summary = uploader.get_import_batch_summary(import_record_id, import_batch_id)
    status = summary.import_batch_status

    stop_polling = _has_exit_status(summary, status, import_batch_id)

    remain_polling = (not stop_polling) and (times_polled <= maximum_poll_limit_number)
    while remain_polling:
        summary = uploader.get_import_batch_summary(import_record_id, import_batch_id)
        times_polled += 1

        status = summary.import_batch_status

        stop_polling = _has_exit_status(summary, status, import_batch_id)
        remain_polling = (not stop_polling) and (
            times_polled <= maximum_poll_limit_number
        )

        if stop_polling:
            break
        if not remain_polling:
            warning_message = (
                f"Batch {import_batch_id} has not reached a terminal state after polling "
                f"{times_polled} times over {times_polled * poll_interval} seconds. "
                f"Last known status: {status}. Stopping polling to avoid infinite loop."
            )
            logger.warning(warning_message)
            raise RepositoryRegistrationError(warning_message)
        logger.info(
            f"Batch {import_batch_id} status={status} " f"Waiting {poll_interval}s..."
        )

        time.sleep(poll_interval)


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
    try:
        if progress_file.exists():
            content = progress_file.read_text(encoding="utf-8")
            progress_blob_name = "task_logs/registration_progress.json"
            blob_upload(content, progress_blob_name)
            logger.info(
                f"Uploaded registration progress file to blob storage: {progress_blob_name}"
            )
        else:
            logger.warning(
                f"Registration progress file not found at expected location: {progress_file}"
            )
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"Failed to upload registration progress file to blob storage: {e}"
        )


def _register_single_file(
    uploader: DestinyRepositoryContentUploader,
    blob_storage_client: DestinyBlobStorageClient,
    base_blob_name: str,
    poll_interval: int,
    progress: RegistrationProgress,
    progress_file: Path,
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
        progress (RegistrationProgress): Current registration progress state.
        progress_file (Path): Path to the JSON file where progress should be saved.

    Returns:
        RegistrationReport: Summary with import record ID and import batch IDs.

    """
    try:
        uploader.refresh_token()
    except DestinyRepositoryImportError:
        logger.exception("Failed to refresh token")
        raise

    in_progress = progress.in_progress.get(base_blob_name)
    import_batch_ids: list[UUID] = []

    if in_progress:
        logger.info(
            f"Resuming in-progress registration for {base_blob_name}"
            f" (import record={in_progress.import_record_id})"
        )
        import_record_id = in_progress.import_record_id
        import_batch_ids = in_progress.import_batch_ids
    else:
        blob_url_pairs = blob_storage_client.get_all_blob_url_pairs(base_blob_name)
        if len(blob_url_pairs) == 0:
            logger.warning(f"No blobs found to register for {base_blob_name}")
        logger.info(
            f"Found {len(blob_url_pairs)} blobs to register for {base_blob_name}"
        )

        try:
            import_record = uploader.register_new_import(
                source_type=ImportSourceType.BULK_IMPORTER
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

        try:
            for pair in blob_url_pairs:
                batch = uploader.register_import_batch_for_single_blob(
                    pair.get("blob_name", ""), pair.get("sas_url", ""), import_record
                )
                import_batch_ids.append(batch.id)
        except HTTPError as batch_registration_error:
            error_message = f"Failed to register import batch for {base_blob_name}: {batch_registration_error}"
            logger.exception(error_message)
            raise RepositoryRegistrationError(
                error_message
            ) from batch_registration_error

        try:
            uploader.finalise_import_record(import_record.id)
        except HTTPError as finalise_error:
            error_message = (
                f"Failed to finalise ImportRecord {import_record.id}: {finalise_error}"
            )
            logger.exception(error_message)
            raise RepositoryRegistrationError(error_message) from finalise_error
        logger.info(f"Finalised ImportRecord {import_record.id}.")

        import_record_id = import_record.id

        progress.in_progress[base_blob_name] = InProgressRecord(
            import_record_id=import_record_id,
            import_batch_ids=import_batch_ids,
        )
        _save_progress(progress_file, progress)
        logger.info(f"ImportRecord {import_record_id} registered for {base_blob_name}.")
        logger.info(f"Polling {len(import_batch_ids)} batches...")

    try:
        for batch_id in import_batch_ids:
            poll_registration_status(
                uploader, import_record_id, batch_id, poll_interval
            )
    except RepositoryRegistrationError as polling_error:
        progress.in_progress.pop(base_blob_name, None)
        progress.failed.append(base_blob_name)
        _save_progress(progress_file, progress)
        error_message = (
            f"Error while polling import batches for {base_blob_name}: {polling_error}"
        )
        logger.exception(error_message)
        raise RepositoryRegistrationError(error_message) from polling_error
    except HTTPError as polling_http_error:
        error_message = (
            f"HTTP error while polling import batches for {base_blob_name}: {polling_http_error}"
            " - this may be transient. Waiting for next retry..."
        )
        logger.error(error_message)
        raise

    return RegistrationReport(
        import_record_id=import_record_id,
        import_batch_ids=import_batch_ids,
        batch_count=len(import_batch_ids),
    )


def _reconcile_in_progress(
    progress: RegistrationProgress,
    uploader: DestinyRepositoryContentUploader,
    progress_file: Path,
) -> None:
    """
    Check ingestion status of in-progress batches after a restart.

    Base blob names that moved to a terminal state (completed/failed)
    during down time are moved to an appropriate list based on their current status.

    Args:
        progress (RegistrationProgress): Current registration progress state.
        uploader (DestinyRepositoryContentUploader): Destiny Repository uploader instance.
        progress_file (Path): Path to the progress file.

    """
    if not progress.in_progress:
        return

    logger.info(
        f"Checking status of {len(progress.in_progress)} in-progress registrations..."
    )

    resolved = []
    for base_blob_name, record in progress.in_progress.items():
        all_completed = True
        any_failed = False

        for batch_id in record.import_batch_ids:
            try:
                summary = uploader.get_import_batch_summary(
                    record.import_record_id, batch_id
                )
                status = summary.import_batch_status

                if status in {
                    ImportBatchStatus.FAILED,
                    ImportBatchStatus.PARTIALLY_FAILED,
                }:
                    any_failed = True
                    all_completed = False
                    break
                if status != ImportBatchStatus.COMPLETED:
                    all_completed = False
            except HTTPError as http_error:
                logger.warning(
                    f"HTTP error while checking batch {batch_id} for {base_blob_name}: {http_error}"
                    " - this may be transient. Will check again on next reconciliation."
                )
                all_completed = False
                break
        if any_failed:
            warning_message = f"Registration for {base_blob_name} failed during downtime. Marking as failed."
            logger.warning(warning_message)
            progress.failed.append(base_blob_name)
            resolved.append(base_blob_name)
        elif all_completed:
            success_message = f"Registration for {base_blob_name} completed during downtime. Marking as completed."
            logger.info(success_message)
            progress.completed[base_blob_name] = record.import_record_id
            resolved.append(base_blob_name)

    for base_blob_name in resolved:
        progress.in_progress.pop(base_blob_name)

    if resolved:
        logger.info(f"Reconciled {len(resolved)} in-progress registrations: {resolved}")
        _save_progress(progress_file, progress)


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

    logger.info("Checking status of any in-progress registrations from previous runs.")
    _reconcile_in_progress(progress, uploader, progress_file)

    total_files_to_register = len(processed_files)
    skipped_files = 0
    total_batches_registered = 0
    results = []

    for n, processed_file in enumerate(processed_files, start=1):
        completed = set(progress.completed.keys())

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
        try:
            result = _register_single_file(
                uploader=uploader,
                blob_storage_client=blob_storage_client,
                base_blob_name=base_blob_name,
                poll_interval=settings.POLL_INTERVAL_SECONDS,
                progress=progress,
                progress_file=progress_file,
            )
        except RepositoryRegistrationError as registration_error:
            logger.error(
                f"Registration failed for {base_blob_name}: {registration_error}"
            )
            continue
        total_batches_registered += result.batch_count
        results.append(result)

        progress.in_progress.pop(base_blob_name, None)
        if base_blob_name in progress.failed:
            progress.failed.remove(base_blob_name)
            progress.retried_completed[base_blob_name] = result.import_record_id
        progress.completed[base_blob_name] = result.import_record_id
        _save_progress(progress_file, progress)

        progress_message = (
            f"{n}/{total_files_to_register} registered\n"
            f"({skipped_files} skipped\n"
            f"{len(progress.retried_completed)} retried and completed)"
        )

        logger.info(progress_message)

    completed_count = len(progress.completed)
    retried_completed_count = len(progress.retried_completed)
    logger.success(
        f"Registration complete: {completed_count}/{total_files_to_register} files registered\n"
        f"{skipped_files} skipped\n"
        f"{retried_completed_count} retried and completed\n"
        f"{total_batches_registered} total batches."
    )
    return RegistrationSummary(
        total_files=total_files_to_register,
        completed_count=completed_count,
        skipped_count=skipped_files,
        retried_count=retried_completed_count,
        total_batches_registered=total_batches_registered,
        results=results,
    )
