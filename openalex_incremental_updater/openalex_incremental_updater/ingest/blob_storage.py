"""Blob storage interaction utility functions."""

import base64
from collections.abc import Iterator

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


def blob_upload(
    data: Iterator[bytes], filename: str, chunk_size: int = 4 * 1024 * 1024
) -> str:
    """
    Upload data to blob storage.

    Args:
        data (Iterator[bytes]): The response from the API, converted to JSON-lines
        filename (str): The name of the file to upload
        chunk_size (int): The size of each chunk to upload. Defaults to 4 MB.

    Returns:
        str: The filename of the uploaded blob

    """
    try:
        blob_service_client = get_blob_service_client()

        blob_client = blob_service_client.get_blob_client(
            container=get_settings().STORAGE_BLOB_CONTAINER, blob=filename
        )
        buffer = bytearray()
        block_ids = []
        block_num = 0
        for chunk in data:
            buffer.extend(chunk)
            while len(buffer) >= chunk_size:
                block_id = base64.b64encode(f"{block_num:07}".encode()).decode()
                blob_client.stage_block(
                    block_id=block_id,
                    data=buffer[:chunk_size],
                )
                block_ids.append(block_id)
                buffer = buffer[chunk_size:]
                block_num += 1

        # Upload remaining data as the final block
        if buffer:
            block_id = base64.b64encode(f"{block_num:07}".encode()).decode()
            blob_client.stage_block(
                block_id=block_id,
                data=buffer,
            )
            block_ids.append(block_id)

        blob_client.commit_block_list(block_ids)
        logger.info(f"Successfully uploaded entire refresh response to {filename}")

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
