"""
Attempt to locally process a single file and avoid Azure interactions entirely.

Grabs a single .gz file from the snapshot, streams and transforms it,
writes resulting JSONL lines to a local file, printing the path.

This is intended as a smoke test for the core processing logic, without
any other integrations.
"""

import asyncio
from pathlib import Path

import pendulum
from airflow.decorators import dag, task
from loguru import logger

from openalex_snapshot_processor.config import get_settings
from openalex_snapshot_processor.enumeration import enumerate_work_files
from openalex_snapshot_processor.file_processor import _log_errors, transform_file


@dag(
    dag_id="local_smoke_test",
    schedule=None,
    start_date=pendulum.now("UTC"),
    catchup=False,
    tags=["openalex", "smoke_test", "local"],
    doc_md=__doc__,
)
def smoke_test_local() -> None:
    """
    Generate a local smoke test to ensure file processing works.

    Avoids any interaction with Azure/the DESTINY repository.
    """

    @task
    def select_file() -> str:
        """
        Select a file from the snapshot for processing.

        Currently uses the first file.

        Returns:
            str: The local file path of the first .gz file in the snapshot.

        """
        settings = get_settings()
        snapshot_root = settings.SNAPTSHOT_ROOT
        file_paths = enumerate_work_files(snapshot_root)
        if not file_paths:
            error_message = f"No files found in the snapshot directory {snapshot_root}."
            raise ValueError(error_message)
        return str(file_paths[0])

    @task
    def transform_and_write(file_path: str) -> dict:
        """
        Transform the selected file and write the output to a local JSONL file.

        Args:
            file_path (str): The local file path of the .gz file to process.

        Returns:
            dict: A summary of the processing results, including paths, record count, and any errors.

        """

        async def _run() -> tuple[list[bytes], dict]:
            """
            Define a helper function to async-run file processing.

            Returns:
                tuple[list[bytes], dict]: The result of processing the file
                    including the list of JSONL lines as bytes and any errors encountered.

            """
            return await transform_file(file_path)

        lines, errors = asyncio.run(_run())
        output_path = Path(__file__).parent / "smoke_test_output.jsonl"
        logger.info(f"Writing transformed lines to local file: {output_path}")
        output_path.write_bytes(b"".join(lines))
        error_log = _log_errors(Path(file_path), errors) if errors else None

        return {
            "file_path": file_path,
            "output_path": str(output_path),
            "size_mb": round(output_path.stat().st_size / (1024 * 1024), 2),
            "record_count": len(lines),
            "errors": errors,
            "error_log": str(error_log) if error_log else None,
        }

    @task
    def report(result: dict) -> None:
        logger.info(
            "Local-only smoke test complete\n"
            f"Source: {result["file_path"]}\n"
            f"Output: {result["output_path"]}\n"
            f"Records: {result["record_count"]}\n"
            f"Errors: {result["errors"]}\n"
            f"Error log: {result["error_log"]}"
        )

    file_path = select_file()
    result = transform_and_write(file_path)
    report(result)


smoke_test_local()
