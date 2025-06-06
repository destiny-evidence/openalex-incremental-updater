import asyncio
import re
import time
from io import StringIO

import pytest
from loguru import logger

from openalex_incremental_updater.core.utils import async_timer, sync_timer


def test_sync_timer_decorator() -> None:
    """
    Test the sync_timer decorator.

    This test checks if the sync_timer decorator correctly measures the execution time of a synchronous function.
    """
    wait_time_seconds = 0.1

    @sync_timer
    def sample_function() -> str:
        time.sleep(wait_time_seconds)
        return "Function completed"

    log_stream = StringIO()
    handler_id = logger.add(log_stream, format="{message}")
    result = sample_function()
    logger.remove(handler_id)
    log_contents = log_stream.getvalue()
    match = re.search(r"Elapsed time: ([\d.]+) seconds", log_contents)
    elapsed_time = float(match.group(1)) if match else 999.9

    assert match, "Expected elapsed time log message"
    assert (
        result == "Function completed"
    ), "Expected the function to complete successfully"
    assert (
        pytest.approx(elapsed_time, 0.1) == wait_time_seconds
    ), f"Expected elapsed time {wait_time_seconds}, got {elapsed_time}"


def test_async_timer_decorator() -> None:
    """
    Test the async_timer decorator.

    This test checks if the async_timer decorator correctly measures the execution time of an asynchronous function.
    """
    wait_time_seconds = 0.1

    @async_timer
    async def sample_async_function() -> str:
        await asyncio.sleep(wait_time_seconds)
        return "Async function completed"

    log_stream = StringIO()
    handler_id = logger.add(log_stream, format="{message}")
    result = asyncio.run(sample_async_function())
    logger.remove(handler_id)
    log_contents = log_stream.getvalue()
    match = re.search(r"Elapsed time: ([\d.]+) seconds", log_contents)
    elapsed_time = float(match.group(1)) if match else 999.9

    assert match, "Expected elapsed time log message"
    assert (
        pytest.approx(elapsed_time, 0.1) == wait_time_seconds
    ), f"Expected elapsed time {wait_time_seconds}, got {elapsed_time}"
    assert (
        result == "Async function completed"
    ), "Expected the async function to complete successfully"
