"""Functionality to ingest content to the DESTINY repository."""

import time
from datetime import UTC, datetime

from loguru import logger
from pydantic import BaseModel, Field, PastDatetime
from requests.exceptions import JSONDecodeError

from refresh_requester.blob_storage import DestinyBlobStorageClient
from refresh_requester.config import Settings, get_retry_session
from refresh_requester.token import get_token


class DestinyRepositoryImportError(Exception):
    """Custom exception for errors during import to the DESTINY repository."""


class DestinyRepositoryImportRecord(BaseModel):
    """Base import record class."""

    search_string: str | None = Field(
        default=None,
        description="The search string used to produce this import",
    )
    searched_at: PastDatetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="""
The timestamp (including timezone) at which the search which produced
this import was conducted. If no timezone is included, the timestamp
is assumed to be in UTC.
        """,
    )
    processor_name: str = Field(
        description="The name of the processor that is importing the data."
    )
    processor_version: str = Field(
        description="The version of the processor that is importing the data."
    )
    notes: str | None = Field(
        default=None,
        description="""
Any additional notes regarding the import (eg. reason for importing, known
issues).
        """,
    )
    expected_reference_count: int = Field(
        description="""
The number of references expected to be included in this import.
-1 is accepted if the number is unknown.
""",
        ge=-1,
    )
    source_name: str = Field(
        description="The source of the reference being imported (eg. Open Alex)"
    )


class DestinyRepositoryContentUploader:
    """Class to handle content upload to the DESTINY repository."""

    def __init__(self, settings: Settings) -> None:
        """Class constructor."""
        self.settings = settings
        self.session = get_retry_session()
        self.session.headers = {
            "Authorization": f"Bearer {get_token(self.settings)}",
        }

    def register_new_import(self) -> dict:
        """
        Register a new import record with the DESTINY repository.

        Raises:
            DestinyRepositoryImportError: The error that occurred while registering the import,
                with a descriptive message.

        Returns:
            dict: The response from the DESTINY repository after registering the import.

        """
        registration_url = f"{self.settings.REPOSITORY_ENDPOINT}/imports/record"
        payload = DestinyRepositoryImportRecord(
            processor_name="Bulk OpenAlex Importer",
            processor_version="initial_openalex_import",
            expected_reference_count=-1,
            source_name="OpenAlex",
        )
        response = self.session.post(
            registration_url,
            json=payload.model_dump(mode="json"),
        )
        response.raise_for_status()
        try:
            return response.json()
        except JSONDecodeError as json_decode_error:
            error_message = f"Failed to decode JSON response: {json_decode_error} from {response.content}"
            raise DestinyRepositoryImportError(error_message) from json_decode_error

    def register_import_batch_for_single_blob(
        self, blob_name: str, sas_url: str, import_record: dict
    ) -> dict:
        """
        Register an import batch for a single blob.

        Args:
            blob_name (str): The name of the blob to register.
            sas_url (str): The SAS URL of the blob to register.
            import_record (dict): The import record to associate with the batch.

        Returns:
            dict: The response from the DESTINY repository after registering the import batch.

        """
        registration_url = f"{self.settings.REPOSITORY_ENDPOINT}/imports/record/{import_record["id"]}/batch/"
        payload = {
            "storage_url": sas_url,
            "callback_url": None,
        }
        response = self.session.post(
            registration_url,
            json=payload,
        )
        response.raise_for_status()
        import_batch = response.json()
        logger.info(
            f"Registered import batch for blob {blob_name} with ID {import_batch['id']}"
        )

        return import_batch

    def finalise_import_record(self, import_record: dict) -> dict:
        """
        Finalise the import record in the DESTINY repository.

        Args:
            import_record (dict): The import record to finalise.

        Raises:
            DestinyRepositoryImportError: The error that occurred while finalising the import record,
                with a descriptive message.

        Returns:
            dict: The response from the DESTINY repository after finalising the import record.

        """
        response = self.session.patch(
            f"{self.settings.REPOSITORY_ENDPOINT}/imports/record/{import_record['id']}/finalise",
        )
        response.raise_for_status()
        try:
            return response.json()
        except JSONDecodeError as json_decode_error:
            error_message = f"Failed to decode JSON response: {json_decode_error} from {response.content}"
            raise DestinyRepositoryImportError(error_message) from json_decode_error

    def check_if_import_batch_completed(self, import_batch_id: str) -> bool:
        """
        Check if the import batch has completed.

        Args:
            import_batch_id (str): The ID of the import batch to check.

        Returns:
            bool: True if the import batch has completed, False otherwise.

        """
        response = self.session.get(
            f"{self.settings.REPOSITORY_ENDPOINT}/imports/batch/{import_batch_id}"
        )
        response.raise_for_status()
        import_batch_status = response.json()
        completed = import_batch_status["status"] == "completed"
        logger.info(f"Import completed? {completed}")
        return completed

    def get_import_batch_summary(self, import_batch_id: str) -> dict:
        """
        Get the summary of the import batch.

        Args:
            import_record (dict): The import record containing the ID of the batch.

        Returns:
            dict: The summary of the import batch.

        """
        response = self.session.get(
            f"{self.settings.REPOSITORY_ENDPOINT}/imports/batch/{import_batch_id}/summary"
        )
        response.raise_for_status()
        return response.json()


def upload_blob_storage_contents_to_repository(
    settings: Settings, max_retries: int = 5
) -> None:
    """
    Upload all blob storage contents to the DESTINY repository.

    Args:
        settings (Settings): Pydantic settings object containing configuration.
        max_retries (int, optional): The maximum number of retries for checking import batch completion. Defaults to 5.

    """
    blob_client = DestinyBlobStorageClient()
    blob_url_pairs = blob_client.get_all_blob_url_pairs()
    uploader = DestinyRepositoryContentUploader(settings)
    import_record = uploader.register_new_import()

    import_batch_ids = []
    for blob_url_pair in blob_url_pairs:
        blob_name = blob_url_pair["blob_name"]
        sas_url = blob_url_pair["sas_url"]

        import_batch = uploader.register_import_batch_for_single_blob(
            blob_name, sas_url, import_record
        )
        import_batch_ids.append(import_batch["id"])

    uploader.finalise_import_record(import_record)

    for import_batch_id in import_batch_ids:
        logger.info(f"Polling import batch {import_batch_id} for completion...")

        for attempt in range(max_retries):
            completed_status = uploader.check_if_import_batch_completed(import_batch_id)
            if completed_status:
                logger.info(f"Import batch {import_batch_id} completed successfully.")
                break
            logger.info(
                f"Import batch {import_batch_id} not completed yet. Attempt {attempt + 1}/{max_retries}. Retry in 10s."
            )
            time.sleep(10)
        summary = uploader.get_import_batch_summary(import_batch_id)
        logger.info(f"Import batch {import_batch_id} summary: {summary}")
    logger.success("All import batches completed successfully.")
