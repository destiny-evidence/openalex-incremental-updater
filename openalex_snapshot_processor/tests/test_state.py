"""Tests for state.py."""

import json

import pytest

from openalex_snapshot_processor.models import BatchRecord, BatchState, FeederState
from openalex_snapshot_processor.state import (
    archive_and_reset_state,
    initialize_state,
    load_manifest,
    load_state,
    save_state,
)


def test_load_manifest_success(manifest_dir) -> None:
    """load_manifest should parse a valid manifest.json."""
    manifest = load_manifest(manifest_dir)
    assert len(manifest.batches) == 3
    assert manifest.totals.batch_files == 3


def test_load_manifest_missing(tmp_path) -> None:
    """load_manifest should raise FileNotFoundError if manifest.json is absent."""
    with pytest.raises(FileNotFoundError, match="Manifest not found"):
        load_manifest(tmp_path)


def test_load_state_returns_none_when_absent(tmp_path) -> None:
    """load_state should return None when state.json does not exist."""
    assert load_state(tmp_path) is None


def test_save_and_load_state_round_trip(tmp_path) -> None:
    """save_state then load_state should round-trip cleanly."""
    state = FeederState(
        import_record_id="00000000-0000-0000-0000-000000000001",
        total_batches=2,
        batches={
            "a.jsonl.gz": BatchRecord(filename="a.jsonl.gz"),
            "b.jsonl.gz": BatchRecord(
                filename="b.jsonl.gz",
                state=BatchState.COMPLETED,
            ),
        },
    )
    save_state(state, tmp_path)

    # File should exist
    state_path = tmp_path / "state.json"
    assert state_path.exists()

    # Content should be valid JSON
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["total_batches"] == 2

    # Round-trip through load_state
    loaded = load_state(tmp_path)
    assert loaded is not None
    assert loaded.import_record_id == state.import_record_id
    assert loaded.batches["b.jsonl.gz"].state == BatchState.COMPLETED


def test_save_state_atomic(tmp_path) -> None:
    """save_state should not leave temp files on success."""
    state = FeederState(total_batches=0)
    save_state(state, tmp_path)

    # Only state.json should exist (no .tmp files)
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0].name == "state.json"


def test_initialize_state(sample_manifest) -> None:
    """initialize_state should create PENDING batches from a manifest."""
    state = initialize_state(sample_manifest)
    assert state.total_batches == 3
    assert state.started_at is not None
    assert state.import_record_id is None

    for batch in state.batches.values():
        assert batch.state == BatchState.PENDING


def test_archive_and_reset_state(tmp_path) -> None:
    """archive_and_reset_state should archive, preserve completed, reset the rest."""
    from uuid import UUID

    original = FeederState(
        import_record_id=UUID("00000000-0000-0000-0000-000000000001"),
        total_batches=4,
        started_at="2026-02-23T10:00:00Z",
        batches={
            "a.jsonl.gz": BatchRecord(
                filename="a.jsonl.gz",
                state=BatchState.COMPLETED,
                blob_name="snapshot_bulk/a.jsonl.gz",
                import_batch_id=UUID("00000000-0000-0000-0000-000000000010"),
            ),
            "b.jsonl.gz": BatchRecord(
                filename="b.jsonl.gz",
                state=BatchState.IN_PROGRESS,
                blob_name="snapshot_bulk/b.jsonl.gz",
                import_batch_id=UUID("00000000-0000-0000-0000-000000000011"),
            ),
            "c.jsonl.gz": BatchRecord(
                filename="c.jsonl.gz",
                state=BatchState.PENDING,
            ),
            "d.jsonl.gz": BatchRecord(
                filename="d.jsonl.gz",
                state=BatchState.FAILED,
                error="upload timeout",
            ),
        },
    )

    new_state = archive_and_reset_state(original, tmp_path)

    # Archive file should exist with original state
    archive_files = list(tmp_path.glob("state.cancelled.*.json"))
    assert len(archive_files) == 1
    archived = json.loads(archive_files[0].read_text(encoding="utf-8"))
    assert archived["import_record_id"] == "00000000-0000-0000-0000-000000000001"
    assert archived["batches"]["b.jsonl.gz"]["state"] == "in_progress"

    # New state: completed preserved, all others reset to PENDING
    assert new_state.import_record_id is None
    assert new_state.total_batches == 4
    assert new_state.started_at is not None

    assert new_state.batches["a.jsonl.gz"].state == BatchState.COMPLETED
    assert new_state.batches["a.jsonl.gz"].blob_name == "snapshot_bulk/a.jsonl.gz"

    for name in ("b.jsonl.gz", "c.jsonl.gz", "d.jsonl.gz"):
        batch = new_state.batches[name]
        assert batch.state == BatchState.PENDING
        assert batch.blob_name is None
        assert batch.import_batch_id is None
        assert batch.error is None

    # state.json on disk should match new state
    on_disk = load_state(tmp_path)
    assert on_disk is not None
    assert on_disk.import_record_id is None
    assert on_disk.batches["a.jsonl.gz"].state == BatchState.COMPLETED
    assert on_disk.batches["b.jsonl.gz"].state == BatchState.PENDING


def test_load_state_with_existing_file(tmp_path) -> None:
    """load_state should correctly parse a state.json written manually."""
    state_data = {
        "version": 1,
        "import_record_id": "00000000-0000-0000-0000-000000000001",
        "total_batches": 1,
        "started_at": "2026-02-23T10:00:00Z",
        "last_poll_at": None,
        "batches": {
            "batch_00001.jsonl.gz": {
                "filename": "batch_00001.jsonl.gz",
                "state": "in_progress",
                "blob_name": "snapshot_bulk/batch_00001.jsonl.gz",
                "import_batch_id": "00000000-0000-0000-0000-000000000010",
                "submitted_at": "2026-02-23T10:01:00Z",
                "completed_at": None,
                "error": None,
            }
        },
    }
    (tmp_path / "state.json").write_text(json.dumps(state_data), encoding="utf-8")
    loaded = load_state(tmp_path)
    assert loaded is not None
    assert loaded.batches["batch_00001.jsonl.gz"].state == BatchState.IN_PROGRESS
