"""Module to decompress gzipped JSONL files and upload them to Azure Blob Storage."""

import gzip
import os
import shutil
from pathlib import Path

from azure.core.exceptions import (
    AzureError,
)
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient
from dotenv import dotenv_values, load_dotenv
from loguru import logger
from tqdm import tqdm

load_dotenv_outcome = load_dotenv(Path.cwd() / ".env")
logger.info(f"Loaded .env file? {load_dotenv_outcome}")
logger.info(f"{dotenv_values()}")

STORAGE_ACCOUNT_NAME = os.getenv("STORAGE_BLOB_ACCOUNT")
STORAGE_BLOB_CONTAINER = os.getenv("STORAGE_BLOB_CONTAINER")


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
        account_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
        credential = AzureCliCredential()

        return BlobServiceClient(account_url, credential=credential)

    except AzureError as azure_error:
        error_message = f"Error getting blob client: {azure_error}"
        logger.error(error_message)
        raise BlobUploadError(error_message) from azure_error


def upload_to_blob_storage(data_path: Path) -> bool:
    """
    Upload the uncompressed file to blob storage.

    Args:
        data_path (Path): Uncompressed JSON-L file.

    Returns:
        bool: Success or not?

    """
    blob_name = data_path.name
    try:
        blob_service_client = get_blob_service_client()

        blob_client = blob_service_client.get_blob_client(
            container=STORAGE_BLOB_CONTAINER, blob=blob_name
        )

        with data_path.open("rb") as data:
            blob_client.upload_blob(data, overwrite=True)
            logger.info(f"Successfully uploaded {data_path.name}")
            return True

    except Exception as e:
        logger.exception(f"Upload failed for {data_path.name}: {e}")
        return False


def decompress_file(gz_path: Path) -> Path:
    """
    Decompress a gzipped JSONL file.

    Args:
        gz_path (Path): Path to the gzipped JSONL file.

    Returns:
        Path: Path to the decompressed JSONL file.

    """
    decompressed_path = gz_path.with_suffix("")
    logger.info(f"Decompressing {gz_path.name} → {decompressed_path.name}")
    with gzip.open(gz_path, "rb") as f_in, decompressed_path.open("wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    return decompressed_path


def process_file(gz_path: Path) -> None:
    """
    Process a gzipped JSONL file, decompress and upload to blob storage.

    Args:
        gz_path (Path): Path to the gzipped JSONL file.

    """
    try:
        jsonl_path = decompress_file(gz_path)

        if upload_to_blob_storage(jsonl_path):
            jsonl_path.unlink()
            logger.success(f"Uploaded and cleaned up: {gz_path.name}")
        else:
            logger.warning(f"Upload failed, keeping files: {gz_path.name}")

    except Exception as e:
        logger.exception(f"Error processing {gz_path.name}: {e}")


def main() -> None:
    """Decompress gzipped JSONL files and upload them to Azure Blob Storage."""
    load_dotenv()

    logger.add("decompress_and_upload.log", rotation="5 MB", level="INFO", enqueue=True)

    input_dir = Path.cwd() / "compressed_destiny_tim_query_subset_jsonl"
    files = sorted(input_dir.glob("*.jsonl.gz"))

    if not files:
        logger.error("No files found!")
        return

    logger.info(f"Found {len(files)} compressed files to upload.")
    for gz_file in tqdm(files, desc="Uploading", unit="file"):
        process_file(gz_file)


if __name__ == "__main__":
    main()
