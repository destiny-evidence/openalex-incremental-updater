"""
DAG for the full run of the OpenAlex snapshot processor.

This DAG orchestrates the end-to-end processing of
OpenAlex snapshot works files, including enumeration (counting of files),
processing (conversion to DESTINY-Reference-like JSONL), upload
to blob storage and registration of uploaded blobs in the DESTINY repository.

This DAG has no schedule and should be triggered manually.
It is not envisaged that we will want to run this regularly.
"""

from datetime import timedelta

import pendulum
from airflow.decorators import dag, task
from loguru import logger

from openalex_snapshot_processor.config import get_settings
from openalex_snapshot_processor.enumeration import enumerate_work_files
from openalex_snapshot_processor.file_processor import process_file
from openalex_snapshot_processor.registration import register_file_blobs


@dag(
    dag_id="openalex_snapshot_dag",
    schedule=None,
    start_date=pendulum.now("UTC"),
    catchup=False,
    max_active_tasks=16,
    tags=["openalex", "snapshot"],
    doc_md=__doc__,
)
def openalex_snapshot_ingest() -> None:
    """
    Define the entire DAG for the OpenAlex snapshot ingest process.

    Uses @task to define individual step-wise tasks.
    """

    @task(task_id="enumerate_files")
    def enumerate_files() -> list[str]:
        """
        Enumerate the OpenAlex snapshot works files to be processed.

        Returns:
            list[str]: List of file paths to be processed.

        """
        settings = get_settings()
        file_paths = enumerate_work_files(settings.SNAPSHOT_ROOT)
        return [str(file_path) for file_path in file_paths]

    @task(
        task_id="process_single_file",
        retries=3,
        retry_delay=timedelta(minutes=1),
    )
    def process_single_file(file_path: str) -> dict:
        """
        Process each OpenAlex snapshot works file: convert and upload to blob storage.

        Args:
            file_path (str): Path to the file to be processed.

        Returns:
            dict: The metadata of the processed file, as dictionary.

        """
        return process_file(file_path).model_dump()

    @task(task_id="register_blobs", retries=3, retry_delay=timedelta(minutes=1))
    def register_blob(processed_file: dict) -> dict:
        """
        Register the uploaded blob in the DESTINY repository.

        Args:
            processed_file[dict]: The processed file object, as a dictionary.

        Returns:
            dict: The response from the registration API.

        """
        report = register_file_blobs(processed_file.get("base_blob_name", ""))

        import_record_json = report.import_record.model_dump_json()

        return {
            "file_path": processed_file.get("file_path"),
            "base_blob_name": processed_file.get("base_blob_name"),
            "blob_names": processed_file.get("blob_names"),
            "record_count": processed_file.get("record_count"),
            "error_log": processed_file.get("error_log"),
            "import_record": import_record_json,
            "import_batch_count": len(report.import_batch_ids),
        }

    @task(task_id="report")
    def report(results: list[dict]) -> None:
        """
        Log a summary of the full snapshot ingest run.

        Args:
            results (list[dict]): A list of registration results dicts.

        """
        total_files = len(results)
        total_records = sum(record.get("record_count", 0) for record in results)
        total_blobs = sum(len(record.get("blob_names") or []) for record in results)
        total_batches = sum(record.get("import_batch_count", 0) for record in results)
        files_with_errors = [
            record["file_path"] for record in results if record.get("error_log")
        ]

        logger.success(
            "Snapshot ingest complete!\n"
            f"{total_files} files processed\n"
            f"{total_records} records processed\n"
            f"{total_blobs} blobs uploaded\n"
            f"{total_batches} import batches generated"
        )
        if files_with_errors:
            logger.warning(
                f"{len(files_with_errors)} files with data quality errors.\n"
                f"{files_with_errors=}"
            )

    file_paths = enumerate_files()
    processed_files = process_single_file.expand(file_path=file_paths)
    registration_results = register_blob.expand(processed_file=processed_files)
    report(registration_results)


openalex_snapshot_ingest()
