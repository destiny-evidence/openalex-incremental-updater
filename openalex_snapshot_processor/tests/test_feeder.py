"""Tests for feeder.py."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from openalex_snapshot_processor.models import (
    BatchRecord,
    BatchState,
    FeederState,
    RuntimeSettings,
)


def _make_settings():
    """Return a minimal mock Settings for Feeder construction."""
    s = MagicMock()
    s.BATCH_DIR = "/fake/batches"
    s.BLOB_PREFIX = "snapshot_bulk/"
    return s


def _make_feeder(state, runtime_settings=None, blob_client=None, dr_client=None):
    """Construct a Feeder with mocked dependencies."""
    from openalex_snapshot_processor.feeder import Feeder

    return Feeder(
        settings=_make_settings(),
        runtime_settings=runtime_settings
        or RuntimeSettings(window_size=2, poll_interval_seconds=1),
        blob_client=blob_client or MagicMock(),
        dr_client=dr_client or MagicMock(),
        state=state,
        batch_dir=MagicMock(),
    )


def _make_state(batch_configs):
    """Build a FeederState from a list of (filename, state) tuples."""
    batches = {}
    for filename, bs in batch_configs:
        rec = BatchRecord(filename=filename, state=bs)
        if bs == BatchState.IN_PROGRESS:
            rec.import_batch_id = UUID("00000000-0000-0000-0000-000000000099")
            rec.submitted_at = datetime.now(tz=UTC)
        batches[filename] = rec
    return FeederState(
        import_record_id=UUID("00000000-0000-0000-0000-000000000001"),
        total_batches=len(batches),
        started_at=datetime.now(tz=UTC),
        batches=batches,
    )


@pytest.mark.asyncio
async def test_fill_window_submits_pending() -> None:
    """_fill_window submits only 1 batch per cycle due to per-cycle cap."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.PENDING),
            ("b.jsonl.gz", BatchState.PENDING),
            ("c.jsonl.gz", BatchState.PENDING),
        ]
    )

    mock_blob = MagicMock()
    mock_dr = MagicMock()
    mock_dr.register_batch.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000010")
    )

    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=2, poll_interval_seconds=1),
        blob_client=mock_blob,
        dr_client=mock_dr,
    )

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._fill_window()

    # Per-cycle cap: only 1 submitted (ramp-up also limits to 1 with 0 completed)
    in_progress = [
        b for b in state.batches.values() if b.state == BatchState.IN_PROGRESS
    ]
    assert len(in_progress) == 1


@pytest.mark.asyncio
async def test_fill_window_respects_existing_in_progress() -> None:
    """_fill_window blocked: 0 completed + 1 in-progress fills effective_window=1."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.IN_PROGRESS),
            ("b.jsonl.gz", BatchState.PENDING),
            ("c.jsonl.gz", BatchState.PENDING),
        ]
    )

    mock_dr = MagicMock()
    mock_dr.register_batch.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000010")
    )

    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=2, poll_interval_seconds=1),
        blob_client=MagicMock(),
        dr_client=mock_dr,
    )

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._fill_window()

    # 0 completed → effective_window=1, already 1 in-progress → no slots
    in_progress = [
        b for b in state.batches.values() if b.state == BatchState.IN_PROGRESS
    ]
    assert len(in_progress) == 1


@pytest.mark.asyncio
async def test_fill_window_ramp_up_zero_completed() -> None:
    """Cold start: 0 completed → effective_window=1, only 1 batch submitted."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.PENDING),
            ("b.jsonl.gz", BatchState.PENDING),
            ("c.jsonl.gz", BatchState.PENDING),
        ]
    )

    mock_dr = MagicMock()
    mock_dr.register_batch.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000010")
    )

    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=5, poll_interval_seconds=1),
        blob_client=MagicMock(),
        dr_client=mock_dr,
    )

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._fill_window()

    in_progress = [
        b for b in state.batches.values() if b.state == BatchState.IN_PROGRESS
    ]
    assert len(in_progress) == 1


@pytest.mark.asyncio
async def test_fill_window_ramp_up_with_completions() -> None:
    """2 completed → effective_window=3, but per-cycle cap still limits to 1."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.COMPLETED),
            ("b.jsonl.gz", BatchState.COMPLETED),
            ("c.jsonl.gz", BatchState.PENDING),
            ("d.jsonl.gz", BatchState.PENDING),
            ("e.jsonl.gz", BatchState.PENDING),
        ]
    )

    mock_dr = MagicMock()
    mock_dr.register_batch.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000010")
    )

    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=5, poll_interval_seconds=1),
        blob_client=MagicMock(),
        dr_client=mock_dr,
    )

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._fill_window()

    in_progress = [
        b for b in state.batches.values() if b.state == BatchState.IN_PROGRESS
    ]
    assert len(in_progress) == 1


@pytest.mark.asyncio
async def test_fill_window_ramp_up_saturated() -> None:
    """Completed >= window_size-1 → effective_window equals window_size."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.COMPLETED),
            ("b.jsonl.gz", BatchState.COMPLETED),
            ("c.jsonl.gz", BatchState.COMPLETED),
            ("d.jsonl.gz", BatchState.PENDING),
            ("e.jsonl.gz", BatchState.PENDING),
        ]
    )

    mock_dr = MagicMock()
    mock_dr.register_batch.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000010")
    )

    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=3, poll_interval_seconds=1),
        blob_client=MagicMock(),
        dr_client=mock_dr,
    )

    assert feeder.effective_window == 3  # saturated: min(3, 3+1) = 3

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._fill_window()

    # Per-cycle cap still limits to 1
    in_progress = [
        b for b in state.batches.values() if b.state == BatchState.IN_PROGRESS
    ]
    assert len(in_progress) == 1


@pytest.mark.asyncio
async def test_fill_window_no_slot_when_window_full_from_ramp() -> None:
    """0 completed + 1 in-progress → effective_window=1, no slots."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.IN_PROGRESS),
            ("b.jsonl.gz", BatchState.PENDING),
        ]
    )

    mock_dr = MagicMock()
    mock_dr.register_batch.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000010")
    )

    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=5, poll_interval_seconds=1),
        blob_client=MagicMock(),
        dr_client=mock_dr,
    )

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._fill_window()

    # No new submissions — the 1 in-progress fills effective_window=1
    in_progress = [
        b for b in state.batches.values() if b.state == BatchState.IN_PROGRESS
    ]
    assert len(in_progress) == 1
    assert state.batches["b.jsonl.gz"].state == BatchState.PENDING


@pytest.mark.asyncio
async def test_fill_window_per_cycle_cap() -> None:
    """Many slots open but per-cycle cap limits to 1 submission."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.COMPLETED),
            ("b.jsonl.gz", BatchState.COMPLETED),
            ("c.jsonl.gz", BatchState.COMPLETED),
            ("d.jsonl.gz", BatchState.PENDING),
            ("e.jsonl.gz", BatchState.PENDING),
            ("f.jsonl.gz", BatchState.PENDING),
        ]
    )

    mock_dr = MagicMock()
    mock_dr.register_batch.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000010")
    )

    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=4, poll_interval_seconds=1),
        blob_client=MagicMock(),
        dr_client=mock_dr,
    )

    # effective_window=4, 0 in-progress → 4 slots, but per-cycle cap = 1
    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._fill_window()

    in_progress = [
        b for b in state.batches.values() if b.state == BatchState.IN_PROGRESS
    ]
    assert len(in_progress) == 1


def test_effective_window_property() -> None:
    """effective_window should reflect completed count + 1."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.COMPLETED),
            ("b.jsonl.gz", BatchState.COMPLETED),
            ("c.jsonl.gz", BatchState.PENDING),
        ]
    )
    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=5, poll_interval_seconds=1),
    )
    assert feeder.effective_window == 3  # min(5, 2+1) = 3


def test_effective_window_capped_at_window_size() -> None:
    """effective_window should never exceed window_size."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.COMPLETED),
            ("b.jsonl.gz", BatchState.COMPLETED),
            ("c.jsonl.gz", BatchState.COMPLETED),
            ("d.jsonl.gz", BatchState.COMPLETED),
            ("e.jsonl.gz", BatchState.PENDING),
        ]
    )
    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=3, poll_interval_seconds=1),
    )
    # 4 completed + 1 = 5, but capped at window_size=3
    assert feeder.effective_window == 3


@pytest.mark.asyncio
async def test_submit_batch_failure_marks_failed() -> None:
    """_submit_batch should mark a batch as FAILED on exception."""
    state = _make_state([("a.jsonl.gz", BatchState.PENDING)])

    mock_blob = MagicMock()
    mock_blob.upload_file.side_effect = Exception("upload failed")

    feeder = _make_feeder(state, blob_client=mock_blob)

    batch = state.batches["a.jsonl.gz"]
    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._submit_batch(batch)

    assert batch.state == BatchState.FAILED
    assert "upload failed" in batch.error


@pytest.mark.asyncio
async def test_poll_batches_completes() -> None:
    """_poll_batches should transition IN_PROGRESS → COMPLETED when DR says so."""
    state = _make_state([("a.jsonl.gz", BatchState.IN_PROGRESS)])

    mock_dr = MagicMock()
    mock_dr.get_batch_status.return_value = MagicMock(status="completed")

    feeder = _make_feeder(state, dr_client=mock_dr)

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._poll_batches()

    assert state.batches["a.jsonl.gz"].state == BatchState.COMPLETED


@pytest.mark.asyncio
async def test_poll_batches_marks_failed() -> None:
    """_poll_batches should transition IN_PROGRESS → FAILED when DR reports failure."""
    state = _make_state([("a.jsonl.gz", BatchState.IN_PROGRESS)])

    mock_dr = MagicMock()
    mock_dr.get_batch_status.return_value = MagicMock(status="failed")

    feeder = _make_feeder(state, dr_client=mock_dr)

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._poll_batches()

    assert state.batches["a.jsonl.gz"].state == BatchState.FAILED


@pytest.mark.asyncio
async def test_poll_batches_marks_partially_failed() -> None:
    """_poll_batches should treat partially_failed as FAILED."""
    state = _make_state([("a.jsonl.gz", BatchState.IN_PROGRESS)])

    mock_dr = MagicMock()
    mock_dr.get_batch_status.return_value = MagicMock(status="partially_failed")

    feeder = _make_feeder(state, dr_client=mock_dr)

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._poll_batches()

    assert state.batches["a.jsonl.gz"].state == BatchState.FAILED
    assert "partially_failed" in state.batches["a.jsonl.gz"].error


@pytest.mark.asyncio
async def test_poll_transient_failure_keeps_in_progress() -> None:
    """_poll_batches should leave batch as IN_PROGRESS on transient poll errors."""
    state = _make_state([("a.jsonl.gz", BatchState.IN_PROGRESS)])

    mock_dr = MagicMock()
    mock_dr.get_batch_status.side_effect = Exception("network error")

    feeder = _make_feeder(state, dr_client=mock_dr)

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder._poll_batches()

    assert state.batches["a.jsonl.gz"].state == BatchState.IN_PROGRESS


@pytest.mark.asyncio
async def test_run_loop_completes_and_finalises() -> None:
    """run() should loop until all batches are terminal, then finalise."""
    state = _make_state([("a.jsonl.gz", BatchState.PENDING)])

    mock_blob = MagicMock()
    mock_dr = MagicMock()
    mock_dr.register_batch.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000010")
    )
    # First poll: still pending, second poll: completed
    mock_dr.get_batch_status.return_value = MagicMock(status="completed")

    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=5, poll_interval_seconds=0),
        blob_client=mock_blob,
        dr_client=mock_dr,
    )

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder.run()

    # Should have finalised
    mock_dr.finalise_import_record.assert_called_once()
    assert state.batches["a.jsonl.gz"].state == BatchState.COMPLETED


@pytest.mark.asyncio
async def test_stop_interrupts_loop() -> None:
    """Calling stop() should break the feeder loop gracefully."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.PENDING),
            ("b.jsonl.gz", BatchState.PENDING),
        ]
    )

    mock_dr = MagicMock()
    mock_dr.register_batch.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000010")
    )
    mock_dr.get_batch_status.return_value = MagicMock(status="processing")

    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=5, poll_interval_seconds=1),
        blob_client=MagicMock(),
        dr_client=mock_dr,
    )

    with patch("openalex_snapshot_processor.feeder.save_state"):
        # Stop after a short delay
        async def stop_soon():
            await asyncio.sleep(0.1)
            feeder.stop()

        stop_task = asyncio.create_task(stop_soon())
        await feeder.run()
        await stop_task

    # Should not have finalised because not all batches are terminal
    mock_dr.finalise_import_record.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_updates_in_progress_batches() -> None:
    """reconcile() should re-check DR status for in-progress batches."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.IN_PROGRESS),
            ("b.jsonl.gz", BatchState.PENDING),
        ]
    )

    mock_dr = MagicMock()
    mock_dr.get_batch_status.return_value = MagicMock(status="completed")

    feeder = _make_feeder(state, dr_client=mock_dr)

    with patch("openalex_snapshot_processor.feeder.save_state"):
        await feeder.reconcile()

    assert state.batches["a.jsonl.gz"].state == BatchState.COMPLETED
    # Pending batch should not have been touched
    assert state.batches["b.jsonl.gz"].state == BatchState.PENDING


def test_pause_resume_property() -> None:
    """is_paused should reflect state after pause() / resume()."""
    state = _make_state([("a.jsonl.gz", BatchState.PENDING)])
    feeder = _make_feeder(state)

    assert feeder.is_paused is False

    feeder.pause()
    assert feeder.is_paused is True

    feeder.resume()
    assert feeder.is_paused is False


@pytest.mark.asyncio
async def test_pause_blocks_fill_window() -> None:
    """A paused feeder should not submit batches until resumed."""
    state = _make_state(
        [
            ("a.jsonl.gz", BatchState.PENDING),
            ("b.jsonl.gz", BatchState.PENDING),
        ]
    )

    mock_blob = MagicMock()
    mock_dr = MagicMock()
    mock_dr.register_batch.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000010"),
    )
    # DR says completed so the loop can finish after resume
    mock_dr.get_batch_status.return_value = MagicMock(status="completed")

    feeder = _make_feeder(
        state,
        runtime_settings=RuntimeSettings(window_size=5, poll_interval_seconds=0),
        blob_client=mock_blob,
        dr_client=mock_dr,
    )

    feeder.pause()

    with patch("openalex_snapshot_processor.feeder.save_state"):
        # Resume after a short delay so the loop can proceed
        async def resume_soon():
            await asyncio.sleep(0.1)
            # While paused, no batches should have been submitted
            pending = [
                b for b in state.batches.values() if b.state == BatchState.PENDING
            ]
            assert len(pending) == 2, "Batches were submitted while paused"
            feeder.resume()

        resume_task = asyncio.create_task(resume_soon())
        await feeder.run()
        await resume_task

    # After resume, batches should have been processed
    completed = [b for b in state.batches.values() if b.state == BatchState.COMPLETED]
    assert len(completed) == 2
