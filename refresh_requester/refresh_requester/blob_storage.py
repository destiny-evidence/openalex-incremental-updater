"""Blob storage utilities."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    HttpResponseError,
    ResourceExistsError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas
from loguru import logger

from refresh_requester.config import get_settings


class BlobUploadError(Exception):
    """Blob Upload Error."""


class DestinyBlobStorageClient:
    """A client for interacting with Blobs within the internal Azure Blob Storage Containers."""

    def __init__(self) -> None:
        """Class constructor."""
        self.blob_service_client = get_blob_service_client()
        self.settings = get_settings()

    def list_all_blobs(self) -> list[str]:
        """
        List all blobs in the storage container.

        Returns:
            list[str]: A list of blob names.

        """
        logger.info("Listing all blobs in the storage container.")
        container_client = self.blob_service_client.get_container_client(
            self.settings.STORAGE_BLOB_CONTAINER
        )
        return [blob.name for blob in container_client.list_blobs()]

    def get_single_blob_sas_token(self, blob_name: str) -> str:
        """
        Generate a SAS token for a single blob.

        Args:
            blob_name (str): The name of the blob to generate a SAS token for.

        Returns:
            str: The generated SAS token for the specified blob.

        """
        logger.info(f"Generating SAS token for blob: {blob_name}")
        return generate_blob_sas(
            account_name=self.settings.STORAGE_BLOB_ACCOUNT,
            container_name=self.settings.STORAGE_BLOB_CONTAINER,
            blob_name=blob_name,
            account_key=self.settings.STORAGE_BLOB_ACCOUNT_KEY.get_secret_value,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(tz=ZoneInfo("UTC")) + timedelta(hours=1),
        )

    def get_blob_sas_pair(self, blob_name: str) -> dict:
        """
        Get the SAS URL for a blob.

        Args:
            blob_name (str): The name of the blob to get the SAS URL for.

        Returns:
            dict: A dictionary containing the blob name and its corresponding SAS URL.

        """
        logger.info(f"Generating SAS token for blob: {blob_name}")
        sas_token = self.get_single_blob_sas_token(blob_name)
        sas_url = f"https://{self.settings.STORAGE_BLOB_ACCOUNT}.blob.core.windows.net/{self.settings.STORAGE_BLOB_CONTAINER}/{blob_name}?{sas_token}"

        return {"blob_name": blob_name, "sas_url": sas_url}

    def get_all_blob_url_pairs(self) -> list[dict]:
        """
        Get all blob names and their corresponding SAS URLs.

        Returns:
            list[dict]: A list of dictionaries, each containing a blob name and its corresponding SAS URL.

        """
        all_blob_sas_pairs = []
        blobs_list = self.list_all_blobs()
        for blob in blobs_list:
            blob_sas_pair = self.get_blob_sas_pair(blob)
            all_blob_sas_pairs.append(blob_sas_pair)
        return all_blob_sas_pairs


def get_blob_service_client() -> BlobServiceClient:
    """
    Get a blob client.

    Raises:
        BlobUploadError: A descriptive error message

    Returns:
        BlobServiceClient: A blob client

    """
    try:
        account_url = (
            f"https://{get_settings().STORAGE_BLOB_ACCOUNT}.blob.core.windows.net"
        )
        credential = DefaultAzureCredential()

        return BlobServiceClient(account_url, credential=credential)

    except AzureError as azure_error:
        error_message = f"Error getting blob client: {azure_error}"
        logger.error(error_message)
        raise BlobUploadError(error_message) from azure_error


def blob_upload(data: str, fetch_date: date, refresh_date: date) -> None:
    """
    Upload the refresh response to blob storage.

    Args:
        data (str): The response from the API, converted to JSON-lines
        refresh_date (date): The date at which the data was fetched

    """
    filename = (
        f"openalex_refresh_from_date_{fetch_date}_refreshed_on_{refresh_date}.jsonl"
    )
    try:
        blob_service_client = get_blob_service_client()

        blob_client = blob_service_client.get_blob_client(
            container=get_settings().STORAGE_BLOB_CONTAINER, blob=filename
        )

        blob_client.upload_blob(data, overwrite=True)
        logger.info(f"Successfully uploaded refresh response to {filename}")

    except (ResourceExistsError, ResourceNotFoundError) as storage_error:
        error_message = f"Error uploading refresh response: {storage_error}"
        logger.error(error_message)
        raise BlobUploadError(error_message) from storage_error
    except (ClientAuthenticationError, HttpResponseError) as request_error:
        error_message = f"Error uploading refresh response: {request_error}"
        logger.error(error_message)
        raise BlobUploadError(error_message) from request_error
    except (ServiceRequestError, AzureError) as azure_error:
        error_message = f"Error uploading refresh response: {azure_error}"
        logger.error(error_message)
        raise BlobUploadError(error_message) from azure_error
    except ValueError as value_error:
        error_message = f"Error uploading refresh response: {value_error}"
        logger.error(error_message)
        raise BlobUploadError(error_message) from value_error


def list_blobs_in_storage() -> list[str]:
    """
    List all blobs in the storage container.

    Returns:
        list[str]: A list of blob names

    """
    blob_service_client = get_blob_service_client()

    container_client = blob_service_client.get_container_client(
        get_settings().STORAGE_BLOB_CONTAINER
    )

    return [blob.name for blob in container_client.list_blobs()]


def check_previous_file_dates() -> date:
    """
    Determine if any previous data is in blob storage.

    Take the date from the filename if so. Otherwise, return yesterday's date.

    Returns:
        date: The most recent date from the filenames

    """
    blob_list = list_blobs_in_storage()

    dates = []
    for blob in blob_list:
        if "openalex_refresh_" in blob:
            date_str = blob.rsplit("_", 1)[1].removesuffix(".jsonl")
            date_obj = date.fromisoformat(date_str)
            dates.append(date_obj)

    if len(dates) > 0:
        return max(dates)
    return datetime.now(tz=ZoneInfo("UTC")).date() - timedelta(days=1)
