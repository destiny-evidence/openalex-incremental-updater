"""Define data conversion functions."""

from destiny_sdk.references import ReferenceFileInput
from loguru import logger


class JSONLConversionError(Exception):
    """JSONL Conversion Error."""


def convert_destinyworks_to_jsonl_string(
    destiny_data: list[ReferenceFileInput],
) -> str:
    """
    Convert a ReferenceFileInput object to JSONL format.

    Args:
        destiny_data (list[ReferenceFileInput]): The list of work objects to convert.

    Returns:
        str: The JSONL representation of the work objects.

    """
    if not isinstance(destiny_data, list):
        error_message = "destiny_data must be a list of dictionaries - TypeError"
        raise JSONLConversionError(error_message)
    try:
        return "\n".join([data.model_dump_json() for data in destiny_data])
    except (TypeError, ValueError) as jsonl_conversion_error:
        error_message = f"Error converting JSON to JSONL: {jsonl_conversion_error}"
        logger.error(error_message)
        raise JSONLConversionError(error_message) from jsonl_conversion_error
