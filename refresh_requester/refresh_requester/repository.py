"""Functionality to ingest content to the DESTINY repository."""

import time
from enum import StrEnum

from destiny_sdk.imports import (
    CollisionStrategy,
    ImportBatchIn,
    ImportBatchRead,
    ImportBatchSummary,
    ImportRecordIn,
    ImportRecordRead,
)
from loguru import logger
from pydantic import UUID4
from requests import Response
from requests.exceptions import JSONDecodeError

from refresh_requester.blob_storage import DestinyBlobStorageClient
from refresh_requester.config import Settings, get_retry_session
from refresh_requester.token_utils import TokenRequestError, get_token
from refresh_requester.utils import format_endpoint_url


class ImportSourceType(StrEnum):
    """Enumeration for import source types."""

    OPEN_ALEX = "openalex"
    SOLR = "solr"


class DestinyRepositoryImportError(Exception):
    """Custom exception for errors during import to the DESTINY repository."""


class DestinyRepositoryContentUploader:
    """Class to handle content upload to the DESTINY repository."""

    def __init__(self, settings: Settings) -> None:
        """Class constructor."""
        self.settings = settings
        self.session = get_retry_session()
        self.session.headers = {
            "Authorization": f"Bearer {get_token(self.settings)}",
        }

    def refresh_token(self) -> None:
        """
        Refresh the token used for authentication with the DESTINY repository.

        This method updates the session headers with a new access token.

        Raises:
            DestinyRepositoryImportError: If there is an error while refreshing the token.

        """
        try:
            self.session.headers["Authorization"] = f"Bearer {get_token(self.settings)}"
            logger.info("Token refreshed successfully.")
        except TokenRequestError as token_error:
            error_message = f"Failed to refresh token: {token_error}"
            raise DestinyRepositoryImportError(error_message) from token_error

    def construct_payload(
        self,
        processor_name: str,
        processor_version: str,
        expected_reference_count: int,
        source_name: str,
    ) -> ImportRecordIn:
        """
        Construct the payload for the import record.

        Args:
            processor_name (str): The name of the processor.
            processor_version (str): The version of the processor.
            expected_reference_count (int): The expected number of references.
            source_name (str): The name of the source.

        Returns:
            ImportRecordIn: The constructed payload for the import record.

        """
        return ImportRecordIn(
            processor_name=processor_name,
            processor_version=processor_version,
            expected_reference_count=expected_reference_count,
            source_name=source_name,
        )

    def retrieve_payload_from_source_type(
        self, source_type: ImportSourceType
    ) -> ImportRecordIn:
        """
        Retrieve the payload for the import record based on the source type.

        Args:
            source_type (ImportSourceType): The type of source for the import (e.g., OPEN_ALEX, SOLR).

        Returns:
            ImportRecordIn: The constructed payload for the import record.

        """
        if source_type == ImportSourceType.SOLR:
            return self.construct_payload(
                processor_name="Bulk Solr Importer",
                processor_version="initial_solr_import",
                expected_reference_count=-1,
                source_name="pik-solr",
            )
        return self.construct_payload(
            processor_name="Bulk OpenAlex Importer",
            processor_version="initial_openalex_import",
            expected_reference_count=-1,
            source_name="openalex",
        )

    def register_new_import(
        self, source_type: ImportSourceType = ImportSourceType.OPEN_ALEX
    ) -> ImportRecordRead:
        """
        Register a new import record with the DESTINY repository.

        Args:
            source_type (ImportSourceType): The type of source for the import (e.g., OPEN_ALEX, SOLR).

        Raises:
            DestinyRepositoryImportError: The error that occurred while registering the import,
                with a descriptive message.

        Returns:
            ImportRecordRead: The response from the DESTINY repository after registering the import.

        """
        base_endpoint_url = format_endpoint_url(self.settings.REPOSITORY_ENDPOINT)
        registration_url = f"{base_endpoint_url}/imports/records/"
        payload = self.retrieve_payload_from_source_type(source_type)

        response = self.session.post(
            registration_url,
            json=payload.model_dump(mode="json"),
        )
        response.raise_for_status()
        try:
            return ImportRecordRead.model_validate(response.json())
        except JSONDecodeError as json_decode_error:
            error_message = f"Failed to decode JSON response: {json_decode_error} from {response.content}"
            raise DestinyRepositoryImportError(error_message) from json_decode_error

    def register_import_batch_for_single_blob(
        self, blob_name: str, sas_url: str, import_record: ImportRecordRead
    ) -> ImportBatchRead:
        """
        Register an import batch for a single blob.

        Args:
            blob_name (str): The name of the blob to register.
            sas_url (str): The SAS URL of the blob to register.
            import_record (ImportRecordRead): The import record to associate with the batch.

        Returns:
            ImportBatchRead: The response from the DESTINY repository after registering the import batch.

        """
        base_endpoint_url = format_endpoint_url(self.settings.REPOSITORY_ENDPOINT)

        registration_url = (
            f"{base_endpoint_url}/imports/records/{import_record.id}/batches/"
        )
        payload = ImportBatchIn(
            collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
            storage_url=str(sas_url),
            callback_url=None,
        )
        response = self.session.post(
            registration_url,
            json=payload.model_dump(mode="json"),
        )
        response.raise_for_status()
        import_batch = ImportBatchRead.model_validate(response.json())
        logger.info(
            f"Registered import batch for blob {blob_name} with ID {import_batch.id}"
        )

        return import_batch

    def finalise_import_record(self, import_record_id: UUID4) -> Response:
        """
        Finalise the import record in the DESTINY repository.

        Args:
            import_record (UUID4): The import record id to finalise.

        Returns:
            Response: The response from the DESTINY repository after finalising the import record.

        Raises:
            DestinyRepositoryImportError: The error that occurred while finalising the import record,
                with a descriptive message.

        """
        base_endpoint_url = format_endpoint_url(self.settings.REPOSITORY_ENDPOINT)

        response = self.session.patch(
            f"{base_endpoint_url}/imports/records/{import_record_id}/finalise/",
        )
        response.raise_for_status()
        return response

    def check_if_import_batch_completed(
        self, import_record_id: UUID4, import_batch_id: UUID4
    ) -> bool:
        """
        Check if the import batch has completed.

        Args:
            import_record_id (UUID4): The ID of the import record the batch belongs to.
            import_batch_id (UUID4): The ID of the import batch to check.

        Returns:
            bool: True if the import batch has completed, False otherwise.

        """
        base_endpoint_url = format_endpoint_url(self.settings.REPOSITORY_ENDPOINT)

        response = self.session.get(
            f"{base_endpoint_url}/imports/records/{import_record_id}/batches/{import_batch_id}/"
        )
        response.raise_for_status()
        import_batch_status = ImportBatchRead.model_validate(response.json())
        return import_batch_status.status == "completed"

    def get_import_batch_summary(
        self, import_record_id: UUID4, import_batch_id: UUID4
    ) -> ImportBatchSummary:
        """
        Get the summary of the import batch.

        Args:
            import_record_id (UUID4): The ID of the import record the batch belongs to.
            import_batch_id (UUID4): The import batch ID.

        Returns:
            ImportBatchSummary: The summary of the import batch.

        """
        base_endpoint_url = format_endpoint_url(self.settings.REPOSITORY_ENDPOINT)

        response = self.session.get(
            f"{base_endpoint_url}/imports/records/{import_record_id}/batches/{import_batch_id}/summary/"
        )
        response.raise_for_status()
        return ImportBatchSummary.model_validate(response.json())

    def poll_import_batches_for_completion(
        self,
        import_record_id: UUID4,
        import_batch_ids: list[UUID4],
        retry_time_seconds: int = 30,
        max_retries: int = 5,
    ) -> None:
        """
        Poll the import batches for completion.

        This method checks the status of each import batch until it is completed
        or the maximum number of retries is reached.

        Args:
            import_record_id (UUID4): The ID of the import record the batches belong to.
            import_batch_ids (list[UUID4]): List of import batch IDs to poll for completion.
            retry_time_seconds (int, optional): Time to wait between retries in seconds. Defaults to 30.
            max_retries (int, optional): The maximum number of retries for checking import
                batch completion. Defaults to 5.

        """
        for import_batch_id in import_batch_ids:
            logger.info(f"Polling import batch {import_batch_id} for completion...")

            for attempt in range(max_retries):
                completed_status = self.check_if_import_batch_completed(
                    import_record_id, import_batch_id
                )
                if completed_status:
                    logger.info(
                        f"Import batch {import_batch_id} completed successfully."
                    )
                    break
                logger.info(
                    f"Import batch {import_batch_id} not completed yet. Attempt {attempt + 1}/{max_retries}."
                )
                logger.info(f"Waiting {retry_time_seconds} seconds before retrying...")
                time.sleep(retry_time_seconds)
            summary = self.get_import_batch_summary(import_record_id, import_batch_id)
            logger.info(f"Import batch {import_batch_id} summary: {summary}")


def upload_blob_storage_contents_to_repository(
    settings: Settings,
    blob_to_upload: str | None = None,
    blob_content_source: ImportSourceType = ImportSourceType.OPEN_ALEX,
) -> dict:
    """
    Upload all blob storage contents to the DESTINY repository.

    Args:
        settings (Settings): Pydantic settings object containing configuration.
        max_retries (int, optional): The maximum number of retries for checking import batch completion. Defaults to 5.
        blob_to_upload (str | None, optional): Specific blob to upload.
            If None, all blobs in the container will be uploaded. Defaults to None.

    Returns:
        dict: A dictionary containing the import record and a list of import batch IDs.

    """
    blob_client = DestinyBlobStorageClient()
    blob_url_pairs = blob_client.get_all_blob_url_pairs(blob_to_upload)
    uploader = DestinyRepositoryContentUploader(settings)
    import_record = uploader.register_new_import(source_type=blob_content_source)

    import_batch_ids = []  # type: list[UUID4]
    for blob_url_pair in blob_url_pairs:
        blob_name = blob_url_pair["blob_name"]
        sas_url = blob_url_pair["sas_url"]

        import_batch = uploader.register_import_batch_for_single_blob(
            blob_name, sas_url, import_record
        )
        import_batch_ids.append(import_batch.id)

    uploader.finalise_import_record(import_record.id)

    return {"import_record": import_record, "import_batch_ids": import_batch_ids}
