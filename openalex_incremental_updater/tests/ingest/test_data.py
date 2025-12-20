import pytest
from pytest_mock import MockerFixture

from openalex_incremental_updater.ingest.data import (
    JSONLConversionError,
    convert_destinyworks_to_jsonl_string,
)
from openalex_incremental_updater.models.destiny import DestinyOpenAlexWork


def test_convert_destinyworks_to_jsonl_string_valid_json(destiny_work_dict: dict):
    """Test successful conversion of JSON to JSON-line based with valid JSON."""
    destiny_data = [
        DestinyOpenAlexWork.model_validate(destiny_work_dict),
        DestinyOpenAlexWork.model_validate(destiny_work_dict),
    ]
    expected_jsonl = '{"visibility":"public","identifiers":[{"identifier_type":"doi",\
"identifier":"10.1234/sampledoi"},{"identifier_type":"openalex","identifier":\
"W1234567890"}],"enhancements":[{"source":"openalex","visibility":"public",\
"processor_version":"1.0.0","content":\
{"enhancement_type":"bibliographic","authorship":[{"display_name":\
"Alice Example","orcid":"0000-0001-2345-6789","position":"first"}],\
"cited_by_count":10,"created_date":"2020-05-01","publication_date":\
"2020-04-01","publication_year":2020,"publisher":"Example Publisher"}}]}\n\
{"visibility":"public","identifiers":[{"identifier_type":"doi","identifier":\
"10.1234/sampledoi"},{"identifier_type":"openalex","identifier":"W1234567890"}],\
"enhancements":[{"source":"openalex","visibility":"public","processor_version":\
"1.0.0","content":{"enhancement_type":\
"bibliographic","authorship":[{"display_name":"Alice Example","orcid":\
"0000-0001-2345-6789","position":"first"}],"cited_by_count":10,"created_date":\
"2020-05-01","publication_date":"2020-04-01","publication_year":2020,\
"publisher":"Example Publisher"}}]}\n'
    result_iterator = convert_destinyworks_to_jsonl_string(destiny_data)
    result_bytes = b"".join(result_iterator)
    result_string = result_bytes.decode("utf-8")
    assert (
        result_string == expected_jsonl
    ), "The expected conversion should be returned."


def test_convert_destinyworks_to_jsonl_string_invalid_json():
    """Test failed conversion of invalid JSON to JSON-line based."""
    result_generator = convert_destinyworks_to_jsonl_string("invalid_json")

    with pytest.raises(JSONLConversionError) as error:
        next(result_generator)

    assert "destiny_data must be an iterable of DestinyOpenAlexWork" in str(error.value)


def test_convert_destinyworks_to_jsonl_string_empty_input():
    """Test successful conversion of an empty input to JSON-line based."""
    response = convert_destinyworks_to_jsonl_string([])
    result_bytes = b"".join(response)
    result = result_bytes.decode("utf-8")
    assert result == "", "Empty input should return an empty string"


def test_convert_destinyworks_to_jsonl_string_fails_non_serializable(
    mocker: MockerFixture, destiny_work_dict: dict
):
    """Test failed conversion of un-serializable JSON to JSON-line based."""
    test_data = [
        DestinyOpenAlexWork.model_validate(destiny_work_dict),
    ]
    mocker.patch(
        "pydantic.BaseModel.model_dump_json",
        side_effect=TypeError("Object of type set is not JSON serializable"),
    )
    result_generator = convert_destinyworks_to_jsonl_string(test_data)

    with pytest.raises(JSONLConversionError) as error:
        _result_bytes = b"".join(result_generator)
    assert (
        str(error.value)
        == "Error converting JSON to JSONL: Object of type set is not JSON serializable"
    ), "We should see a non-serializable related error"
