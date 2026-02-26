"""
Define smoke tests that incorporate Azure functionality.

Currently a version of the full snapshot ingest in miniature.
Really this targets Azure interactions, but serves as a full end-to-end test of the flow.

Individual file processing is tested in `smoke_test_local.py`.
"""

from pathlib import Path

from prefect import flow, task

from openalex_snapshot_processor.config import get_settings
from openalex_snapshot_processor.enumeration import (
    batch_files_by_record_count,
    enumerate_work_files,
)
from openalex_snapshot_processor.registration import (
    RegistrationSummary,
    register_all_blobs_in_serial,
)
from prefect_config.flows.openalex_snapshot_flow import (
    flatten_results,
    process_file_batch_task,
    report,
)

MAXIMUM_BATCH_SIZE = 100_000


@task(retries=3, retry_delay_seconds=60)
def enumerate_files(n_files: int) -> list[list[Path]]:
    """
    Enumerate and batch the OpenAlex snapshot works files to be processed.

    Batches files by record count to avoid inefficiently processing
    many small files.

    Args:
        n_files (int): The number of files to select for processing in the smoke test.

    Returns:
        list[list[Path]]: List of file paths and their record counts to be processed.

    """
    settings = get_settings()
    file_paths_with_counts = enumerate_work_files(settings.SNAPSHOT_ROOT)[:n_files]
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
    batched_files = enumerate_files(n_files_to_process)
    processed_batches = process_file_batch_task.map(batched_files)
    all_processed = flatten_results(processed_batches)
    registration_summary = serial_register_all_blobs(all_processed)
    report(all_processed, registration_summary)


if __name__ == "__main__":
    smoke_test_azure()
