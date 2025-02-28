"""Main module for the refresh requester job."""

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
from refresh_requester.openalex_refresh import OpenAlexRefreshError, request_refresh


class BlobUploadError(Exception):
    """Blob Upload Error."""


def run_job(fetch_date: date) -> dict:
    """
    Run the refresh requester job.

    Args:
        fetch_date (date): The date to request a refresh from

    Returns:
        dict: The response from the API

    """
    settings = get_settings()
    try:
        json_response = request_refresh(settings, fetch_date)
        logger.info(f"Refresh request successful for date {fetch_date}")
    except OpenAlexRefreshError as refresh_error:
        error_message = f"Error requesting refresh: {refresh_error}"
        logger.error(error_message)
        return {"error": error_message}
    return json_response


def blob_upload(data: dict, fetch_date: date) -> None:
    """
    Upload the refresh response to blob storage.

    Args:
        data (dict): The response from the API
        fetch_date (date): The date a request was requested from

    """
    filename = f"openalex_refresh_{fetch_date}.json"
    try:
        blob_service_client = BlobServiceClient.from_connection_string(
            get_settings().STORAGE_BLOB_CONNECTION_STRING
        )

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


def main() -> None:
    """Run the refresh requester job."""
    yesterday = datetime.now(tz=ZoneInfo("UTC")).date() - timedelta(days=1)
    fetch_date = yesterday
    data = run_job(fetch_date)

    blob_upload(data, fetch_date)


if __name__ == "__main__":
    main()
