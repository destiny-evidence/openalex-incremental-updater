"""Domain models for the Snapshot Bulk Feeder."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Batch state machine
# ---------------------------------------------------------------------------
class BatchState(StrEnum):
    """Lifecycle states for a single batch file."""

    PENDING = "pending"
    UPLOADING = "uploading"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_STATES = frozenset({BatchState.COMPLETED, BatchState.FAILED})


# ---------------------------------------------------------------------------
# Persisted models (state.json)
# ---------------------------------------------------------------------------
class BatchRecord(BaseModel):
    """Tracks the lifecycle of a single batch file."""

    filename: str
    state: BatchState = BatchState.PENDING
    blob_name: str | None = None
    import_batch_id: UUID | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class FeederState(BaseModel):
    """Full feeder state persisted to state.json."""

    version: int = 1
    import_record_id: UUID | None = None
    total_batches: int = 0
    started_at: datetime | None = None
    last_poll_at: datetime | None = None
    batches: dict[str, BatchRecord] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Manifest models (read-only input from openalex-bulk-ingest)
# ---------------------------------------------------------------------------
class ManifestBatch(BaseModel):
    """A single batch entry in the manifest."""

    file: str
    records: int


class ManifestTotals(BaseModel):
    """Aggregate totals from the manifest."""

    records_processed: int
    records_written: int
    records_skipped: int
    records_failed: int
    gz_files_processed: int
    gz_files_corrupted: int
    batch_files: int


class Manifest(BaseModel):
    """The manifest.json produced by openalex-bulk-ingest."""

    created_at: datetime
    duration_seconds: float
    totals: ManifestTotals
    batches: list[ManifestBatch]


# ---------------------------------------------------------------------------
# Runtime-tunable settings (shared mutable object, not persisted)
# ---------------------------------------------------------------------------
class RuntimeSettings:
    """
    Mutable settings adjustable via the /settings API endpoint.

    Reads happen on every feeder loop iteration; writes happen via PATCH.
    Since both run on the same asyncio event loop there is no race condition.
    """

    def __init__(self, window_size: int, poll_interval_seconds: int) -> None:
        """Initialise with the given window size and poll interval."""
        self.window_size = window_size
        self.poll_interval_seconds = poll_interval_seconds


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------
class SettingsUpdate(BaseModel):
    """Request body for PATCH /settings."""

    window_size: int | None = Field(None, ge=1)
    poll_interval_seconds: int | None = Field(None, ge=10)


class SettingsResponse(BaseModel):
    """Response body for PATCH /settings."""

    window_size: int
    poll_interval_seconds: int


class FailedBatchInfo(BaseModel):
    """Summary of a failed batch for the /status response."""

    filename: str
    error: str | None


class StatusResponse(BaseModel):
    """Response body for GET /status."""

    import_record_id: UUID | None
    total_batches: int
    completed: int
    failed: int
    in_progress: int
    pending: int
    window_size: int
    effective_window: int
    poll_interval_seconds: int
    window_utilization: int
    throughput_batches_per_hour: float | None
    estimated_completion: datetime | None
    started_at: datetime | None
    last_poll_at: datetime | None
    failed_batches: list[FailedBatchInfo]
    is_paused: bool
    is_complete: bool
