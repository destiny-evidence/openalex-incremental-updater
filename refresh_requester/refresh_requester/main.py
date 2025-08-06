"""Main module for the refresh requester job."""

import os
import socket
import threading
import uuid

from fastapi import FastAPI
from loguru import logger

from refresh_requester.config import get_settings
from refresh_requester.jobs import run_full_pipeline

health_probe_app = FastAPI()


@health_probe_app.get("/health")
async def health_check() -> dict:
    """
    Check the health of the Container App Job.

    Returns:
        dict: A dictionary indicating the health status.

    """
    return {"status": "healthy"}


def start_health_check_server() -> None:
    """Start the health check server."""
    import uvicorn

    uvicorn.run(
        health_probe_app,
        host="0.0.0.0",  # noqa: S104 Possible binding to all interfaces
        port=23045,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        health_check_thread = threading.Thread(
            target=start_health_check_server,
            daemon=True,  # Ensure the thread exits when the main program exits
        )
        health_check_thread.start()
    logger.warning(
        f"[DEBUG] Job started. Host: {socket.gethostname()}, Run ID: {uuid.uuid4()}, PID: {os.getpid()}"
    )

    settings = get_settings()
    run_full_pipeline(settings)
