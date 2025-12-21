"""API Router definitions for the OpenAlex Incremental Updater - version 1."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from openalex_incremental_updater.core.auth import generate_token
from openalex_incremental_updater.core.config import get_settings
from openalex_incremental_updater.core.job_state import JobManager, JobState
from openalex_incremental_updater.core.jobs import (
    run_background_openalex_ingest_job,
)
from openalex_incremental_updater.core.utils import logger
from openalex_incremental_updater.ingest.openalex import (
    CreatedOrUpdated,
)
from openalex_incremental_updater.models.auth import DestinyRepoToken
from openalex_incremental_updater.models.job_response import JobResponse

TASKS: dict[str, asyncio.Task[Any]] = {}
settings = get_settings()

router = APIRouter(prefix=settings.API_V1_STR, tags=["v1"])
job_manager = JobManager()


async def _run_with_tracking_async(job_id: str, coro: Awaitable) -> None:
    """
    Run a coroutine with tracking in the job manager.

    Args:
        job_id (str): The ID of the job to track.
        coro (Awaitable): The coroutine to run.

    """
    job_manager.start(job_id)
    try:
        await coro
        job_manager.succeed(job_id)
    except asyncio.CancelledError:
        logger.warning("Job cancelled with ID: %s", job_id)
        job_manager.cancel(job_id)
    except Exception as generic_exception:  # noqa: BLE001
        logger.error(
            "Job failed with ID: {}. Error message: {}", job_id, generic_exception
        )
        job_manager.fail(job_id, generic_exception)
    finally:
        TASKS.pop(job_id, None)


def report_status(job_manager: JobManager, job_id: str) -> Callable:
    """
    Create a report function for updating the status and progress of a job.

    Args:
        job_manager (JobManager): The job manager instance.
        job_id (str): The ID of the job to report status for.


    """

    def report(**fields: dict) -> None:
        job_manager.set_progress(job_id, **fields)

    return report


@router.get("/openalex_works_ingest_date_range")
async def openalex_ingest_processing(
    start_date: Annotated[
        date,
        Query(description="Date to fetch data from. Must be in ISO format YYYY-MM-DD."),
    ],
    end_date: Annotated[
        date,
        Query(description="Date to fetch data to. Must be in ISO format YYYY-MM-DD."),
    ],
    ingest_type: Annotated[
        CreatedOrUpdated,
        Query(
            description="Method of determining ingest data. Must be one of 'created' or 'updated'."
        ),
    ],
    limit: Annotated[
        int | None, Query(description="Maximum number of records to ingest.")
    ] = None,
) -> JSONResponse:
    """
    Fetch Works from the OpenAlex API with a date range filter and ingest them into the repository.

    Args:
        start_date (date): Start date to fetch data from. Must be in the format YYYY-MM-DD.
        end_date (date): End date to fetch data to. Must be in the format YYYY-MM-DD.
        ingest_type (CreatedOrUpdated): Method of determining ingest data. Must be one of "created" or "updated".
        limit (int): Maximum number of records to ingest.

    Returns:
        list[DestinyOpenAlexWork]: List of DestinyOpenAlexWork objects.

    """
    job_id = job_manager.create(
        meta={
            "start_date": start_date,
            "end_date": end_date,
            "ingest_type": ingest_type,
            "limit": limit,
        }
    )
    report = report_status(job_manager, job_id)
    coroutine = run_background_openalex_ingest_job(
        job_manager, job_id, report, start_date, end_date, ingest_type, limit
    )
    TASKS[job_id] = asyncio.create_task(_run_with_tracking_async(job_id, coroutine))
    response_content = {
        "job_id": job_id,
        "status_url": f"/jobs/{job_id}",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    response_headers = {"Location": f"/jobs/{job_id}", "Retry-After": "3"}
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=response_content,
        headers=response_headers,
    )


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> JSONResponse:
    """
    Get the status of a job.

    Args:
        job_id (str): The ID of the job to retrieve.

    Returns:
        JSONResponse: The status of the job.

    """
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    logger.info(f"{job['status']=}")
    logger.info(f"{job.get('progress')=}")
    logger.info(f"{job.get('result')=}")
    logger.info(f"{job.get('error')=}")
    payload = JobResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress", {}),
        result=job.get("result"),
        error=job.get("error"),
    )
    if job["status"] not in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED, content=payload.model_dump()
        )
    return payload


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str) -> JSONResponse:
    """
    Cancel a job.

    Args:
        job_id (str): The ID of the job to cancel.

    Returns:
        JSONResponse: Response indicating the result of the cancellation.

    """
    task = TASKS.get(job_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Job not found")
    task.cancel()
    return JSONResponse(status_code=204, content={"ok": True})


@router.get("/auth_token")
async def get_auth_token() -> DestinyRepoToken:
    """
    Generate an access token for the OpenAlex API using Azure AD authentication.

    Returns:
        DestinyRepoToken: A model containing the access token and its metadata.

    """
    return generate_token()
