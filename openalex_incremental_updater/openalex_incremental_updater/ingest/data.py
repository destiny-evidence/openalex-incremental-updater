"""Define data conversion functions."""

import itertools
from collections.abc import Iterable, Iterator

from loguru import logger

from openalex_incremental_updater.models.destiny import DestinyOpenAlexWork


class JSONLConversionError(Exception):
    """JSONL Conversion Error."""


def convert_destinyworks_to_jsonl_string(
    destiny_data: Iterator[DestinyOpenAlexWork],
) -> Iterator[bytes]:
    """
    Generate JSONL lines from DestinyOpenAlexWork objects.

    Args:
        destiny_data (Iterator[DestinyOpenAlexWork]): The work objects to convert.

    Yields:
        Iterator[bytes]: An iterator of JSONL lines.

    """
    if not isinstance(destiny_data, Iterable) or isinstance(destiny_data, (str)):
        error_message = "destiny_data must be an iterable of DestinyOpenAlexWork"
        logger.error(error_message)
        raise JSONLConversionError(error_message)
    destiny_data, validation_iter = itertools.tee(destiny_data)
    if any(not isinstance(item, DestinyOpenAlexWork) for item in validation_iter):
        error_message = "destiny_data must be an iterable of DestinyOpenAlexWork"
        logger.error(error_message)
        raise JSONLConversionError(error_message)
    try:
        for data in destiny_data:
            yield (data.model_dump_json() + "\n").encode("utf-8")
    except (TypeError, ValueError, AttributeError) as jsonl_conversion_error:
        error_message = f"Error converting JSON to JSONL: {jsonl_conversion_error}"
        logger.error(error_message)
        raise JSONLConversionError(error_message) from jsonl_conversion_error
