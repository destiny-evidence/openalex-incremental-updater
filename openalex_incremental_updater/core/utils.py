"""Define useful utility functions for the OpenAlex Incremental Updater."""

import functools
import time
from typing import Callable

from loguru import logger


def simple_timer(timed_function: Callable) -> Callable:
    """
    Decorate a function to be timed.

    Args:
        timed_function (callable):  The function to time.

    """

    @functools.wraps(timed_function)
    def wrapper_simple_timer(*args: list, **kwargs: dict) -> None:
        start_time = time.perf_counter()
        timed_function(*args, **kwargs)
        end_time = time.perf_counter()
        logger.info(
            f"{timed_function.__name__}: Elapsed time: {(end_time - start_time):.2f} seconds"
        )

    return wrapper_simple_timer
