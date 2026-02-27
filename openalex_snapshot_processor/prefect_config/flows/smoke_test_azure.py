"""
Define smoke tests that incorporate Azure functionality.

Currently a version of the full snapshot ingest in miniature.
Really this targets Azure interactions, but serves as a full end-to-end test of the flow.

Individual file processing is tested in `smoke_test_local.py`.
"""

from pathlib import Path

from loguru import logger
from prefect import flow, task

from openalex_snapshot_processor.config import get_settings
from openalex_snapshot_processor.enumeration import (
    batch_files_by_record_count,
    enumerate_work_files,
)
from openalex_snapshot_processor.file_processor import _derive_base_blob_name
from openalex_snapshot_processor.registration import (
    RegistrationSummary,
    register_all_blobs_in_serial,
)
from prefect_config.flows.openalex_snapshot_flow import (
    flatten_results,
    process_file_batch_task,
    report,
)
from refresh_requester.blob_storage import DestinyBlobStorageClient

MAXIMUM_BATCH_SIZE = 500_000


@task(retries=3, retry_delay_seconds=60)
def enumerate_files(n_files: int) -> list[tuple[Path, int]]:
    """
    Enumerate and batch the OpenAlex snapshot works files to be processed.

    Batches files by record count to avoid inefficiently processing
    many small files.

    Args:
        n_files (int): The number of files to select for processing in the smoke test.

    Returns:
        list[tuple[Path, int]]: List of file paths and their record counts to be processed.

    """
    settings = get_settings()
    return enumerate_work_files(settings.SNAPSHOT_ROOT)[:n_files]


@task
def filter_already_uploaded(
    file_paths_with_counts: list[tuple[Path, int]],
) -> list[Path]:
    """
    Filter out files that have already been uploaded to blob storage.

    This is important for the smoke test to avoid re-uploading files and
    hitting duplicate upload errors.

    Args:
        file_paths_with_counts (list[tuple[Path, int]]): List of file paths and their record counts to filter.

    Returns:
        list[Path]: List of file paths that have not yet been uploaded.

    """
    blob_client = DestinyBlobStorageClient()
    existing_blobs = set(blob_client.list_all_blobs("openalex_snapshot_works_"))

    unprocessed: list[Path] = []
    skipped: list[Path] = []
    for file_path, _ in file_paths_with_counts:
        base_blob_name = _derive_base_blob_name(file_path)
        if any(blob.startswith(base_blob_name) for blob in existing_blobs):
            skipped.append(file_path)
        else:
            unprocessed.append(file_path)

    if skipped:
        logger.info(
            f"{len(skipped)} files have already been processed and uploaded and will be skipped."
        )
        logger.debug(f"Skipped files: {skipped}")
    return unprocessed


@task
def batch_files(file_paths_with_counts: list[tuple[Path, int]]) -> list[list[Path]]:
    """
    Batch files by record count.

    Always keeps contiguous files. Single files that exceed max batch size
    are considered to be their own batch.

    Args:
        file_paths_with_counts (list[tuple[Path, int]]): List of file paths and their record counts to batch.

    Returns:
        list[list[Path]]: A single batch containing all the file paths.

    """
    return batch_files_by_record_count(file_paths_with_counts, MAXIMUM_BATCH_SIZE)


@task(retries=3, retry_delay_seconds=60)
def serial_register_all_blobs(processed_files: list[dict]) -> RegistrationSummary:
    """
    Register uploaded blobs with the DESTINY repository.

    Args:
        processed_files (list[dict]): List of processed file metadata dicts.

    Returns:
        RegistrationSummary: Summary of registration results.

    """
    progress_file_directory = Path(__file__).parent.parent / "logs"
    progress_file_directory.mkdir(exist_ok=True, parents=True)
    progress_file = (
        progress_file_directory / "smoke_test_azure_registration_progress.json"
    )
    return register_all_blobs_in_serial(processed_files, progress_file)


@flow(name="smoke-test-azure", log_prints=True)
def smoke_test_azure() -> None:
    """Run end to end Azure smoke test for a single file."""
    n_files_to_process = 3
    file_paths_with_counts = enumerate_files(n_files_to_process)
    unprocessed_files = filter_already_uploaded(file_paths_with_counts)
    batched_files = batch_files(unprocessed_files)
    processed_batches = process_file_batch_task.map(batched_files)
    all_processed = flatten_results(processed_batches)
    registration_summary = serial_register_all_blobs(all_processed)
    report(all_processed, registration_summary)


if __name__ == "__main__":
    smoke_test_azure()
