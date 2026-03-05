"""Define prefect-friendly logging config."""

import logging

from loguru import logger

logger.remove()

logger.add(logging.getLogger("prefect"), format="{message}", level=logging.INFO)
