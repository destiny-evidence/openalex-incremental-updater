"""Destiny Repository API client for import record and batch management."""

import time
from http import HTTPStatus
from uuid import UUID

import requests
from destiny_sdk.imports import (
    ImportBatchIn,
    ImportBatchRead,
    ImportRecordIn,
    ImportRecordRead,
)
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from openalex_snapshot_processor.config import Settings

TOKEN_REFRESH_SECONDS = 30 * 60  # 30 minutes


class DRClientError(Exception):
    """Raised on unrecoverable DR API errors."""


def _create_retry_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
        ],
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def _strip_trailing_slash(url: str) -> str:
    return url.rstrip("/")


class DRClient:
    """Synchronous client for the Destiny Repository imports API."""

    def __init__(self, settings: Settings) -> None:
        """Initialise the DR client and fetch an initial auth token."""
        self._settings = settings
        self._base_url = _strip_trailing_slash(str(settings.REPOSITORY_ENDPOINT))
        self._session = _create_retry_session()
        self._token_fetched_at: float = 0.0
        self._ensure_token()

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------
    def _ensure_token(self) -> None:
        """Refresh the bearer token if it's older than TOKEN_REFRESH_SECONDS."""
        if self._settings.TOKEN_ENDPOINT is None:
            return  # auth bypass — no token needed
        now = time.monotonic()
        if now - self._token_fetched_at < TOKEN_REFRESH_SECONDS:
            return
        token = self._fetch_token()
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._token_fetched_at = now
        logger.info("DR token refreshed")

    def _fetch_token(self) -> str:
        url = str(self._settings.TOKEN_ENDPOINT)
        resp = self._session.get(url, timeout=60)
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            msg = "No access_token in token response"
            raise DRClientError(msg)
        return token

    # ------------------------------------------------------------------
    # Import Record
    # ------------------------------------------------------------------
    def create_import_record(
        self,
        expected_reference_count: int = -1,
    ) -> ImportRecordRead:
        """POST /imports/records/ — create a new ImportRecord."""
        self._ensure_token()
        payload = ImportRecordIn(
            processor_name=self._settings.PROCESSOR_NAME,
            processor_version=self._settings.PROCESSOR_VERSION,
            expected_reference_count=expected_reference_count,
            source_name=self._settings.SOURCE_NAME,
        )
        resp = self._session.post(
            f"{self._base_url}/imports/records/",
            json=payload.model_dump(mode="json"),
        )
        resp.raise_for_status()
        record = ImportRecordRead.model_validate(resp.json())
        logger.info("Created ImportRecord {}", record.id)
        return record

    def get_import_record(self, import_record_id: UUID) -> ImportRecordRead:
        """GET /imports/records/{id}/ — verify an ImportRecord still exists."""
        self._ensure_token()
        resp = self._session.get(
            f"{self._base_url}/imports/records/{import_record_id}/",
        )
        resp.raise_for_status()
        return ImportRecordRead.model_validate(resp.json())

    def finalise_import_record(self, import_record_id: UUID) -> None:
        """PATCH /imports/records/{id}/finalise/."""
        self._ensure_token()
        resp = self._session.patch(
            f"{self._base_url}/imports/records/{import_record_id}/finalise/",
        )
        resp.raise_for_status()
        logger.info("Finalised ImportRecord {}", import_record_id)

    # ------------------------------------------------------------------
    # Import Batch
    # ------------------------------------------------------------------
    def register_batch(self, import_record_id: UUID, sas_url: str) -> ImportBatchRead:
        """POST /imports/records/{id}/batches/ — register a new batch."""
        self._ensure_token()
        payload = ImportBatchIn(storage_url=sas_url)
        resp = self._session.post(
            f"{self._base_url}/imports/records/{import_record_id}/batches/",
            json=payload.model_dump(mode="json"),
        )
        resp.raise_for_status()
        batch = ImportBatchRead.model_validate(resp.json())
        logger.info("Registered batch {}", batch.id)
        return batch

    def get_batch_status(
        self, import_record_id: UUID, batch_id: UUID
    ) -> ImportBatchRead:
        """GET /imports/records/{id}/batches/{batch_id}/ — poll batch status."""
        self._ensure_token()
        resp = self._session.get(
            f"{self._base_url}/imports/records/{import_record_id}/batches/{batch_id}/",
        )
        resp.raise_for_status()
        return ImportBatchRead.model_validate(resp.json())
