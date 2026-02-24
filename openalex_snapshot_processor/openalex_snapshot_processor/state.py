"""Persist and restore feeder state to/from state.json."""

import contextlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from openalex_snapshot_processor.models import (
    BatchRecord,
    BatchState,
    FeederState,
    Manifest,
)

STATE_FILENAME = "state.json"
MANIFEST_FILENAME = "manifest.json"


def load_manifest(batch_dir: Path) -> Manifest:
    """
    Parse manifest.json from the batch directory.

    Raises:
        FileNotFoundError: If manifest.json does not exist.
        ValueError: If the manifest cannot be parsed.

    """
    manifest_path = batch_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        msg = f"Manifest not found at {manifest_path}"
        raise FileNotFoundError(msg)

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = Manifest.model_validate(data)
    logger.info(
        "Loaded manifest: {} batches, {} total records",
        manifest.totals.batch_files,
        manifest.totals.records_written,
    )
    return manifest


def load_state(batch_dir: Path) -> FeederState | None:
    """Load state.json if it exists, else return None."""
    state_path = batch_dir / STATE_FILENAME
    if not state_path.exists():
        return None

    data = json.loads(state_path.read_text(encoding="utf-8"))
    state = FeederState.model_validate(data)
    logger.info(
        "Loaded state: {} batches ({} completed, {} in-progress, {} failed)",
        state.total_batches,
        sum(1 for b in state.batches.values() if b.state == BatchState.COMPLETED),
        sum(1 for b in state.batches.values() if b.state == BatchState.IN_PROGRESS),
        sum(1 for b in state.batches.values() if b.state == BatchState.FAILED),
    )
    return state


def save_state(state: FeederState, batch_dir: Path) -> None:
    """Atomically write state.json via tempfile + os.replace."""
    state_path = batch_dir / STATE_FILENAME
    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(batch_dir), prefix=".state_", suffix=".tmp"
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(state.model_dump_json(indent=2))
        tmp_path.replace(state_path)
    except BaseException:
        # Clean up temp file on any failure
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def archive_and_reset_state(state: FeederState, batch_dir: Path) -> FeederState:
    """
    Archive current state, then reset non-completed batches to PENDING.

    - Writes current state to ``state.cancelled.<ISO timestamp>.json``
    - Builds a new FeederState preserving completed batches as-is
    - Resets all other batches to a fresh ``BatchRecord(filename=...)``
    - Clears ``import_record_id`` so startup creates a fresh ImportRecord
    - Persists and returns the new state
    """
    # Archive current state
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_name = f"state.cancelled.{timestamp}.json"
    archive_path = batch_dir / archive_name
    archive_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Archived current state to {}", archive_name)

    # Build new state: keep completed, reset everything else
    new_batches = {}
    for filename, batch in state.batches.items():
        if batch.state == BatchState.COMPLETED:
            new_batches[filename] = batch.model_copy()
        else:
            new_batches[filename] = BatchRecord(filename=filename)

    new_state = FeederState(
        total_batches=state.total_batches,
        started_at=datetime.now(tz=UTC),
        batches=new_batches,
    )

    save_state(new_state, batch_dir)
    logger.info(
        "Reset state: {} completed preserved, {} reset to pending",
        sum(1 for b in new_batches.values() if b.state == BatchState.COMPLETED),
        sum(1 for b in new_batches.values() if b.state == BatchState.PENDING),
    )
    return new_state


def initialize_state(manifest: Manifest) -> FeederState:
    """Create a fresh FeederState with all manifest batches set to PENDING."""
    batches = {
        entry.file: BatchRecord(filename=entry.file) for entry in manifest.batches
    }
    return FeederState(
        total_batches=len(batches),
        started_at=datetime.now(tz=UTC),
        batches=batches,
    )
