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
"publisher":"Example Publisher"}}]}'
    assert (
        convert_destinyworks_to_jsonl_string(destiny_data) == expected_jsonl
    ), "The expected conversion should be returned."


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
        DestinyOpenAlexWork.model_validate(destiny_work_dict),
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
