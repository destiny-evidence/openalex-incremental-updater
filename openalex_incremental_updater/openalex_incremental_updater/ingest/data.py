"""Define data conversion functions."""

from collections.abc import AsyncIterator

from loguru import logger

from openalex_incremental_updater.models.destiny import DestinyOpenAlexWork


class JSONLConversionError(Exception):
    """JSONL Conversion Error."""


async def convert_destinyworks_to_jsonl_string(
    destiny_data: AsyncIterator[list[DestinyOpenAlexWork]],
) -> AsyncIterator[bytes]:
    """
    Generate JSONL lines from DestinyOpenAlexWork objects.

    Args:
        destiny_data (AsyncIterator[list[DestinyOpenAlexWork]]): The work objects to convert.

    Yields:
        AsyncIterator[bytes]: An iterator of JSONL lines.

    """
    try:
        async for batch in destiny_data:
            if not isinstance(batch, list):
                error_message = "Each batch must be a list of DestinyOpenAlexWork"
                logger.error(error_message)
                raise JSONLConversionError(error_message)
            for work in batch:
                if not isinstance(work, DestinyOpenAlexWork):
                    error_message = "All items must be DestinyOpenAlexWork instances"
                    logger.error(error_message)
                    raise JSONLConversionError(error_message)
                jsonl_line = work.model_dump_json().encode("utf-8") + b"\n"
                yield jsonl_line
    except (TypeError, ValueError, AttributeError) as jsonl_conversion_error:
        error_message = f"Error converting JSON to JSONL: {jsonl_conversion_error}"
        logger.error(error_message)
        raise JSONLConversionError(error_message) from jsonl_conversion_error
