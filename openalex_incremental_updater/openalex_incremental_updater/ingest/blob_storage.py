"""Blob storage interaction utility functions."""

import base64
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    HttpResponseError,
    ResourceExistsError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.identity import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient
from loguru import logger

from openalex_incremental_updater.core.config import get_settings


class BlobUploadError(Exception):
    """Blob Upload Error."""


async def _safe_delete_blob(blob_client: BlobServiceClient) -> None:
    """
    Attempt to delete a blob safely.

    In the event that an upload fails partway through, we want to delete the
    incomplete blob to avoid leaving corrupted data in storage.

    This centralises deletion logic and catches any exceptions encountered
    during deletion, logging them and preventing failure propagation.

    Args:
        blob_client (BlobServiceClient): The blob client to delete from

    """
    if blob_client is None:
        return
    try:
        await blob_client.delete_blob()
    except Exception as delete_error:
        # exceptionally, catch all exceptions here to avoid masking the original error
        logger.error(f"Error deleting blob after failure: {delete_error}")


@asynccontextmanager
async def get_blob_service_client() -> AsyncGenerator[BlobServiceClient]:
    """
    Define an async context manager to get a blob service client.

    Raises:
        BlobUploadError: A descriptive error message

    Yields:
        AsyncGenerator[BlobServiceClient, None]: The blob service client

    """
    client = None
    try:
        account_url = (
            f"https://{get_settings().STORAGE_BLOB_ACCOUNT}.blob.core.windows.net"
        )
        credential = DefaultAzureCredential()

        try:
            client = BlobServiceClient(account_url, credential=credential)
        except AzureError as azure_error:
            error_message = f"Error getting blob client: {azure_error}"
            logger.error(error_message)
            raise BlobUploadError(error_message) from azure_error
        yield client
    finally:
        if client is not None:
            await client.close()


async def blob_upload(
    data: AsyncIterator[bytes], filename: str, chunk_size: int = 4 * 1024 * 1024
) -> str:
    """
    Upload data to blob storage.

    Args:
        data (AsyncIterator[bytes]): The response from the API, converted to JSON-lines
        filename (str): The name of the file to upload
        chunk_size (int): The size of each chunk to upload. Defaults to 4 MB.

    Returns:
        str: The filename of the uploaded blob

    """
    try:
        async with get_blob_service_client() as blob_service_client:
            blob_client = blob_service_client.get_blob_client(
                container=get_settings().STORAGE_BLOB_CONTAINER, blob=filename
            )
            buffer = bytearray()
            block_ids = []
            block_num = 0
            async for chunk in data:
                buffer.extend(chunk)
                while len(buffer) >= chunk_size:
                    block_id = base64.b64encode(f"{block_num:07}".encode()).decode()
                    await blob_client.stage_block(
                        block_id=block_id,
                        data=buffer[:chunk_size],
                    )
                    block_ids.append(block_id)
                    buffer = buffer[chunk_size:]
                    block_num += 1

            if buffer:
                block_id = base64.b64encode(f"{block_num:07}".encode()).decode()
                await blob_client.stage_block(
                    block_id=block_id,
                    data=buffer,
                )
                block_ids.append(block_id)

            if not block_ids:
                logger.warning("Uploading empty blob.")

            await blob_client.commit_block_list(block_ids)
            logger.info(f"Successfully uploaded entire refresh response to {filename}")

    except (ResourceExistsError, ResourceNotFoundError) as storage_error:
        error_message = f"Error uploading refresh response: {storage_error}"
        logger.error(error_message)
        await _safe_delete_blob(blob_client)
        raise BlobUploadError(error_message) from storage_error
    except (ClientAuthenticationError, HttpResponseError) as request_error:
        error_message = f"Error uploading refresh response: {request_error}"
        logger.error(error_message)
        await _safe_delete_blob(blob_client)
        raise BlobUploadError(error_message) from request_error
    except (ServiceRequestError, AzureError) as azure_error:
        error_message = f"Error uploading refresh response: {azure_error}"
        logger.error(error_message)
        await _safe_delete_blob(blob_client)
        raise BlobUploadError(error_message) from azure_error
    except ValueError as value_error:
        error_message = f"Error uploading refresh response: {value_error}"
        logger.error(error_message)
        await _safe_delete_blob(blob_client)
        raise BlobUploadError(error_message) from value_error
    return filename
