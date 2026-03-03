"""
Prefect flow for the full run of the OpenAlex snapshot processor.

This flow orchestrates the end-to-end processing of
OpenAlex snapshot works files, including enumeration (counting of files),
processing (conversion to DESTINY-Reference-like JSONL), upload
to blob storage and registration of uploaded blobs in the DESTINY repository.

This flow has no schedule and should be triggered manually.
It is not envisaged that we will want to run this regularly.
"""

from pathlib import Path

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
    register_all_blobs_in_serial,
)
from refresh_requester.blob_storage import DestinyBlobStorageClient

MAXIMUM_BATCH_SIZE = 500_000


@task(retries=3, retry_delay_seconds=60)
def enumerate_files() -> list[FilePathCount]:
    """
    Enumerate and batch the OpenAlex snapshot works files to be processed.

    Batches files by record count to avoid inefficiently processing
    many small files.

    Returns:
        list[FilePathCount]: List of file paths and their record counts to be processed.

    """
    settings = get_settings()
    return enumerate_work_files(settings.SNAPSHOT_ROOT)


@task(retries=3, retry_delay_seconds=60)
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
def process_file_batch_task(batch_file_paths: list[BatchFilePaths]) -> list[dict]:
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
    file_path_list = [
        file_path for batch in batch_file_paths for file_path in batch.batch
    ]
    return process_file_batch(file_path_list, log_directory)


@task
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
    total_batches = sum(
        record.get("import_batch_count", 0) for record in processed_files
    )
    files_with_errors = [
        record["file_path"] for record in processed_files if record.get("error_log")
    ]

    error_log_content = "\n".join(
        f"{record['file_path']}: {record.get('errors')}"
        for record in processed_files
        if record.get("errors")
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


@flow(name="openalex-snapshot-ingest", log_prints=True)
def openalex_snapshot_ingest() -> None:
    """Orchestrate the full snapshot ingest flow: enumeration, processing, registration and reporting."""
    file_paths_with_counts = enumerate_files()
    unprocessed_files = filter_already_uploaded(file_paths_with_counts)
    batched_files = batch_files(unprocessed_files)
    processed_batches = process_file_batch_task.map(batched_files)
    all_processed = flatten_results(processed_batches)
    registration_summary = serial_register_all_processed_files(all_processed)
    report(all_processed, registration_summary)


if __name__ == "__main__":
    openalex_snapshot_ingest()
