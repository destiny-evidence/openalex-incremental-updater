"""
Attempt to locally process a single file and avoid Azure interactions entirely.

Grabs a single .gz file from the snapshot, streams and transforms it,
writes resulting JSONL lines to a local file, printing the path.

This is intended as a smoke test for the core processing logic, without
any other integrations.
"""

import asyncio
from pathlib import Path

from loguru import logger
from prefect import flow, task
from prefect.artifacts import create_markdown_artifact

from openalex_snapshot_processor.config import get_settings
from openalex_snapshot_processor.enumeration import enumerate_work_files
from openalex_snapshot_processor.file_processor import _log_errors, transform_file


@task
def select_files(n_files: int = 1) -> list[str]:
    """
    Select n files from the snapshot for processing.

    Currently uses the first n files found.

    Returns:
        list[str]: The local file paths of the first n .gz files in the snapshot.

    """
    settings = get_settings()
    snapshot_root = settings.SNAPSHOT_ROOT
    file_path_and_counts = enumerate_work_files(snapshot_root)
    if not file_path_and_counts:
        error_message = f"No files found in the snapshot directory {snapshot_root}."
        raise ValueError(error_message)
    return [
        str(file_path_and_count[0])
        for file_path_and_count in file_path_and_counts[:n_files]
    ]


@task
def transform_and_write(file_path: str) -> dict:
    """
    Transform the selected file and write the output to a local JSONL file.

    Args:
        file_path (str): The local file path of the .gz file to process.

    Returns:
        dict: A summary of the processing results, including paths, record count, and any errors.

    """
    lines, errors = asyncio.run(transform_file(file_path))
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True, parents=True)
    output_path = output_dir / f"{Path(file_path).stem}_smoke_test_output_local.jsonl"
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)
    logger.info(f"Writing transformed lines to local file: {output_path}")

    output_content = b"".join(lines)
    output_path.write_bytes(output_content)
    limited_output_content = output_content.decode("utf-8").splitlines()[:100]
    markdown_output_content = "```json\n" + "\n".join(limited_output_content) + "\n```"

    artifact_key_name = (
        "-".join(file_path.rsplit("/", 2)[1:]).replace("_", "-").replace(".gz", "")
    )
    artifact_key_name_cleaned = artifact_key_name.replace("=", "-")
    create_markdown_artifact(
        markdown=markdown_output_content,
        key=f"transformed-output-{artifact_key_name_cleaned}",
        description="The first 100 transformed JSONL lines from the processed file.",
    )
    error_log = _log_errors(Path(file_path), errors, log_dir) if errors else None

    return {
        "file_path": file_path,
        "output_path": str(output_path),
        "size_mb": round(output_path.stat().st_size / (1024 * 1024), 2),
        "record_count": len(lines),
        "errors": errors,
        "error_log": str(error_log) if error_log else None,
    }


@task
def report(processed_files: list[dict]) -> None:
    """
    Log a summary of the smoke test results.

    Args:
        processed_files (list[dict]): The list of result dictionaries from the transform_and_write task.
        Containing file paths, record count, and any errors.

    """
    logger.info(
        "Local-only smoke test complete\n" f"Processed {len(processed_files)} files."
    )
    for result in processed_files:
        logger.info(
            f"Source: {result['file_path']}\n"
            f"Output: {result['output_path']} ({result['size_mb']} MB)\n"
            f"Records: {result['record_count']}\n"
            f"Errors: {result['errors']}\n"
            f"Error log: {result['error_log']}"
        )
    error_log_content = "\n".join(
        f"{result['file_path']}: {result['errors']}"
        for result in processed_files
        if result.get("errors")
    )
    error_log_content = error_log_content or "No errors found."
    markdown_error_log_content = "```json\n" + error_log_content + "\n```"
    create_markdown_artifact(
        markdown=markdown_error_log_content,
        key="error-log",
        description="The error log for the processed files.",
    )


@flow(name="smoke-test-local", log_prints=True)
def smoke_test_local() -> None:
    """
    Orchestrate the local-only smoke test flow with Prefect.

    Select a file, transform and write it, and report results.
    """
    n_test_files = 3
    file_paths = select_files(n_test_files)
    locally_processed_files = transform_and_write.map(file_paths)
    report(locally_processed_files)


if __name__ == "__main__":
    smoke_test_local()
