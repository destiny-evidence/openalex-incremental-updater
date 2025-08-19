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

from refresh_requester.config import Settings, get_settings
from refresh_requester.jobs import run_full_pipeline


async def run_and_request_shutdown(app: FastAPI, settings: Settings) -> None:
    """
    Run the full pipeline and request shutdown.

    Args:
        settings (Settings): The settings to use for the pipeline.

    """
    try:
        await asyncio.to_thread(run_full_pipeline, settings)
        logger.success("Job completed.")
    except Exception as error:  # noqa: BLE001 Ignoring as this is a catch-all for Azure Container App Job failures
        # and we need to ensure the job terminates immediately.
        app.state.exit_code = 1
        error_message = f"An error occurred: {error}"
        logger.error(error_message)
    finally:
        loop = asyncio.get_running_loop()
        loop.stop()


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

    task = asyncio.create_task(run_and_request_shutdown(app, settings))

    try:
        yield
    finally:
        try:
            await task
        except Exception as error:  # noqa: BLE001 # Terminate the App Job if any exception occurs
            app.state.exit_code = 1
            error_message = f"An error occurred: {error}"
            logger.error(error_message)
            os._exit(app.state.exit_code)
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
