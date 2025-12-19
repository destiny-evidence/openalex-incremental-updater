"""Define data conversion functions."""

from collections.abc import Iterator

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
    try:
        for data in destiny_data:
            yield (data.model_dump_json() + "\n").encode("utf-8")
    except (TypeError, ValueError) as jsonl_conversion_error:
        error_message = f"Error converting JSON to JSONL: {jsonl_conversion_error}"
        logger.error(error_message)
        raise JSONLConversionError(error_message) from jsonl_conversion_error
