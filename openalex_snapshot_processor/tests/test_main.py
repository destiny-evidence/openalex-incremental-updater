"""Tests for main.py — FastAPI endpoints."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from openalex_snapshot_processor.config import Settings
from openalex_snapshot_processor.models import (
    BatchRecord,
    BatchState,
    FeederState,
    RuntimeSettings,
)
from openalex_snapshot_processor.state import load_state, save_state


@pytest.fixture
def feeder_state():
    """Return a FeederState with mixed batch statuses."""
    return FeederState(
        import_record_id=UUID("00000000-0000-0000-0000-000000000001"),
        total_batches=4,
        started_at=datetime(2026, 2, 23, 10, 0, tzinfo=UTC),
        last_poll_at=datetime(2026, 2, 24, 12, 0, tzinfo=UTC),
        batches={
            "batch_00001.jsonl.gz": BatchRecord(
                filename="batch_00001.jsonl.gz",
                state=BatchState.COMPLETED,
            ),
            "batch_00002.jsonl.gz": BatchRecord(
                filename="batch_00002.jsonl.gz",
                state=BatchState.IN_PROGRESS,
                import_batch_id=UUID("00000000-0000-0000-0000-000000000010"),
            ),
            "batch_00003.jsonl.gz": BatchRecord(
                filename="batch_00003.jsonl.gz",
                state=BatchState.PENDING,
            ),
            "batch_00004.jsonl.gz": BatchRecord(
                filename="batch_00004.jsonl.gz",
                state=BatchState.FAILED,
                error="upload timeout",
            ),
        },
    )


@pytest.fixture
def client(feeder_state):
    """Return a TestClient with the feeder globals patched (no lifespan)."""
    import openalex_snapshot_processor.main as main_mod

    rs = RuntimeSettings(window_size=10, poll_interval_seconds=300)

    mock_feeder = MagicMock()
    mock_feeder.state = feeder_state
    mock_feeder.runtime_settings = rs
    mock_feeder.batch_dir = Path("/fake/batches")
    mock_feeder.is_paused = False
    mock_feeder.effective_window = 2

    original_feeder = main_mod._feeder
    original_rs = main_mod._runtime_settings
    main_mod._feeder = mock_feeder
    main_mod._runtime_settings = rs

    # Don't use context manager — avoids triggering the lifespan
    yield TestClient(main_mod.app, raise_server_exceptions=True)

    main_mod._feeder = original_feeder
    main_mod._runtime_settings = original_rs


def test_health(client) -> None:
    """GET /health should return 200 with status ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_status(client) -> None:
    """GET /status should return counts matching the fixture state."""
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_batches"] == 4
    assert data["completed"] == 1
    assert data["failed"] == 1
    assert data["in_progress"] == 1
    assert data["pending"] == 1
    assert data["window_size"] == 10
    assert data["effective_window"] == 2
    assert data["is_complete"] is False
    assert len(data["failed_batches"]) == 1
    assert data["failed_batches"][0]["filename"] == "batch_00004.jsonl.gz"


def test_status_feeder_not_running() -> None:
    """GET /status should return 503 when feeder is not running."""
    import openalex_snapshot_processor.main as main_mod

    original = main_mod._feeder
    main_mod._feeder = None
    try:
        tc = TestClient(main_mod.app, raise_server_exceptions=False)
        resp = tc.get("/status")
        assert resp.status_code == 503
    finally:
        main_mod._feeder = original


def test_patch_settings(client) -> None:
    """PATCH /settings should update runtime settings."""
    resp = client.patch(
        "/settings", json={"window_size": 20, "poll_interval_seconds": 120}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_size"] == 20
    assert data["poll_interval_seconds"] == 120


def test_patch_settings_partial(client) -> None:
    """PATCH /settings with only window_size should leave poll_interval unchanged."""
    resp = client.patch("/settings", json={"window_size": 15})
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_size"] == 15
    assert data["poll_interval_seconds"] == 300


def test_retry_batch_success(client) -> None:
    """POST /batches/{filename}/retry should reset a failed batch to pending."""
    with patch("openalex_snapshot_processor.main.save_state"):
        resp = client.post("/batches/batch_00004.jsonl.gz/retry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "pending"
    assert data["error"] is None


def test_retry_batch_not_found(client) -> None:
    """POST /batches/{filename}/retry should return 404 for unknown batch."""
    resp = client.post("/batches/nonexistent.jsonl.gz/retry")
    assert resp.status_code == 404


def test_retry_batch_wrong_state(client) -> None:
    """POST /batches/{filename}/retry should return 409 for non-failed batch."""
    resp = client.post("/batches/batch_00001.jsonl.gz/retry")
    assert resp.status_code == 409


def test_status_includes_is_paused(client) -> None:
    """GET /status should include the is_paused field."""
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_paused" in data
    assert data["is_paused"] is False


def test_pause_success(client) -> None:
    """POST /pause should return 200 when feeder is running."""
    import openalex_snapshot_processor.main as main_mod

    main_mod._feeder.is_paused = False
    resp = client.post("/pause")
    assert resp.status_code == 200
    assert resp.json() == {"status": "paused"}
    main_mod._feeder.pause.assert_called_once()


def test_pause_already_paused(client) -> None:
    """POST /pause should return 409 when feeder is already paused."""
    import openalex_snapshot_processor.main as main_mod

    main_mod._feeder.is_paused = True
    resp = client.post("/pause")
    assert resp.status_code == 409


def test_resume_success(client) -> None:
    """POST /resume should return 200 when feeder is paused."""
    import openalex_snapshot_processor.main as main_mod

    main_mod._feeder.is_paused = True
    resp = client.post("/resume")
    assert resp.status_code == 200
    assert resp.json() == {"status": "running"}
    main_mod._feeder.resume.assert_called_once()


def test_resume_not_paused(client) -> None:
    """POST /resume should return 409 when feeder is not paused."""
    import openalex_snapshot_processor.main as main_mod

    main_mod._feeder.is_paused = False
    resp = client.post("/resume")
    assert resp.status_code == 409


def test_delete_import(client) -> None:
    """DELETE /import should archive state, reset non-completed to PENDING."""
    with patch(
        "openalex_snapshot_processor.main.archive_and_reset_state"
    ) as mock_reset:
        # Simulate what archive_and_reset_state returns: completed preserved, rest PENDING
        mock_reset.return_value = FeederState(
            total_batches=4,
            batches={
                "batch_00001.jsonl.gz": BatchRecord(
                    filename="batch_00001.jsonl.gz",
                    state=BatchState.COMPLETED,
                ),
                "batch_00002.jsonl.gz": BatchRecord(
                    filename="batch_00002.jsonl.gz",
                ),
                "batch_00003.jsonl.gz": BatchRecord(
                    filename="batch_00003.jsonl.gz",
                ),
                "batch_00004.jsonl.gz": BatchRecord(
                    filename="batch_00004.jsonl.gz",
                ),
            },
        )
        resp = client.delete("/import")
    assert resp.status_code == 200
    data = resp.json()
    # Fixture has: 1 COMPLETED, 1 IN_PROGRESS, 1 PENDING, 1 FAILED
    # Non-terminal (IN_PROGRESS + PENDING) = 2 cancelled
    assert data["cancelled_batches"] == 2
    assert data["completed"] == 1
    assert data["pending"] == 3  # IN_PROGRESS + PENDING + FAILED all reset
    assert "failed" not in data


def test_cancel_writes_resumable_state(tmp_path, feeder_state) -> None:
    """DELETE /import with real archive_and_reset_state should write resumable state."""
    import openalex_snapshot_processor.main as main_mod

    # Write initial state to disk so archive_and_reset_state has something to archive
    save_state(feeder_state, tmp_path)

    rs = RuntimeSettings(window_size=10, poll_interval_seconds=300)
    mock_feeder = MagicMock()
    mock_feeder.state = feeder_state
    mock_feeder.runtime_settings = rs
    mock_feeder.batch_dir = tmp_path
    mock_feeder.is_paused = False

    original_feeder = main_mod._feeder
    original_rs = main_mod._runtime_settings
    main_mod._feeder = mock_feeder
    main_mod._runtime_settings = rs

    try:
        tc = TestClient(main_mod.app, raise_server_exceptions=True)
        resp = tc.delete("/import")
        assert resp.status_code == 200

        # Verify archive file was written
        archive_files = list(tmp_path.glob("state.cancelled.*.json"))
        assert len(archive_files) == 1

        # Verify state.json on disk is the reset state
        loaded = load_state(tmp_path)
        assert loaded is not None
        assert loaded.import_record_id is None
        assert loaded.batches["batch_00001.jsonl.gz"].state == BatchState.COMPLETED
        for name in (
            "batch_00002.jsonl.gz",
            "batch_00003.jsonl.gz",
            "batch_00004.jsonl.gz",
        ):
            assert loaded.batches[name].state == BatchState.PENDING

        # Verify the feeder's in-memory state was also updated
        assert mock_feeder.state.import_record_id is None
    finally:
        main_mod._feeder = original_feeder
        main_mod._runtime_settings = original_rs


@pytest.mark.asyncio
async def test_startup_after_cancel_creates_new_import_record(
    tmp_path, set_test_env, monkeypatch
) -> None:
    """_startup loading a post-cancel state should create a fresh ImportRecord in DR."""
    from openalex_snapshot_processor.main import _startup

    # Write a post-cancel state: import_record_id=None, 1 completed, 2 pending
    post_cancel_state = FeederState(
        total_batches=3,
        started_at=datetime(2026, 2, 24, 14, 0, tzinfo=UTC),
        batches={
            "batch_00001.jsonl.gz": BatchRecord(
                filename="batch_00001.jsonl.gz",
                state=BatchState.COMPLETED,
                blob_name="snapshot_bulk/batch_00001.jsonl.gz",
                import_batch_id=UUID("00000000-0000-0000-0000-000000000010"),
            ),
            "batch_00002.jsonl.gz": BatchRecord(filename="batch_00002.jsonl.gz"),
            "batch_00003.jsonl.gz": BatchRecord(filename="batch_00003.jsonl.gz"),
        },
    )
    save_state(post_cancel_state, tmp_path)

    # Point BATCH_DIR at tmp_path and construct real Settings
    monkeypatch.setenv("BATCH_DIR", str(tmp_path))
    settings = Settings()

    new_record_id = UUID("00000000-0000-0000-0000-000000000099")
    mock_record = MagicMock(id=new_record_id)

    with (
        patch("openalex_snapshot_processor.main.SnapshotBlobClient"),
        patch("openalex_snapshot_processor.main.DRClient") as mock_dr_cls,
    ):
        mock_dr = mock_dr_cls.return_value
        mock_dr.create_import_record.return_value = mock_record

        feeder = await _startup(settings)

        # _startup should have called create_import_record (not get_import_record)
        mock_dr.create_import_record.assert_called_once()
        mock_dr.get_import_record.assert_not_called()

    # Feeder state should have the new import_record_id
    assert feeder.state.import_record_id == new_record_id

    # Completed batch preserved, pending batches still pending
    assert feeder.state.batches["batch_00001.jsonl.gz"].state == BatchState.COMPLETED
    assert feeder.state.batches["batch_00002.jsonl.gz"].state == BatchState.PENDING
    assert feeder.state.batches["batch_00003.jsonl.gz"].state == BatchState.PENDING

    # State should have been persisted with the new import_record_id
    persisted = load_state(tmp_path)
    assert persisted is not None
    assert persisted.import_record_id == new_record_id
