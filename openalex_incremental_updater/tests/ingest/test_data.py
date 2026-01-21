import json

import pytest
from destiny_sdk.references import ReferenceFileInput
from pytest_mock import MockerFixture

from openalex_incremental_updater.ingest.data import (
    JSONLConversionError,
    convert_destinyworks_to_jsonl_string,
)


def test_convert_destinyworks_to_jsonl_string_valid_json(destiny_work_dict: dict):
    """Test successful conversion of JSON to JSON-line based with valid JSON."""
    destiny_data = [
        ReferenceFileInput.model_validate(destiny_work_dict),
        ReferenceFileInput.model_validate(destiny_work_dict),
    ]
    expected_line_count = 2
    expected_identifier_count = 2
    result = convert_destinyworks_to_jsonl_string(destiny_data)
    # Split the JSONL into lines and parse each
    lines = result.strip().split("\n")
    assert len(lines) == expected_line_count, "Should have 2 lines in the output"
    for line in lines:
        parsed = json.loads(line)
        assert parsed["visibility"] == "public"
        assert len(parsed["identifiers"]) == expected_identifier_count
        assert len(parsed["enhancements"]) == 1


def test_convert_destinyworks_to_jsonl_string_invalid_json():
    """Test failed conversion of invalid JSON to JSON-line based."""
    with pytest.raises(JSONLConversionError) as error:
        convert_destinyworks_to_jsonl_string("invalid_json")
    assert (
        str(error.value) == "destiny_data must be a list of dictionaries - TypeError"
    ), "Should see a type error-related message"


def test_convert_destinyworks_to_jsonl_string_empty_input():
    """Test successful conversion of an empty input to JSON-line based."""
    response = convert_destinyworks_to_jsonl_string([])
    assert response == "", "Empty input should return an empty string"


def test_convert_destinyworks_to_jsonl_string_fails_non_serializable(
    mocker: MockerFixture, destiny_work_dict: dict
):
    """Test failed conversion of un-serializable JSON to JSON-line based."""
    test_data = [
        ReferenceFileInput.model_validate(destiny_work_dict),
    ]
    mocker.patch(
        "pydantic.BaseModel.model_dump_json",
        side_effect=TypeError("Object of type set is not JSON serializable"),
    )
    with pytest.raises(JSONLConversionError) as error:
        convert_destinyworks_to_jsonl_string(test_data)
    assert (
        str(error.value)
        == "Error converting JSON to JSONL: Object of type set is not JSON serializable"
    ), "We should see a non-serializable related error"
