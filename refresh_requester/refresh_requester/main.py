"""Main module for the refresh requester job."""

import asyncio
import os
import socket
import sys
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from loguru import logger

from refresh_requester.config import get_settings
from refresh_requester.jobs import run_full_pipeline


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
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
    task = asyncio.create_task(asyncio.to_thread(run_full_pipeline, settings))
    try:
        yield
    finally:
        await task
        logger.success("Job completed. Exiting container.")
        sys.exit(0)


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
