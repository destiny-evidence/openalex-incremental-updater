import pytest

from refresh_requester.data import JSONLConversionError, convert_json_to_jsonl


def test_convert_json_to_jsonl_valid_json():
    """Test successful conversion of JSON to JSON-line based with valid JSON."""
    json_data = [
        {"key1": "value1", "key2": "value2"},
        {"key3": "value3", "key4": "value4"},
    ]
    expected_jsonl = (
        '{"key1": "value1", "key2": "value2"}\n{"key3": "value3", "key4": "value4"}'
    )
    assert (
        convert_json_to_jsonl(json_data) == expected_jsonl
    ), "The expected conversion should be returned."


def test_convert_json_to_jsonl_invalid_json():
    """Test failed conversion of invalid JSON to JSON-line based."""
    with pytest.raises(JSONLConversionError) as error:
        convert_json_to_jsonl("invalid_json")
    assert (
        str(error.value) == "json_data must be a list of dictionaries - TypeError"
    ), "Should see a type error-related message"


def test_convert_json_to_jsonl_empty_input():
    """Test successful conversion of an empty input to JSON-line based."""
    response = convert_json_to_jsonl([])
    assert response == "", "Empty input should return an empty string"


def test_convert_json_to_jsonl_fails_non_serializable():
    """Test failed conversion of un-serializable JSON to JSON-line based."""
    json_data = [
        {"key1": "value1", "key2": "value2"},
        {"key3": "value3", "key4": "value4"},
        {"key5": set()},
    ]
    with pytest.raises(JSONLConversionError) as error:
        convert_json_to_jsonl(json_data)
    assert (
        str(error.value)
        == "Error converting JSON to JSONL: Object of type set is not JSON serializable"
    ), "We should see a non-serializable related error"
