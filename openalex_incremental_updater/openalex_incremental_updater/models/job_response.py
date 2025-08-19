"""Define job response model."""

from pydantic import BaseModel

from openalex_incremental_updater.core.job_state import JobState


class JobResponse(BaseModel):
    """Job response model for tracking job status and results."""

    job_id: str
    status: JobState
    progress: dict = {}
    result: str | None = None
    error: str | None = None
