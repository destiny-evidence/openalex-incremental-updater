"""Blob storage interaction utility functions."""

from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    HttpResponseError,
    ResourceExistsError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from loguru import logger

from openalex_incremental_updater.core.config import get_settings


class BlobUploadError(Exception):
    """Blob Upload Error."""


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


def blob_upload(data: str, filename: str) -> str:
    """
    Upload data to blob storage.

    Args:
        data (str): The response from the API, converted to JSON-lines
        filename (str): The name of the file to upload

    Returns:
        str: The filename of the uploaded blob

    """
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
    return filename
