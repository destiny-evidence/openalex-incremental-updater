"""Shared fixtures for the Snapshot Bulk Feeder tests."""

import json
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from openalex_snapshot_processor.config import Settings
from openalex_snapshot_processor.models import (
    BatchRecord,
    BatchState,
    FeederState,
    Manifest,
    RuntimeSettings,
)


@pytest.fixture
def caplog(caplog: pytest.LogCaptureFixture) -> Generator[pytest.LogCaptureFixture]:
    """Route loguru output into pytest's caplog."""

    class PropagateHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), format="{message}")
    yield caplog
    logger.remove(handler_id)


@pytest.fixture(scope="session", autouse=True)
def anyio_backend() -> tuple[str, dict[str, Any]]:
    """Specify the anyio backend for async tests."""
    return "asyncio", {"use_uvloop": True}


# ------------------------------------------------------------------
# Environment / Settings
# ------------------------------------------------------------------
ENV_DEFAULTS: dict[str, str] = {
    "BATCH_DIR": "/fake/batches",
    "WINDOW_SIZE": "5",
    "POLL_INTERVAL_SECONDS": "60",
    "STORAGE_BLOB_ACCOUNT": "fakeaccount",
    "STORAGE_BLOB_CONTAINER": "fakecontainer",
    "STORAGE_BLOB_ACCOUNT_KEY": "ZmFrZWtleQ==",  # pragma: allowlist secret
    "BLOB_PREFIX": "snapshot_bulk/",
    "SAS_TOKEN_EXPIRY_HOURS": "168",
    "REPOSITORY_ENDPOINT": "https://fake-repo.example.com",
    "TOKEN_ENDPOINT": "https://fake-token.example.com/token",
    "PROCESSOR_NAME": "Test Feeder",
    "PROCESSOR_VERSION": "0.0.1",
    "SOURCE_NAME": "test-source",
    "DECOMPRESS_ON_UPLOAD": "false",
    "LOG_LEVEL": "DEBUG",
}


@pytest.fixture
def set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set all required environment variables for Settings."""
    for key, value in ENV_DEFAULTS.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def test_settings(set_test_env) -> Settings:
    """Return a Settings instance loaded from test env vars."""
    return Settings()


# ------------------------------------------------------------------
# Manifest
# ------------------------------------------------------------------
SAMPLE_MANIFEST_DICT: dict = {
    "created_at": "2026-02-23T10:00:00Z",
    "duration_seconds": 100.0,
    "totals": {
        "records_processed": 300000,
        "records_written": 300000,
        "records_skipped": 0,
        "records_failed": 0,
        "gz_files_processed": 3,
        "gz_files_corrupted": 0,
        "batch_files": 3,
    },
    "batches": [
        {"file": "batch_00001.jsonl.gz", "records": 100000},
        {"file": "batch_00002.jsonl.gz", "records": 100000},
        {"file": "batch_00003.jsonl.gz", "records": 100000},
    ],
}


@pytest.fixture
def sample_manifest() -> Manifest:
    """Return a parsed Manifest with 3 batches."""
    return Manifest.model_validate(SAMPLE_MANIFEST_DICT)


@pytest.fixture
def manifest_dir(tmp_path: Path) -> Path:
    """Create a temp directory with a manifest.json and dummy batch files."""
    (tmp_path / "manifest.json").write_text(
        json.dumps(SAMPLE_MANIFEST_DICT), encoding="utf-8"
    )
    for entry in SAMPLE_MANIFEST_DICT["batches"]:
        (tmp_path / entry["file"]).write_bytes(b"\x00")
    return tmp_path


# ------------------------------------------------------------------
# State
# ------------------------------------------------------------------
@pytest.fixture
def sample_state() -> FeederState:
    """Return a FeederState with 3 batches (2 pending, 1 completed)."""
    return FeederState(
        import_record_id="00000000-0000-0000-0000-000000000001",
        total_batches=3,
        started_at="2026-02-23T10:00:00Z",
        batches={
            "batch_00001.jsonl.gz": BatchRecord(
                filename="batch_00001.jsonl.gz",
                state=BatchState.COMPLETED,
                blob_name="snapshot_bulk/batch_00001.jsonl.gz",
                import_batch_id="00000000-0000-0000-0000-000000000010",
                submitted_at="2026-02-23T10:01:00Z",
                completed_at="2026-02-23T10:05:00Z",
            ),
            "batch_00002.jsonl.gz": BatchRecord(
                filename="batch_00002.jsonl.gz",
            ),
            "batch_00003.jsonl.gz": BatchRecord(
                filename="batch_00003.jsonl.gz",
            ),
        },
    )


@pytest.fixture
def runtime_settings() -> RuntimeSettings:
    """Return default runtime settings for tests."""
    return RuntimeSettings(window_size=5, poll_interval_seconds=60)
