"""Define data conversion functions."""

import json

from loguru import logger


class JSONLConversionError(Exception):
    """JSONL Conversion Error."""


def convert_json_to_jsonl(json_data: list[dict]) -> str:
    """
    Convert JSON data to JSONL format.

    Args:
        data (dict): The JSON data to convert

    Returns:
        str: The JSONL data

    """
    if not isinstance(json_data, list):
        error_message = "json_data must be a list of dictionaries - TypeError"
        raise JSONLConversionError(error_message)
    try:
        return "\n".join([json.dumps(data) for data in json_data])
    except (TypeError, ValueError) as jsonl_convertsion_error:
        error_message = f"Error converting JSON to JSONL: {jsonl_convertsion_error}"
        logger.error(error_message)
        raise JSONLConversionError(error_message) from jsonl_convertsion_error
