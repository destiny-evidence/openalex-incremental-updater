"""Define smoke tests that incorporate Azure functionality."""

import pendulum
from airflow.decorators import dag, task
from loguru import logger

from openalex_snapshot_processor.config import get_settings
from openalex_snapshot_processor.enumeration import enumerate_work_files
from openalex_snapshot_processor.file_processor import ProcessedFile, process_file
from openalex_snapshot_processor.registration import register_file_blobs


@dag(
    dag_id="smoke_test_azure",
    schedule=None,
    start_date=pendulum.now("UTC"),
    catchup=False,
    tags=["openalex", "smoke-test", "azure"],
    doc_md=__doc__,
)
def smoke_test_azure() -> None:
    """
    Define a DAG to perform Azure smoke tests.

    Raises:
        ValueError: Raises if no candidate files are found.

    """

    @task
    def select_file() -> str:
        """
        Select a single file to process.

        Currently uses the first file found,.

        Returns:
            str: Path to selected file, as string.

        """
        settings = get_settings()
        snapshot_root = settings.SNAPSHOT_ROOT
        files = enumerate_work_files(snapshot_root)
        if not files:
            error_message = f"No files found under {snapshot_root}"
            raise ValueError(error_message)
        return str(files[0])

    @task
    def process_single_file(file_path: str) -> ProcessedFile:
        """
        Process a single file.

        Args:
            file_path (str): Path to file to process, as string.

        Returns:
            ProcessedFile: A ProcessedFile object.

        """
        return process_file(file_path)

    @task
    def register_blobs(process_result: ProcessedFile) -> dict:
        report = register_file_blobs(process_result.base_blob_name)

        return {
            "base_blob_name": process_result.base_blob_name,
            "blob_count": len(process_result.blob_names),
            "record_count": process_result.record_count,
            "error_log": process_result.error_log,
            "import_record": report.import_record,
            "import_batch_count": len(report.import_batch_ids),
        }

    @task
    def report(result: dict) -> None:
        logger.info(
            "Azure-focused smoke test complete\n"
            f"Base blob {result["base_blob_name"]}\n"
            f"Blobs uploaded: {result["blob_count"]}\n"
            f"Records {result["record_count"]}\n"
            f"Error log: {result["error_log"]}\n"
            f"Import record: {result["import_record"]}\n"
            f"Batches: {result["import_batch_count"]}"
        )

    file_path = select_file()
    processed_result = process_single_file(file_path)
    registration_result = register_blobs(processed_result)
    report(registration_result)


smoke_test_azure()
