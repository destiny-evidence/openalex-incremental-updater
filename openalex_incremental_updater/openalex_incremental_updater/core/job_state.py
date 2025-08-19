"""Tools to track the state of jobs."""

import time
import traceback
import uuid
from enum import StrEnum
from typing import Any


class JobState(StrEnum):
    """
    Enumeration of job states.

    Args:
        StrEnum: Description of the job states.

    """

    PENDING = "pending"
    RUNNING = "running"
    DOWNLOADED = "downloaded"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobManager:
    """Manage background jobs for the application."""

    def __init__(self) -> None:
        """Class constructor."""
        self._jobs: dict[str, dict[str, Any]] = {}

    def create(self, meta: dict[str, Any] | None = None) -> str:
        """
        Create a new job.

        Args:
            meta (dict[str, Any] | None, optional): Metadata to associate with the job. Defaults to None.

        Returns:
            str: The ID of the created job.

        """
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = {
            "status": JobState.PENDING,
            "created_at": time.time(),
            "started_at": None,
            "finished_at": None,
            "progress": {},
            "error": None,
            "traceback": None,
            "meta": meta or {},
            "cancel_requested": False,
        }
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        """
        Get the details of a job.

        Args:
            job_id (str): The ID of the job to retrieve.

        Returns:
            dict[str, Any] | None: The job details or None if not found.

        """
        return self._jobs.get(job_id)

    def start(self, job_id: str) -> None:
        """

        Mark a job as started.

        Starts a timer and sets status to running.

        Args:
            job_id (str): The ID of the job to start.

        """
        job = self._jobs[job_id]
        job["status"] = JobState.RUNNING
        job["started_at"] = time.time()

    def succeed(self, job_id: str, **extra: str) -> None:
        """
        Mark a job as succeeded.

        Args:
            job_id (str): The ID of the job to mark as succeeded.
            extra (str): Additional information to store with the job.

        """
        job = self._jobs[job_id]
        job.update(status=JobState.SUCCEEDED, finished_at=time.time(), **extra)

    def cancel(self, job_id: str) -> None:
        """
        Cancel a job.

        Args:
            job_id (str): The ID of the job to cancel.

        """
        job = self._jobs[job_id]
        job.update(status=JobState.CANCELLED, finished_at=time.time())

    def fail(self, job_id: str, exc: BaseException) -> None:
        """
        Mark a job as failed.

        Args:
            job_id (str): The ID of the job to mark as failed.
            exc (BaseException): The exception that caused the job to fail.

        """
        job = self._jobs[job_id]
        job["status"] = JobState.FAILED
        job["finished_at"] = time.time()
        job["error"] = f"{type(exc).__name__}: {exc}"
        job["traceback"] = traceback.format_exc()

    def set_progress(self, job_id: str, **fields: str) -> None:
        """
        Update the progress of a job.

        Args:
            job_id (str): The ID of the job to update.
            fields (str): Key-value pairs representing progress updates.

        """
        self._jobs[job_id]["progress"].update(**fields)
