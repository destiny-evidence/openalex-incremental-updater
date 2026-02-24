"""Tests for models.py."""

from uuid import UUID

from openalex_snapshot_processor.models import (
    TERMINAL_STATES,
    BatchRecord,
    BatchState,
    FeederState,
    RuntimeSettings,
    SettingsUpdate,
    StatusResponse,
)


def test_batch_state_values() -> None:
    """BatchState enum members should have the expected string values."""
    assert BatchState.PENDING == "pending"
    assert BatchState.IN_PROGRESS == "in_progress"
    assert BatchState.COMPLETED == "completed"
    assert BatchState.FAILED == "failed"


def test_terminal_states() -> None:
    """TERMINAL_STATES should contain only completed and failed."""
    assert {BatchState.COMPLETED, BatchState.FAILED} == TERMINAL_STATES


def test_batch_record_defaults() -> None:
    """BatchRecord should default to PENDING with no IDs."""
    record = BatchRecord(filename="batch_00001.jsonl.gz")
    assert record.state == BatchState.PENDING
    assert record.blob_name is None
    assert record.import_batch_id is None
    assert record.error is None


def test_feeder_state_round_trip() -> None:
    """FeederState should serialise and deserialise via JSON."""
    state = FeederState(
        import_record_id=UUID("00000000-0000-0000-0000-000000000001"),
        total_batches=2,
        batches={
            "a.jsonl.gz": BatchRecord(filename="a.jsonl.gz"),
            "b.jsonl.gz": BatchRecord(
                filename="b.jsonl.gz",
                state=BatchState.COMPLETED,
            ),
        },
    )
    json_str = state.model_dump_json()
    restored = FeederState.model_validate_json(json_str)
    assert restored.import_record_id == state.import_record_id
    assert restored.batches["b.jsonl.gz"].state == BatchState.COMPLETED


def test_manifest_parsing(sample_manifest) -> None:
    """Manifest fixture should parse with correct batch count."""
    assert len(sample_manifest.batches) == 3
    assert sample_manifest.totals.batch_files == 3
    assert sample_manifest.batches[0].file == "batch_00001.jsonl.gz"


def test_runtime_settings_mutable() -> None:
    """RuntimeSettings should allow direct mutation."""
    rs = RuntimeSettings(window_size=10, poll_interval_seconds=300)
    rs.window_size = 20
    rs.poll_interval_seconds = 60
    assert rs.window_size == 20
    assert rs.poll_interval_seconds == 60


def test_settings_update_validation() -> None:
    """SettingsUpdate should reject invalid values."""
    update = SettingsUpdate(window_size=5, poll_interval_seconds=30)
    assert update.window_size == 5

    # Both fields are optional
    update_partial = SettingsUpdate(window_size=3)
    assert update_partial.poll_interval_seconds is None


def test_status_response_construction() -> None:
    """StatusResponse should accept all fields."""
    resp = StatusResponse(
        import_record_id=None,
        total_batches=100,
        completed=50,
        failed=2,
        in_progress=5,
        pending=43,
        window_size=10,
        effective_window=8,
        poll_interval_seconds=300,
        window_utilization=5,
        throughput_batches_per_hour=12.5,
        estimated_completion=None,
        started_at=None,
        last_poll_at=None,
        failed_batches=[],
        is_paused=False,
        is_complete=False,
    )
    assert resp.total_batches == 100
    assert resp.is_complete is False
