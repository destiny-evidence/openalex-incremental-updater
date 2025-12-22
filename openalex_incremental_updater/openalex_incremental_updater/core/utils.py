"""Define useful utility functions for the OpenAlex Incremental Updater."""

import functools
import inspect
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import ParamSpec, TypeVar, cast, overload

from loguru import logger

P = ParamSpec("P")
R = TypeVar("R")


T = TypeVar("T")


@overload
def async_timer(
    timed_function: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]: ...


@overload
def async_timer(
    timed_function: Callable[P, AsyncIterator[T]],
) -> Callable[P, AsyncIterator[T]]: ...


def async_timer(
    timed_function: Callable[P, Awaitable[R]] | Callable[P, AsyncIterator[T]],
) -> Callable[P, Awaitable[R]] | Callable[P, AsyncIterator[T]]:
    """Decorate an async function or async generator with timer information and log this."""
    if inspect.isasyncgenfunction(timed_function):

        @functools.wraps(timed_function)
        async def async_gen_timer_wrapper(
            *args: P.args, **kwargs: P.kwargs
        ) -> AsyncIterator[T]:
            start_time: float | None = time.perf_counter()
            async for item in timed_function(*args, **kwargs):
                if start_time is not None:
                    end_time = time.perf_counter()
                    logger.info(
                        f"{timed_function.__name__}: Elapsed time to first yield: {(end_time - start_time):.2f} seconds"
                    )
                    start_time = None
                yield item

        return cast(Callable[P, AsyncIterator[T]], async_gen_timer_wrapper)

    @functools.wraps(timed_function)
    async def async_timer_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start_time = time.perf_counter()
        awaitable_func = cast(Callable[P, Awaitable[R]], timed_function)
        result = await awaitable_func(*args, **kwargs)
        end_time = time.perf_counter()
        logger.info(
            f"{timed_function.__name__}: Elapsed time: {(end_time - start_time):.2f} seconds"
        )
        return result

    return cast(Callable[P, Awaitable[R]], async_timer_wrapper)


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
