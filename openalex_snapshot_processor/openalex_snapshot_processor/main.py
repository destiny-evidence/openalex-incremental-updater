"""FastAPI application for the Snapshot Bulk Feeder."""

import asyncio
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from loguru import logger

from openalex_snapshot_processor.blob_client import SnapshotBlobClient
from openalex_snapshot_processor.config import Settings, get_settings
from openalex_snapshot_processor.dr_client import DRClient
from openalex_snapshot_processor.feeder import Feeder
from openalex_snapshot_processor.models import (
    TERMINAL_STATES,
    BatchState,
    FailedBatchInfo,
    RuntimeSettings,
    SettingsResponse,
    SettingsUpdate,
    StatusResponse,
)
from openalex_snapshot_processor.state import (
    archive_and_reset_state,
    initialize_state,
    load_manifest,
    load_state,
    save_state,
)

# Module-level references set during lifespan
_feeder: Feeder | None = None
_runtime_settings: RuntimeSettings | None = None


def _configure_logging(level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level)


async def _startup(settings: Settings) -> Feeder:
    """Initialise or resume the feeder and return it ready to run."""
    batch_dir = Path(settings.BATCH_DIR)

    state = load_state(batch_dir)
    if state is None:
        manifest = load_manifest(batch_dir)
        state = initialize_state(manifest)
        logger.info("Initialised fresh state with {} batches", state.total_batches)
    else:
        logger.info("Resumed state with {} batches", state.total_batches)

    blob_client = SnapshotBlobClient(settings)
    dr_client = DRClient(settings)

    # Create or verify ImportRecord
    if state.import_record_id is None:
        record = await asyncio.to_thread(dr_client.create_import_record)
        state.import_record_id = record.id
        save_state(state, batch_dir)
    else:
        await asyncio.to_thread(dr_client.get_import_record, state.import_record_id)
        logger.info("Verified existing ImportRecord {}", state.import_record_id)

    runtime_settings = RuntimeSettings(
        window_size=settings.WINDOW_SIZE,
        poll_interval_seconds=settings.POLL_INTERVAL_SECONDS,
    )

    feeder = Feeder(
        settings=settings,
        runtime_settings=runtime_settings,
        blob_client=blob_client,
        dr_client=dr_client,
        state=state,
        batch_dir=batch_dir,
    )

    # Reconcile in-progress batches after restart
    await feeder.reconcile()

    return feeder


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
    """Start the feeder loop on startup, stop it on shutdown."""
    global _feeder, _runtime_settings  # noqa: PLW0603

    settings = get_settings()
    _configure_logging(settings.LOG_LEVEL)

    feeder = await _startup(settings)
    _feeder = feeder
    _runtime_settings = feeder.runtime_settings

    task = asyncio.create_task(feeder.run())
    yield
    feeder.stop()
    await task

    _feeder = None
    _runtime_settings = None


app = FastAPI(title="Snapshot Bulk Feeder", lifespan=lifespan)


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/status")
async def status() -> StatusResponse:
    """Return current feeder progress and statistics."""
    if _feeder is None:
        raise HTTPException(status_code=503, detail="Feeder not running")

    state = _feeder.state
    rs = _feeder.runtime_settings

    completed = sum(
        1 for b in state.batches.values() if b.state == BatchState.COMPLETED
    )
    failed = sum(1 for b in state.batches.values() if b.state == BatchState.FAILED)
    in_progress = sum(
        1 for b in state.batches.values() if b.state == BatchState.IN_PROGRESS
    )
    pending = sum(
        1
        for b in state.batches.values()
        if b.state in {BatchState.PENDING, BatchState.UPLOADING}
    )

    # Throughput / ETA
    throughput = None
    eta = None
    if state.started_at and completed > 0:
        elapsed_hours = (datetime.now(tz=UTC) - state.started_at).total_seconds() / 3600
        if elapsed_hours > 0:
            throughput = round(completed / elapsed_hours, 1)
            remaining = pending + in_progress
            if throughput > 0:
                hours_left = remaining / throughput
                eta = datetime.now(tz=UTC) + timedelta(hours=hours_left)

    failed_batches = [
        FailedBatchInfo(filename=b.filename, error=b.error)
        for b in state.batches.values()
        if b.state == BatchState.FAILED
    ]

    return StatusResponse(
        import_record_id=state.import_record_id,
        total_batches=state.total_batches,
        completed=completed,
        failed=failed,
        in_progress=in_progress,
        pending=pending,
        window_size=rs.window_size,
        effective_window=_feeder.effective_window,
        poll_interval_seconds=rs.poll_interval_seconds,
        window_utilization=in_progress,
        throughput_batches_per_hour=throughput,
        estimated_completion=eta,
        started_at=state.started_at,
        last_poll_at=state.last_poll_at,
        failed_batches=failed_batches,
        is_paused=_feeder.is_paused,
        is_complete=all(b.state in TERMINAL_STATES for b in state.batches.values()),
    )


@app.patch("/settings")
async def update_settings(body: SettingsUpdate) -> SettingsResponse:
    """Adjust window_size and/or poll_interval_seconds at runtime."""
    if _runtime_settings is None:
        raise HTTPException(status_code=503, detail="Feeder not running")

    if body.window_size is not None:
        _runtime_settings.window_size = body.window_size
        logger.info("window_size updated to {}", body.window_size)
    if body.poll_interval_seconds is not None:
        _runtime_settings.poll_interval_seconds = body.poll_interval_seconds
        logger.info("poll_interval_seconds updated to {}", body.poll_interval_seconds)

    return SettingsResponse(
        window_size=_runtime_settings.window_size,
        poll_interval_seconds=_runtime_settings.poll_interval_seconds,
    )


@app.post("/batches/{filename}/retry")
async def retry_batch(filename: str) -> dict:
    """Reset a failed batch back to pending for retry."""
    if _feeder is None:
        raise HTTPException(status_code=503, detail="Feeder not running")

    batch = _feeder.state.batches.get(filename)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch '{filename}' not found")
    if batch.state != BatchState.FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"Batch '{filename}' is in state '{batch.state}', not 'failed'",
        )

    batch.state = BatchState.PENDING
    batch.error = None
    batch.blob_name = None
    batch.import_batch_id = None
    batch.submitted_at = None
    batch.completed_at = None

    save_state(_feeder.state, _feeder.batch_dir)
    logger.info("Reset batch {} to pending for retry", filename)

    return batch.model_dump(mode="json")


@app.post("/pause")
async def pause() -> dict:
    """Pause the feeder loop — stops submitting new batches and polling."""
    if _feeder is None:
        raise HTTPException(status_code=503, detail="Feeder not running")
    if _feeder.is_paused:
        raise HTTPException(status_code=409, detail="Feeder is already paused")

    _feeder.pause()
    logger.info("Feeder paused by operator")
    return {"status": "paused"}


@app.post("/resume")
async def resume() -> dict:
    """Resume a paused feeder loop."""
    if _feeder is None:
        raise HTTPException(status_code=503, detail="Feeder not running")
    if not _feeder.is_paused:
        raise HTTPException(status_code=409, detail="Feeder is not paused")

    _feeder.resume()
    logger.info("Feeder resumed by operator")
    return {"status": "running"}


@app.delete("/import")
async def delete_import() -> dict:
    """Cancel the import — archive state, reset non-completed batches to PENDING."""
    if _feeder is None:
        raise HTTPException(status_code=503, detail="Feeder not running")

    _feeder.stop()

    # Count before reset
    completed = sum(
        1 for b in _feeder.state.batches.values() if b.state == BatchState.COMPLETED
    )
    cancelled = sum(
        1 for b in _feeder.state.batches.values() if b.state not in TERMINAL_STATES
    )

    new_state = archive_and_reset_state(_feeder.state, _feeder.batch_dir)
    _feeder.state = new_state

    pending = sum(
        1 for b in new_state.batches.values() if b.state == BatchState.PENDING
    )

    logger.info("Import cancelled — {} batches cancelled", cancelled)
    return {"cancelled_batches": cancelled, "completed": completed, "pending": pending}
