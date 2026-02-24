"""Core async feeder loop: sliding-window upload, register, and poll."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from openalex_snapshot_processor.blob_client import BlobUploadError, SnapshotBlobClient
from openalex_snapshot_processor.config import Settings
from openalex_snapshot_processor.dr_client import DRClient
from openalex_snapshot_processor.models import (
    TERMINAL_STATES,
    BatchRecord,
    BatchState,
    FeederState,
    RuntimeSettings,
)
from openalex_snapshot_processor.state import save_state


class Feeder:
    """Manages the sliding-window feed of batch files into destiny-repository."""

    def __init__(  # noqa: PLR0913
        self,
        settings: Settings,
        runtime_settings: RuntimeSettings,
        blob_client: SnapshotBlobClient,
        dr_client: DRClient,
        state: FeederState,
        batch_dir: Path,
    ) -> None:
        """Initialise the feeder with its dependencies and initial state."""
        self._settings = settings
        self.runtime_settings = runtime_settings
        self._blob_client = blob_client
        self._dr_client = dr_client
        self.state = state
        self._batch_dir = batch_dir
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # starts in running (not paused) state

    @property
    def batch_dir(self) -> Path:
        """Return the batch directory path."""
        return self._batch_dir

    @property
    def is_paused(self) -> bool:
        """Return whether the feeder loop is currently paused."""
        return not self._pause_event.is_set()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def stop(self) -> None:
        """Signal the feeder loop to stop after the current cycle."""
        self._stop_event.set()

    def pause(self) -> None:
        """Pause the feeder loop — stops submitting new batches and polling."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume a paused feeder loop."""
        self._pause_event.set()

    async def run(self) -> None:
        """Run the main loop: fill window, sleep, poll -- until done or stopped."""
        logger.info(
            "Feeder starting — {} total batches, {} pending",
            self.state.total_batches,
            self._count(BatchState.PENDING),
        )

        while not self._all_terminal() and not self._stop_event.is_set():
            # If paused, wait for either resume or stop
            if self.is_paused:
                pause_wait = asyncio.ensure_future(self._pause_event.wait())
                stop_wait = asyncio.ensure_future(self._stop_event.wait())
                _done, pending = await asyncio.wait(
                    {pause_wait, stop_wait},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                if self._stop_event.is_set():
                    break
                # Resumed — continue the loop

            await self._fill_window()
            self._persist()

            # Interruptible sleep
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.runtime_settings.poll_interval_seconds,
                )
                break  # stop requested during sleep
            except TimeoutError:
                pass

            await self._poll_batches()
            self._persist()

        if self._all_terminal() and not self._stop_event.is_set():
            await self._finalise()

        logger.info("Feeder loop exited")

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------
    @property
    def effective_window(self) -> int:
        """Current ramp-up limit: min(window_size, completed_count + 1)."""
        completed = self._count(BatchState.COMPLETED)
        return min(self.runtime_settings.window_size, completed + 1)

    async def _fill_window(self) -> None:
        """Submit pending batches respecting ramp-up and per-cycle cap."""
        in_progress = self._count(BatchState.IN_PROGRESS)
        ew = self.effective_window
        slots = ew - in_progress

        if ew < self.runtime_settings.window_size:
            logger.info(
                "Ramp-up active: effective_window={} (configured={})",
                ew,
                self.runtime_settings.window_size,
            )

        if slots <= 0:
            return

        pending = [
            b for b in self.state.batches.values() if b.state == BatchState.PENDING
        ]
        # Layer 2: max 1 submission per poll cycle
        to_submit = pending[: min(slots, 1)]

        for batch in to_submit:
            if self._stop_event.is_set():
                break
            await self._submit_batch(batch)

    async def _submit_batch(self, batch: BatchRecord) -> None:
        """Upload a batch file to blob storage and register it with DR."""
        batch.state = BatchState.UPLOADING
        file_path = self._batch_dir / batch.filename
        blob_name = self._blob_name(batch.filename)

        try:
            # Upload to blob storage
            await asyncio.to_thread(self._blob_client.upload_file, file_path, blob_name)
            batch.blob_name = blob_name

            # Generate SAS URL
            sas_url = await asyncio.to_thread(
                self._blob_client.generate_sas_url, blob_name
            )

            # Register with DR
            import_batch = await asyncio.to_thread(
                self._dr_client.register_batch,
                self.state.import_record_id,
                sas_url,
            )
            batch.import_batch_id = import_batch.id
            batch.state = BatchState.IN_PROGRESS
            batch.submitted_at = datetime.now(tz=UTC)
            logger.info(
                "Submitted {} -> batch {}",
                batch.filename,
                import_batch.id,
            )
        except (BlobUploadError, Exception) as exc:
            batch.state = BatchState.FAILED
            batch.error = str(exc)
            logger.error("Failed to submit {}: {}", batch.filename, exc)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------
    async def _poll_batches(self) -> None:
        """Check DR status for all in-progress batches."""
        in_progress = [
            b for b in self.state.batches.values() if b.state == BatchState.IN_PROGRESS
        ]
        if not in_progress:
            return

        for batch in in_progress:
            await self._poll_single(batch)

        self.state.last_poll_at = datetime.now(tz=UTC)

    async def _poll_single(self, batch: BatchRecord) -> None:
        """Poll a single batch and update its state."""
        try:
            result = await asyncio.to_thread(
                self._dr_client.get_batch_status,
                self.state.import_record_id,
                batch.import_batch_id,
            )
            status = str(result.status).lower()
            if status == "completed":
                batch.state = BatchState.COMPLETED
                batch.completed_at = datetime.now(tz=UTC)
                logger.info("Batch {} completed", batch.filename)
            elif status in {"failed", "partially_failed"}:
                batch.state = BatchState.FAILED
                batch.completed_at = datetime.now(tz=UTC)
                batch.error = f"DR reported batch as {status}"
                logger.warning("Batch {} {} in DR", batch.filename, status)
        except Exception as exc:  # noqa: BLE001
            # Transient poll failure — leave as IN_PROGRESS, retry next cycle
            logger.warning("Poll failed for {} (will retry): {}", batch.filename, exc)

    # ------------------------------------------------------------------
    # Finalisation
    # ------------------------------------------------------------------
    async def _finalise(self) -> None:
        """Finalise the ImportRecord once all batches are terminal."""
        if self.state.import_record_id is None:
            return
        try:
            await asyncio.to_thread(
                self._dr_client.finalise_import_record,
                self.state.import_record_id,
            )
            logger.info("ImportRecord {} finalised", self.state.import_record_id)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to finalise ImportRecord {}: {}",
                self.state.import_record_id,
                exc,
            )

    # ------------------------------------------------------------------
    # Reconciliation (called once at startup for existing state)
    # ------------------------------------------------------------------
    async def reconcile(self) -> None:
        """Re-check DR status for all in-progress batches after a restart."""
        in_progress = [
            b for b in self.state.batches.values() if b.state == BatchState.IN_PROGRESS
        ]
        if not in_progress:
            return

        logger.info(
            "Reconciling {} in-progress batches after restart", len(in_progress)
        )
        for batch in in_progress:
            await self._poll_single(batch)
        self._persist()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _count(self, state: BatchState) -> int:
        return sum(1 for b in self.state.batches.values() if b.state == state)

    def _all_terminal(self) -> bool:
        return all(b.state in TERMINAL_STATES for b in self.state.batches.values())

    def _blob_name(self, filename: str) -> str:
        return f"{self._settings.BLOB_PREFIX}{filename}"

    def _persist(self) -> None:
        save_state(self.state, self._batch_dir)
