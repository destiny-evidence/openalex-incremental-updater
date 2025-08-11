"""Main module for the refresh requester job."""

import asyncio
import os
import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from loguru import logger

from refresh_requester.config import get_settings
from refresh_requester.jobs import run_full_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Context manager for the lifespan of the FastAPI application.

    Args:
        _app (FastAPI): The FastAPI application instance.

    Returns:
        AsyncIterator[None]: An asynchronous iterator for the lifespan context.

    """
    logger.debug(
        "Job started. Host: {}, Run ID: {}, PID: {}",
        socket.gethostname(),
        uuid.uuid4(),
        os.getpid(),
    )
    settings = get_settings()
    app.state.exit_code = 0

    async def run_and_request_shutdown() -> None:
        """Run the full pipeline and request shutdown."""
        try:
            await asyncio.to_thread(run_full_pipeline, settings)
            logger.success("Job completed.")
        except Exception:  # noqa: BLE001 Ignoring as this is a catch-all for Azure Container App Job failures
            # and we need to ensure the job terminates immediately.
            app.state.exit_code = 1
            logger.exception("Job failed.")
        finally:
            loop = asyncio.get_event_loop()
            loop.stop()

    task = asyncio.create_task(run_and_request_shutdown())

    try:
        yield
    finally:
        try:
            await task
        except Exception:  # noqa: BLE001 # Terminate the App Job if any exception occurs
            app.state.exit_code = 1
        logger.success("Exiting container.")
        os._exit(app.state.exit_code)


app = FastAPI(
    title="Refresh Requester App",
    description="An app containing job to refresh data from OpenAlex and upload it to the repository.",
    version=version("refresh_requester"),
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict:
    """
    Check the health of the Container App Job.

    Returns:
        dict: A dictionary indicating the health status.

    """
    return {"status": "healthy"}
