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


@task(retries=3, retry_delay_seconds=60)
@forward_logs
def filter_already_uploaded(
    file_paths_with_counts: list[FilePathCount],
) -> list[FilePathCount]:
    """
    Filter out files already uploaded to blob storage.

    Avoids workers spending time reprocessing files where these
    already exist.

    Args:
        file_paths_with_counts (list[FilePathCount]): List of
            file paths and their record counts to filter.

    Returns:
        list[FilePathCount]: List of file paths that have not yet been uploaded.

    """
    blob_client = DestinyBlobStorageClient()
    existing_blobs = set(blob_client.list_all_blobs("openalex_snapshot_works_"))
    unprocessed: list[FilePathCount] = []
    skipped: list[FilePathCount] = []
    for file_path_count in file_paths_with_counts:
        base_blob_name = _derive_base_blob_name(file_path_count.file_path)
        if any(blob.startswith(base_blob_name) for blob in existing_blobs):
            skipped.append(file_path_count)
        else:
            unprocessed.append(file_path_count)

    if skipped:
        logger.info(
            f"{len(skipped)} files have already been processed and uploaded and will be skipped."
        )
        logger.debug(f"Skipped files: {skipped}")
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
    processed_files: list[dict],
) -> RegistrationSummary:
    """
    Register all processed files in blob storage against the DESTINY repository.

    This needs to be performed in serial to not overwhelm the
    DESTINY repository ingest queue.

    Polls each file's import batches to completion before adding
    to the queue.

    Args:
        processed_files (list[dict]): List of processed file metadata dicts.

    Returns:
        RegistrationSummary: The registration summary object.

    """
    progress_file_directory = Path(__file__).parent.parent / "logs"
    progress_file_directory.mkdir(exist_ok=True, parents=True)
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

    to_register = []
    for base in sorted(base_names):
        if base in completed or base in set(known_processed_base_names):
            continue
        pairs = blob_client.get_all_blob_url_pairs(base)
        if not pairs:
            continue
        blob_names = [pair["blob_name"] for pair in pairs]
        total_records = 0
        for pair in pairs:
            try:
                total_records += _count_lines_from_sas_url(pair["sas_url"])
            except Exception as e:  # noqa: BLE001
                logger.error(
                    f"Error occurred while counting lines in {pair['sas_url']}: {e}"
                )
                total_records = 0
                break

        processed_dict = {
            "base_blob_name": base,
            "blob_names": blob_names,
            "record_count": total_records,
            "file_path": None,
            "error_log": None,
        }
        to_register.append(processed_dict)
    return to_register


@flow(name="openalex-snapshot-ingest", log_prints=True)
def openalex_snapshot_ingest() -> None:
    """Orchestrate the full snapshot ingest flow: enumeration, processing, registration and reporting."""
    configure_logger()
    optional_file_limit = 10
    file_paths_with_counts = enumerate_files(optional_file_limit)
    unprocessed_files = filter_already_uploaded(file_paths_with_counts)
    batched_files = batch_files(unprocessed_files)
    logger.info(
        f"Processing {len(unprocessed_files)} unprocessed files in {len(batched_files)} batches."
    )
    processed_batches = process_file_batch_task.map(batched_files)
    all_processed = flatten_results(processed_batches)
    logger.info(
        f"Completed processing of {len(all_processed)} files. Proceeding to registration."
    )
    progress_file_directory = Path(__file__).parent.parent / "logs"
    progress_file = progress_file_directory / "registration_progress.json"
    known_base_names = [
        pair.get("base_blob_name")
        for pair in all_processed
        if pair.get("base_blob_name")
    ]
    unregistered_files = discover_uploaded_unregistered_files(
        known_base_names, progress_file
    )

    final_processed_file_set = all_processed + unregistered_files
    processed_blob_name = (
        f"task_logs/processed_files_"
        f"{datetime.now(ZoneInfo('UTC')).strftime('%Y-%m-%dT%H-%M-%SZ')}.json"
    )
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
    registration_summary = serial_register_all_processed_files(final_processed_file_set)
    report(final_processed_file_set, registration_summary)


if __name__ == "__main__":
    openalex_snapshot_ingest()
