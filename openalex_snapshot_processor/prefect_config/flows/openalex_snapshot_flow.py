"""
Prefect flow for the full run of the OpenAlex snapshot processor.

This flow orchestrates the end-to-end processing of
OpenAlex snapshot works files, including enumeration (counting of files),
processing (conversion to DESTINY-Reference-like JSONL), upload
to blob storage and registration of uploaded blobs in the DESTINY repository.

This flow has no schedule and should be triggered manually.
It is not envisaged that we will want to run this regularly.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from loguru import logger
from prefect import flow, task
from prefect.artifacts import create_markdown_artifact

from openalex_snapshot_processor.config import get_settings
from openalex_snapshot_processor.enumeration import (
    BatchFilePaths,
    FilePathCount,
    batch_files_by_record_count,
    enumerate_work_files,
)
from openalex_snapshot_processor.file_processor import (
    _derive_base_blob_name,
    process_file_batch,
)
from openalex_snapshot_processor.registration import (
    RegistrationSummary,
    _load_progress,
    register_all_blobs_in_serial,
)
from prefect_config.flows.logging_config import configure_logger, forward_logs
from refresh_requester.blob_storage import DestinyBlobStorageClient, blob_upload

MAXIMUM_BATCH_SIZE = 500_000

settings = get_settings()


class ManifestMismatchError(Exception):
    """Custom exception to indicate a mismatch between manifest entries and blob storage contents."""


def _manifest_url_to_base_name(url: str) -> str:
    """
    Convert a manifest S3 URL to the base blob name.

    Args:
        url (str): The S3 URL from the manifest.

    Returns:
        str: The base blob name derived from the URL.

    """
    name = url.replace(
        "s3://openalex/data/works/updated_date=", "openalex_snapshot_works_"
    )
    return name.replace("/", "_").replace(".gz", "")


def _is_expected_number_of_blobs(
    record_count: int,
    batch_blob_size: int,
    existing_blobs: set[str],
    base_blob_name: str,
) -> dict:
    """
    Check if the number of blobs is as expected for a given record count and batch blob size.

    Args:
        record_count (int): The total number of records in the snapshot file.
        batch_blob_size (int): The number of records per blob batch.
        existing_blobs (set[str]): The set of existing blob names in blob storage.
        base_blob_name (str): The base blob name derived from the file path.

    Returns:
        dict: A dictionary containing the expected and actual number of blobs,
            and whether the actual number meets or exceeds the expected number.

    """
    expected_number_of_blobs = (record_count - 1) // batch_blob_size + 1

    matching_blobs = [
        blob for blob in existing_blobs if blob.startswith(base_blob_name)
    ]
    return {
        "expected": expected_number_of_blobs,
        "actual": len(matching_blobs),
        "is_expected": len(matching_blobs) >= expected_number_of_blobs,
    }


def _check_blob_storage_for_incomplete_snapshot_file_processing(
    file_paths_with_counts: list[FilePathCount],
    existing_blobs: set[str],
    manifest_base_blob_name_record_counts: dict[str, int],
    blob_batch_size: int,
) -> tuple[list[FilePathCount], list[FilePathCount]]:
    """
    Check blob storage for for complete sets of processed and uploaded snapshots.

    Both to avoid reprocessing and reuploading files where this has already been completed,
    but also to catch any partially processed files where some, but not all, of an expected
    set of blobs derived from a snapshot file are present in blob storage.

    For these cases, the entire snapshot file is reprocessed.

    Args:
        file_paths_with_counts (list[FilePathCount]):
            List of file paths and their record counts to check against blob storage.
        existing_blobs (set[str]): Set of existing blob names in blob storage.
        manifest_base_blob_name_record_counts (dict[str, int]):
            A mapping of base blob names to their record counts, derived from the manifest.
        blob_batch_size (int): The size of each blob batch.

    Returns:
        tuple[list[FilePathCount], list[FilePathCount]]:
            A tuple containing the list of unprocessed file paths and the list of skipped file paths.

    """
    unprocessed: list[FilePathCount] = []
    skipped: list[FilePathCount] = []
    for file_path_count in file_paths_with_counts:
        base_blob_name = _derive_base_blob_name(file_path_count.file_path)
        if any(blob.startswith(base_blob_name) for blob in existing_blobs):
            if base_blob_name not in manifest_base_blob_name_record_counts:
                error_message = (
                    f"Base blob name {base_blob_name} derived from local file path "
                    f"{file_path_count.file_path} and found in blob storage "
                    "was **not** found in manifest. "
                    " Check that the manifest file is correct and up to date. "
                )
                raise ManifestMismatchError(error_message)

            record_count = manifest_base_blob_name_record_counts[base_blob_name]

            is_expected_number_of_blobs = _is_expected_number_of_blobs(
                record_count, blob_batch_size, existing_blobs, base_blob_name
            )
            if is_expected_number_of_blobs["is_expected"]:
                skipped.append(file_path_count)
            else:
                info_message = (
                    f"File {file_path_count.file_path} has {is_expected_number_of_blobs['actual']} blobs "
                    f"processed and uploaded. Expected at least {is_expected_number_of_blobs['expected']} "
                    f"blobs from manifest metadata based on a batch size of {blob_batch_size} "
                    f"and record count of {record_count}."
                    "Reprocessing all data to ensure blob storage is complete and correct."
                )
                logger.info(info_message)
                unprocessed.append(file_path_count)
        else:
            unprocessed.append(file_path_count)

    return skipped, unprocessed


def _derive_base_blob_name_from_blob_storage(blob_name: str) -> str:
    """
    Derive the base blob name from the blob name as it appears in blob storage.

    This is necessary because the blob names in storage have additional suffixes
    compared to the base blob names derived from file paths, due to the upload
    and registration process.

    Args:
        blob_name (str): The name of the blob as it appears in blob storage.

    Returns:
        str: The derived base blob name.

    """
    return blob_name.rsplit("_part_", 1)[0]


def _count_lines_from_sas_url(
    sas_url: str,
    timeout_seconds: int = 30,
) -> int:
    """
    Count the number of lines in a blob given its SAS URL.

    Args:
        sas_url (str): The SAS URL of the blob to count lines in.
        timeout_seconds (int): The timeout for the operation in seconds.

    Returns:
        int: The number of lines in the blob.

    """
    session = requests.Session()

    with session.get(sas_url, stream=True, timeout=timeout_seconds) as response:
        response.raise_for_status()
        return sum(1 for _ in response.iter_lines())


@task(retries=3, retry_delay_seconds=60)
@forward_logs
def enumerate_files(file_limit: int | None = None) -> list[FilePathCount]:
    """
    Enumerate and batch the OpenAlex snapshot works files to be processed.

    Batches files by record count to avoid inefficiently processing
    many small files.

    Args:
        file_limit (int | None): The number of files to select for processing in the smoke test.

    Returns:
        list[FilePathCount]: List of file paths and their record counts to be processed.

    """
    if file_limit is not None:
        return enumerate_work_files(settings.SNAPSHOT_ROOT)[:file_limit]
    return enumerate_work_files(settings.SNAPSHOT_ROOT)


def _get_manifest_record_counts() -> dict[str, int]:
    """
    Return the manifest entries as a dictionary mapping base blob names to record counts.

    Returns:
        dict[str, int]: The manifest entries, as a dictionary mapping base blob names to record counts.

    """
    with settings.MANIFEST_PATH.open("r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    manifest_entries = manifest.get("entries", [])

    return {
        _manifest_url_to_base_name(entry["url"]): entry.get("meta", {}).get(
            "record_count", 0
        )
        for entry in manifest_entries
    }


def _log_unprocessed_files_to_file(
    unprocessed_files: list[FilePathCount], canonical_now_time: str
) -> None:
    """
    Log the unprocessed files to a file in the logs directory.

    Args:
        unprocessed_files (list[FilePathCount]): The list of unprocessed files to log.
        canonical_now_time (str): The canonical time string to use in log file names.

    """
    log_directory = Path(__file__).parent.parent / "logs"
    log_directory.mkdir(exist_ok=True, parents=True)
    unprocessed_file_log = (
        log_directory / f"unprocessed_files_{canonical_now_time}.json"
    )
    with unprocessed_file_log.open("w", encoding="utf-8") as log_file:
        json.dump(
            [
                {
                    "file_path": str(file_path_count.file_path),
                    "record_count": file_path_count.record_count,
                }
                for file_path_count in unprocessed_files
            ],
            log_file,
        )


@task(retries=3, retry_delay_seconds=60)
@forward_logs
def filter_already_uploaded(
    file_paths_with_counts: list[FilePathCount],
    canonical_now_time: str,
) -> list[FilePathCount]:
    """
    Filter out files already uploaded to blob storage.

    Avoids workers spending time reprocessing files where these
    already exist.

    Args:
        file_paths_with_counts (list[FilePathCount]): List of
            file paths and their record counts to filter.
        canonical_now_time (str): The canonical time string to use in log file names.

    Returns:
        list[FilePathCount]: List of file paths that have not yet been uploaded.

    """
    blob_client = DestinyBlobStorageClient()
    existing_blobs = set(blob_client.list_all_blobs("openalex_snapshot_works_"))
    blob_batch_size = settings.BLOB_BATCH_SIZE

    manifest_base_blob_name_record_counts = _get_manifest_record_counts()

    skipped, unprocessed = _check_blob_storage_for_incomplete_snapshot_file_processing(
        file_paths_with_counts,
        existing_blobs,
        manifest_base_blob_name_record_counts,
        blob_batch_size,
    )

    if skipped:
        logger.info(
            f"{len(skipped)} files have already been processed and uploaded and will be skipped."
        )
        logger.debug(f"Skipped files: {skipped}")

    _log_unprocessed_files_to_file(unprocessed, canonical_now_time)
    return unprocessed


@task
@forward_logs
def batch_files(file_paths_with_counts: list[FilePathCount]) -> list[BatchFilePaths]:
    """
    Batch files by record count.

    Files are batched together until the total record count in the batch reaches
    MAXIMUM_BATCH_SIZE. If a single file has a record count that exceeds
    MAXIMUM_BATCH_SIZE, it is considered to be its own batch.

    Args:
        file_paths_with_counts (list[FilePathCount]): List of file paths and their record counts to batch.

    Returns:
        list[BatchFilePaths]: A list of BatchFilePaths objects.

    """
    return batch_files_by_record_count(file_paths_with_counts, MAXIMUM_BATCH_SIZE)


@task(
    retries=3,
    retry_delay_seconds=60,
)
@forward_logs
def process_file_batch_task(batch_file_paths: BatchFilePaths) -> list[dict]:
    """
    Process a batch of files in one worker.

    Converts and uploads files to blob storage.



    Args:
        batch_file_paths (list[BatchFilePaths]): List of BatchFilePaths objects to be processed.

    Returns:
        list[dict]: The metadata of the processed files, as a list of dictionaries.
            One per file processed.


    """
    log_directory = Path(__file__).parent.parent / "logs"
    file_path_list = list(batch_file_paths.batch)
    return process_file_batch(file_path_list, log_directory)


@task
@forward_logs
def flatten_results(batched_results: list[list[dict]]) -> list[dict]:
    """
    Flatten per-batch results into a single list for serial ingestion.

    Args:
        batched_results (list[list[dict]]): List of lists of processed file metadata dicts.
            One list per batch of files processed.

    Returns:
        list[dict]: A flattened list of processed file metadata dicts.

    """
    return [item for batch in batched_results for item in batch]


@task(retries=1, retry_delay_seconds=300)
@forward_logs
def serial_register_all_processed_files(
    progress_file_directory: Path,
    processed_files: list[dict],
) -> RegistrationSummary:
    """
    Register all processed files in blob storage against the DESTINY repository.

    This needs to be performed in serial to not overwhelm the
    DESTINY repository ingest queue.

    Polls each file's import batches to completion before adding
    to the queue.

    Args:
        progress_file_directory (Path): The directory where the registration progress file is stored.
        processed_files (list[dict]): List of processed file metadata dicts.

    Returns:
        RegistrationSummary: The registration summary object.

    """
    progress_file = progress_file_directory / "registration_progress.json"
    return register_all_blobs_in_serial(processed_files, progress_file)


@task
@forward_logs
def report(
    processed_files: list[dict],
    registration_summary: RegistrationSummary,
    artifact_key: str = "snapshot-ingest",
) -> None:
    """
    Log a summary of the full snapshot ingest run.

    Args:
        processed_files (list[dict]): A list of processed file metadata dicts.
        registration_summary (RegistrationSummary): The registration summary object.

    """
    total_records = sum(record.get("record_count", 0) for record in processed_files)
    total_blobs = sum(len(record.get("blob_names") or []) for record in processed_files)
    total_batches = registration_summary.total_batches_registered
    files_with_errors = [
        record["file_path"] for record in processed_files if record.get("error_log")
    ]

    error_log_content = "\n".join(
        f"{record['file_path']}: {record.get('errors')}"
        for record in processed_files
        if record.get("error_log")
    )
    if error_log_content:
        error_log_content_markdown = f"```json\n{error_log_content}\n```"
        create_markdown_artifact(
            markdown=error_log_content_markdown,
            key=f"{artifact_key}-error-log",
            description="Error log.",
        )
    logger.success(
        "Snapshot ingest complete!\n"
        f"{registration_summary.total_files} files processed\n"
        f"{total_records} records processed\n"
        f"{total_blobs} blobs uploaded\n"
        f"{total_batches} import batches generated"
    )
    if files_with_errors:
        logger.warning(
            f"{len(files_with_errors)} files with data quality errors.\n"
            f"{files_with_errors=}"
        )


@task
@forward_logs
def discover_uploaded_unregistered_files(
    known_processed_base_names: list[str],
    progress_file: Path,
    blob_prefix: str = "openalex_snapshot_works_",
) -> list[dict]:
    """
    Discover any files that have been uploaded to blob storage but not yet registered.

    This is to catch any files that may have been processed and uploaded,
    but where the flow failed before registration.

    Args:
        known_processed_base_names (list[str]): List of base blob names for files known
            to have been processed.
        progress_file (Path): Path to the registration progress file, which contains the
            list of already registered blobs.
        blob_prefix (str): The prefix of the blobs to check for.

    Returns:
        list[dict]: A list of metadata dicts for any files that have been uploaded but not registered.

    """
    blob_client = DestinyBlobStorageClient()
    progress = _load_progress(progress_file)
    completed = set(progress.completed.keys())

    existing_blobs = blob_client.list_all_blobs(blob_prefix)

    base_names = {
        _derive_base_blob_name_from_blob_storage(blob) for blob in existing_blobs
    }
    manifest_record_counts = _get_manifest_record_counts()
    to_register = []
    for base in sorted(base_names):
        if base in completed or base in set(known_processed_base_names):
            if base not in manifest_record_counts:
                error_message = (
                    f"Base blob name {base} found in blob storage but not in manifest record counts. "
                    "This base blob name will be skipped. Check that the manifest file is correct and up to date."
                )
                raise ManifestMismatchError(error_message)
            record_count = manifest_record_counts[base]
            is_expected_number_of_blobs = _is_expected_number_of_blobs(
                record_count, settings.BLOB_BATCH_SIZE, existing_blobs, base
            )
            if not is_expected_number_of_blobs["is_expected"]:
                error_message = (
                    f"Base blob name {base} found in blob storage and manifest "
                    " but does not have the expected number of blobs. "
                    f"Expected at least {is_expected_number_of_blobs['expected']} blobs "
                    f"based on manifest record count of {record_count} and batch size of "
                    f"{settings.BLOB_BATCH_SIZE}, found {is_expected_number_of_blobs['actual']} blobs."
                )
                logger.error(error_message)
                logger.error(f"Reprocess blob with base name {base}.")
                raise ManifestMismatchError(error_message)
            continue
        pairs = blob_client.get_all_blob_url_pairs(base)
        if not pairs:
            continue
        blob_names = [pair["blob_name"] for pair in pairs]
        sorted_pairs = sorted(pairs, key=lambda blob_pair: blob_pair["blob_name"])
        number_of_parts = len(sorted_pairs)
        try:
            last_part_count = _count_lines_from_sas_url(sorted_pairs[-1]["sas_url"])
            total_records = (
                number_of_parts - 1
            ) * settings.BLOB_BATCH_SIZE + last_part_count

        except Exception as total_record_reporting_error:  # noqa: BLE001
            error_message = "Error occurred while counting lines in last part"
            f" of {base}: {total_record_reporting_error}"
            logger.error(error_message)
            total_records = 0

        processed_dict = {
            "base_blob_name": base,
            "blob_names": blob_names,
            "record_count": total_records,
            "file_path": None,
            "error_log": None,
        }
        to_register.append(processed_dict)
    return to_register


@task
@forward_logs
def invalidate_stale_registration_entries(
    unprocessed_files: list[FilePathCount],
    progress_file: Path,
    canonical_now_time: str,
) -> None:
    """
    Remove registration progress entries for files being reprocessed.

    When a snapshot file is identified as needing reprocessing,
    any existing registration entries for that file's base blob name
    are then invalid and should be removed from the registration progress tracking.

    Args:
        unprocessed_files (list[FilePathCount]): List of FilePathCount objects for files that are being reprocessed.
        progress_file (Path): Path to the registration progress file, which contains the list
            of already registered blobs.
        canonical_now_time (str): The current timestamp in UTC.

    """
    if not unprocessed_files or not progress_file.exists():
        return

    progress = _load_progress(progress_file)
    base_names_to_reprocess = {
        _derive_base_blob_name(file_path_count.file_path)
        for file_path_count in unprocessed_files
    }
    invalidated_blobs = []
    for base_name in base_names_to_reprocess:
        removed = False

        if base_name in progress.completed:
            del progress.completed[base_name]
            removed = True
        if base_name in progress.in_progress:
            del progress.in_progress[base_name]
            removed = True
        if base_name in progress.failed:
            progress.failed.remove(base_name)
            removed = True
        if base_name in progress.retried_completed:
            del progress.retried_completed[base_name]
            removed = True
        if removed:
            invalidated_blobs.append(base_name)

    if invalidated_blobs:
        backup_path = progress_file.with_suffix(f".backup_{canonical_now_time}")
        shutil.copy2(progress_file, backup_path)
        logger.info(
            f"Backed up registration progress file to {backup_path} before invalidating entries for reprocessed files."
        )
        progress_file.write_text(progress.model_dump_json(), encoding="utf-8")
        logger.info(
            f"Invalidated registration progress entries for {len(invalidated_blobs)} blobs "
            f"due to reprocessing of their source files: {invalidated_blobs}"
        )


@flow(name="openalex-snapshot-ingest", log_prints=True)
def openalex_snapshot_ingest(*, dry_run: bool = False) -> None:
    """
    Orchestrate the full snapshot ingest flow.

    Covers enumeration, processing, registration and reporting.

    Args:
        dry_run (bool): If True, the flow will run without performing processing or registration.

    """
    canonical_now_time = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H-%M-%SZ")
    progress_file_directory = Path(__file__).parent.parent / "logs"
    progress_file_directory.mkdir(exist_ok=True, parents=True)

    progress_file = progress_file_directory / "registration_progress.json"
    configure_logger()
    optional_file_limit = None

    file_paths_with_counts = enumerate_files(optional_file_limit)
    unprocessed_files = filter_already_uploaded(
        file_paths_with_counts, canonical_now_time
    )
    invalidate_stale_registration_entries(
        unprocessed_files, progress_file, canonical_now_time
    )
    batched_files = batch_files(unprocessed_files)
    logger.info(
        f"Processing {len(unprocessed_files)} unprocessed files in {len(batched_files)} batches."
    )
    if dry_run and unprocessed_files:
        logger.info("Dry run enabled - skipping processing and registration.")
        logger.info(
            f"Enumerated {len(file_paths_with_counts)} files with record counts: {file_paths_with_counts}"
        )
        logger.info("Files that would be processed (not already uploaded): ")
        record_counter = 0

        for file_path, record_count in unprocessed_files:
            record_counter += record_count[-1]
            logger.info(f" - {file_path}: {record_count} records")
            logger.info(f"{len(unprocessed_files)} with {record_counter} records")
        return

    processed_batches = process_file_batch_task.map(batched_files)
    all_processed = flatten_results(processed_batches)
    logger.info(
        f"Completed processing of {len(all_processed)} files. Proceeding to registration."
    )

    known_base_names = [
        pair.get("base_blob_name")
        for pair in all_processed
        if pair.get("base_blob_name")
    ]
    unregistered_files = discover_uploaded_unregistered_files(
        known_base_names, progress_file
    )

    if dry_run:
        logger.info("Dry run enabled - skipping registration.")
        logger.info(
            "Files that would be registered (including already uploaded but unregistered files): "
        )
        for record in all_processed + unregistered_files:
            logger.info(
                f" - {record.get('base_blob_name')}: {record.get('blob_names')}"
            )
        return

    final_processed_file_set = all_processed + unregistered_files
    processed_blob_name = f"task_logs/processed_files_" f"{canonical_now_time}.json"
    try:
        blob_upload(
            json.dumps(final_processed_file_set, default=str), processed_blob_name
        )
        logger.info(
            f"Uploaded metadata of processed files to blob storage: {processed_blob_name}"
        )
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"Failed to upload metadata of processed files to blob storage: {e}"
        )
    registration_summary = serial_register_all_processed_files(
        progress_file_directory, final_processed_file_set
    )
    report(final_processed_file_set, registration_summary)


if __name__ == "__main__":
    openalex_snapshot_ingest()
