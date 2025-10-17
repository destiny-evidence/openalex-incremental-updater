"""Redirect Uvicorn logs to Loguru to enable simple logging throughout the app."""

import logging
import sys

from loguru import logger

from openalex_incremental_updater.core.config import (
    DeploymentEnvironment,
    Settings,
    get_settings,
)

loglevel_mapping = {
    50: "CRITICAL",
    40: "ERROR",
    30: "WARNING",
    20: "INFO",
    10: "DEBUG",
    0: "NOTSET",
}


class InterceptHandler(logging.Handler):
    """Intercept standard logging messages and redirect them to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record.

        Args:
            record (logging.LogRecord): The log record to emit

        """
        try:
            level = logger.level(record.levelname).name
        except AttributeError:
            level = loglevel_mapping[record.levelno]
        frame = logging.currentframe()
        depth = 2
        if frame:
            while frame.f_code.co_filename == logging.__file__:
                if frame.f_back is None:
                    break
                frame = frame.f_back
                depth += 1

        log = logger.bind(request_id="app")
        log.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(log_level: str = "DEBUG") -> None:
    """
    Set up logging with Loguru after intercepting Uvicorn logs.

    Args:
        log_level (str, optional): Minimum log level to store. Defaults to "DEBUG".

    """
    settings: Settings = get_settings()

    logger.remove()  # Remove default logger
    if settings.DEPLOYMENT_ENVIRONMENT == DeploymentEnvironment.PRODUCTION:
        # force production log level to at least INFO and serialise.
        logger.add(sys.stdout, level="INFO", serialize=True)
        logger.add(
            sys.stderr, format="{time} {level} {message}", level="INFO", serialize=True
        )
    else:
        logger.add(
            sys.stderr,
            format="{time} {level} {message}",
            level=log_level,
        )

    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    for uvi_logger in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(uvi_logger).handlers = [InterceptHandler()]
        uvicorn_logger = logging.getLogger(uvi_logger)
        uvicorn_logger.handlers = [InterceptHandler()]
        uvicorn_logger.propagate = False
