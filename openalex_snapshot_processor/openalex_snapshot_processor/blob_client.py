"""Azure Blob Storage client for uploading batch files and generating SAS URLs."""

import gzip
import io
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)
from loguru import logger

from openalex_snapshot_processor.config import Settings


class BlobUploadError(Exception):
    """Raised when a blob upload fails."""


def _build_service_client(settings: Settings) -> BlobServiceClient:
    """
    Build a BlobServiceClient from settings.

    When ``STORAGE_BLOB_ENDPOINT`` is set (e.g. Azurite), uses shared-key auth
    against the custom endpoint.  Otherwise uses DefaultAzureCredential against
    the standard Azure endpoint.
    """
    if settings.STORAGE_BLOB_ENDPOINT:
        from azure.core.credentials import AzureNamedKeyCredential

        credential = AzureNamedKeyCredential(
            settings.STORAGE_BLOB_ACCOUNT,
            settings.STORAGE_BLOB_ACCOUNT_KEY.get_secret_value(),
        )
        return BlobServiceClient(
            account_url=settings.STORAGE_BLOB_ENDPOINT,
            credential=credential,
        )

    from azure.identity import DefaultAzureCredential

    account_url = f"https://{settings.STORAGE_BLOB_ACCOUNT}.blob.core.windows.net"
    return BlobServiceClient(account_url, credential=DefaultAzureCredential())


class SnapshotBlobClient:
    """Upload pre-processed batch files and generate SAS URLs."""

    def __init__(self, settings: Settings) -> None:
        """Initialise the blob client from application settings."""
        self._settings = settings
        self._service_client = _build_service_client(settings)
        self._blob_base_url = (
            settings.STORAGE_BLOB_ENDPOINT
            or f"https://{settings.STORAGE_BLOB_ACCOUNT}.blob.core.windows.net"
        )

    def upload_file(self, file_path: Path, blob_name: str) -> None:
        """
        Upload a local file to Azure Blob Storage.

        When ``DECOMPRESS_ON_UPLOAD`` is *True*, the .gz file is decompressed
        before uploading (and the blob name should omit the .gz suffix).
        Otherwise the raw .gz bytes are uploaded with ``Content-Encoding: gzip``.

        Raises:
            BlobUploadError: On any Azure SDK failure.

        """
        blob_client = self._service_client.get_blob_client(
            container=self._settings.STORAGE_BLOB_CONTAINER, blob=blob_name
        )

        try:
            limit = self._settings.TEST_RECORD_LIMIT
            if limit is not None:
                data = self._truncated_gz(file_path, limit)
                blob_client.upload_blob(
                    data,
                    overwrite=True,
                    content_settings=ContentSettings(content_encoding="gzip"),
                )
                logger.info(
                    "Uploaded {} -> {} (truncated to {} records)",
                    file_path.name,
                    blob_name,
                    limit,
                )
            elif self._settings.DECOMPRESS_ON_UPLOAD:
                with gzip.open(file_path, "rb") as gz:
                    blob_client.upload_blob(gz.read(), overwrite=True)
            else:
                with file_path.open("rb") as fh:
                    blob_client.upload_blob(
                        fh.read(),
                        overwrite=True,
                        content_settings=ContentSettings(content_encoding="gzip"),
                    )
            if limit is None:
                logger.info("Uploaded {} -> {}", file_path.name, blob_name)
        except Exception as exc:
            msg = f"Failed to upload {file_path.name}: {exc}"
            logger.error(msg)
            raise BlobUploadError(msg) from exc

    @staticmethod
    def _truncated_gz(file_path: Path, limit: int) -> bytes:
        """Read a .jsonl.gz, keep the first *limit* lines, re-compress."""
        buf = io.BytesIO()
        with (
            gzip.open(file_path, "rb") as src,
            gzip.GzipFile(fileobj=buf, mode="wb") as dst,
        ):
            for i, line in enumerate(src):
                if i >= limit:
                    break
                dst.write(line)
        return buf.getvalue()

    def generate_sas_url(self, blob_name: str) -> str:
        """Generate a read-only SAS URL for a blob."""
        sas_token = generate_blob_sas(
            account_name=self._settings.STORAGE_BLOB_ACCOUNT,
            container_name=self._settings.STORAGE_BLOB_CONTAINER,
            blob_name=blob_name,
            account_key=self._settings.STORAGE_BLOB_ACCOUNT_KEY.get_secret_value(),
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(tz=ZoneInfo("UTC"))
            + timedelta(hours=self._settings.SAS_TOKEN_EXPIRY_HOURS),
        )
        return (
            f"{self._blob_base_url}"
            f"/{self._settings.STORAGE_BLOB_CONTAINER}/{blob_name}?{sas_token}"
        )

    def blob_exists(self, blob_name: str) -> bool:
        """Check whether a blob already exists in the container."""
        blob_client = self._service_client.get_blob_client(
            container=self._settings.STORAGE_BLOB_CONTAINER, blob=blob_name
        )
        return blob_client.exists()
