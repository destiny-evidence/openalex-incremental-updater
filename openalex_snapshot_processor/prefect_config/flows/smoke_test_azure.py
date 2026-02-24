"""
Define smoke tests that incorporate Azure functionality.

Currently a version of the full snapshot ingest in miniature.
Really this targets Azure interactions, but serves as a full end-to-end test of the flow.

Individual file processing is tested in `smoke_test_local.py`.
"""

from pathlib import Path

from prefect import flow, task

from openalex_snapshot_processor.registration import register_all_blobs_in_serial
from prefect_config.flows.openalex_snapshot_flow import (
    enumerate_files,
    flatten_results,
    process_file_batch_task,
    report,
    serial_register_all_processed_files,
)
from prefect_config.flows.smoke_test_local import select_files


@task(retries=3, retry_delay_seconds=60)
def select_mini_batch(n_files: int) -> list[Path]:
    """
    Select a small number of files to process in the smoke test.

    Args:
        n_files (int): The number of files to select for processing.

    Returns:
        list[Path]: A list of file paths to be processed in the smoke test.

    """
    file_path_strings = select_files(n_files)
    file_paths = [Path(file_path_string) for file_path_string in file_path_strings]
    all_batched_files = enumerate_files()
    return [
        file_path
        for batch in all_batched_files
        for file_path in batch
        if file_path in file_paths
    ]


@task(retries=3, retry_delay_seconds=60)
def register_blobs(processed_file: dict) -> dict:
    """
    Register uploaded blobs with the DESTINY repository.

    Args:
        processed_file (dict): Processed file metadata.

    Returns:
        dict: Summary of registration results.

    """
    progress_file_directory = Path(__file__).parent.parent / "logs"
    progress_file_directory.mkdir(exist_ok=True, parents=True)

    progress_file = (
        progress_file_directory / "smoke_test_azure_registration_progress.json"
    )
    summary = register_all_blobs_in_serial([processed_file], progress_file)

    return {
        "base_blob_name": processed_file["base_blob_name"],
        "blob_count": len(processed_file.get("blob_names") or []),
        "record_count": processed_file.get("record_count"),
        "error_log": processed_file.get("error_log"),
        "total_batches": summary.get("total_batches_registered"),
        "results": summary.get("results", {}),
    }


@flow(name="smoke-test-azure", log_prints=True)
def smoke_test_azure() -> None:
    """Run end to end Azure smoke test for a single file."""
    n_files_to_process = 1
    batched_files = select_mini_batch(n_files_to_process)
    processed_batches = process_file_batch_task.map(batched_files)
    all_processed = flatten_results(processed_batches)
    registration_summary = serial_register_all_processed_files(all_processed)
    report(registration_summary)


if __name__ == "__main__":
    smoke_test_azure()
