"""
Define prefect-friendly logging config.

Config taken from Prefect docs at:
https://linen.prefect.io/t/26413254/does-anyone-have-a-guide-on-how-to-integrate-loguru-with-pre

"""

import functools
from collections.abc import Callable
from contextlib import suppress

from loguru import logger
from prefect import get_run_logger

handler_ids: list[int] = []


def configure_logger() -> None:
    """Configure the prefect logger to receive logs from loguru."""
    try:
        run_logger = get_run_logger()
    except Exception:  # noqa: BLE001
        return

    for handler_id in handler_ids:
        with suppress(ValueError):
            logger.remove(handler_id)

    log_format = "{message}"

    handler_ids.append(
        logger.add(
            run_logger.debug,
            filter=lambda record: record["level"].name == "DEBUG",
            level="TRACE",
            format=log_format,
        )
    )


def forward_logs(func: Callable) -> object:
    """
    Forward logs from loguru to the prefect logger.

    This is a decorator that can be applied to any prefect task or flow function.

    Args:
        func (Callable): The function to decorate.

    Returns:
        object: The decorated function with log forwarding enabled.

    """

    @functools.wraps(func)
    def wrapper(*args: tuple, **kwargs: dict) -> object:
        """
        Wrap a function to forward logs from loguru to the prefect logger.

        Returns:
            object: The decorated function with log forwarding enabled.

        """
        configure_logger()
        return func(*args, **kwargs)

    return wrapper
