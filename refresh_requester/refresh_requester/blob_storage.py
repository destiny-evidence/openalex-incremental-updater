"""Blob storage utilities."""

import json
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
from azure.storage.blob import BlobServiceClient
from loguru import logger

from refresh_requester.config import get_settings


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
        return BlobServiceClient.from_connection_string(
            get_settings().STORAGE_BLOB_CONNECTION_STRING
        )

    except AzureError as azure_error:
        error_message = f"Error getting blob client: {azure_error}"
        logger.error(error_message)
        raise BlobUploadError(error_message) from azure_error


def blob_upload(data: dict, refresh_date: date) -> None:
    """
    Upload the refresh response to blob storage.

    Args:
        data (dict): The response from the API
        refresh_date (date): The date at which the data was fetched

    """
    filename = f"openalex_refresh_{refresh_date}.json"
    try:
        blob_service_client = get_blob_service_client()

        blob_client = blob_service_client.get_blob_client(
            container=get_settings().STORAGE_BLOB_CONTAINER, blob=filename
        )

        blob_client.upload_blob(json.dumps(data), overwrite=True)
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
            date_str = blob.removeprefix("openalex_refresh_").removesuffix(".json")
            date_obj = date.fromisoformat("-".join(date_str))
            dates.append(date_obj)

    if len(dates) > 0:
        return max(dates)
    return datetime.now(tz=ZoneInfo("UTC")).date() - timedelta(days=1)
