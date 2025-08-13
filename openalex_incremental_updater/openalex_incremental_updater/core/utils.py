"""Define useful utility functions for the OpenAlex Incremental Updater."""

import functools
import time
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from loguru import logger

P = ParamSpec("P")
R = TypeVar("R")


def async_timer(
    timed_function: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    """
    Decorate an async function with timer information and log this.

    Args:
        timed_function (Callable[P, R]): The function to time.

    Returns:
        Callable[P, R]: The wrapped function.

    """

    @functools.wraps(timed_function)
    async def async_timer_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        """
        Wrap the called async function with timer information.

        Returns:
            return_type: The result of the called function.

        """
        start_time = time.perf_counter()
        result = await timed_function(*args, **kwargs)
        end_time = time.perf_counter()
        logger.info(
            f"{timed_function.__name__}: Elapsed time: {(end_time - start_time):.2f} seconds"
        )
        return result

    return async_timer_wrapper


def sync_timer(
    timed_function: Callable[P, R],
) -> Callable[P, R]:
    """
    Decorate a sync function with timer information and log this.

    Args:
        timed_function (Callable[P, R]): The function to time.

    Returns:
        Callable[P, R]: The wrapped function.

    """

    @functools.wraps(timed_function)
    def sync_timer_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        """
        Wrap the called function with timer information.

        Returns:
            return_type: The result of the called function.

        """
        start_time = time.perf_counter()
        result = timed_function(*args, **kwargs)
        end_time = time.perf_counter()
        logger.info(
            f"{timed_function.__name__}: Elapsed time: {(end_time - start_time):.2f} seconds"
        )
        return result

    return sync_timer_wrapper
