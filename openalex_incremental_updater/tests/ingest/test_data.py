import json

import pytest
from destiny_sdk.references import ReferenceFileInput
from pytest_mock import MockerFixture

from openalex_incremental_updater.ingest.data import (
    JSONLConversionError,
    convert_destinyworks_to_jsonl_string,
)


@pytest.mark.asyncio
async def test_convert_destinyworks_to_jsonl_string_valid_json(destiny_work_dict: dict):
    """Test successful conversion of JSON to JSON-line based with valid JSON."""
    destiny_data = [
        [
            ReferenceFileInput.model_validate(destiny_work_dict),
        ],
        [
            ReferenceFileInput.model_validate(destiny_work_dict),
            ReferenceFileInput.model_validate(destiny_work_dict),
        ],
    ]
    expected_jsonl_dict = [
        {
            "visibility": "public",
            "identifiers": [
                {"identifier": "10.1234/sampledoi", "identifier_type": "doi"},
                {"identifier": "W1234567890", "identifier_type": "open_alex"},
            ],
            "enhancements": [
                {
                    "source": "openalex",
                    "visibility": "public",
                    "robot_version": "1.0.0",
                    "content": {
                        "enhancement_type": "bibliographic",
                        "authorship": [
                            {
                                "display_name": "Alice Example",
                                "orcid": "0000-0001-2345-6789",
                                "position": "first",
                            }
                        ],
                        "cited_by_count": 10,
                        "created_date": "2020-05-01",
                        "updated_date": None,
                        "publication_date": "2020-04-01",
                        "publication_year": 2020,
                        "publisher": "Example Publisher",
                        "title": None,
                        "pagination": {
                            "volume": "123",
                            "issue": "456",
                            "first_page": "789",
                            "last_page": "999",
                        },
                        "publication_venue": None,
                    },
                }
            ],
        },
        {
            "visibility": "public",
            "identifiers": [
                {"identifier": "10.1234/sampledoi", "identifier_type": "doi"},
                {"identifier": "W1234567890", "identifier_type": "open_alex"},
            ],
            "enhancements": [
                {
                    "source": "openalex",
                    "visibility": "public",
                    "robot_version": "1.0.0",
                    "content": {
                        "enhancement_type": "bibliographic",
                        "authorship": [
                            {
                                "display_name": "Alice Example",
                                "orcid": "0000-0001-2345-6789",
                                "position": "first",
                            }
                        ],
                        "cited_by_count": 10,
                        "created_date": "2020-05-01",
                        "updated_date": None,
                        "publication_date": "2020-04-01",
                        "publication_year": 2020,
                        "publisher": "Example Publisher",
                        "title": None,
                        "pagination": {
                            "volume": "123",
                            "issue": "456",
                            "first_page": "789",
                            "last_page": "999",
                        },
                        "publication_venue": None,
                    },
                }
            ],
        },
        {
            "visibility": "public",
            "identifiers": [
                {"identifier": "10.1234/sampledoi", "identifier_type": "doi"},
                {"identifier": "W1234567890", "identifier_type": "open_alex"},
            ],
            "enhancements": [
                {
                    "source": "openalex",
                    "visibility": "public",
                    "robot_version": "1.0.0",
                    "content": {
                        "enhancement_type": "bibliographic",
                        "authorship": [
                            {
                                "display_name": "Alice Example",
                                "orcid": "0000-0001-2345-6789",
                                "position": "first",
                            }
                        ],
                        "cited_by_count": 10,
                        "created_date": "2020-05-01",
                        "updated_date": None,
                        "publication_date": "2020-04-01",
                        "publication_year": 2020,
                        "publisher": "Example Publisher",
                        "title": None,
                        "pagination": {
                            "volume": "123",
                            "issue": "456",
                            "first_page": "789",
                            "last_page": "999",
                        },
                        "publication_venue": None,
                    },
                }
            ],
        },
    ]
    expected_jsonl = "".join(
        [
            json.dumps(sub_dict, separators=(",", ":")) + "\n"
            for sub_dict in expected_jsonl_dict
        ]
    )

    async def async_gen(data):
        for item in data:
            yield item

    destiny_data_async_generator = async_gen(destiny_data)
    result_iterator = convert_destinyworks_to_jsonl_string(destiny_data_async_generator)
    result = [item async for item in result_iterator]
    result_string = b"".join(result).decode("utf-8")
    assert (
        result_string == expected_jsonl
    ), "The expected conversion should be returned."


@pytest.mark.asyncio
async def test_convert_destinyworks_to_jsonl_string_invalid_jsonl_conversion_batch_level(
    destiny_work_dict,
):
    """Test failed conversion of invalid JSON to JSON-line based."""
    test_invalid_json_destiny_works = "invalid_dict_item"

    async def async_gen(data):
        for item in data:
            yield item

    destiny_data_async_generator = async_gen(test_invalid_json_destiny_works)
    result_generator = convert_destinyworks_to_jsonl_string(
        destiny_data_async_generator
    )

    with pytest.raises(JSONLConversionError) as error:
        _result = [item async for item in result_generator]

    assert "Each batch must be a list of ReferenceFileInput" in str(error.value)


@pytest.mark.asyncio
async def test_convert_destinyworks_to_jsonl_string_invalid_jsonl_conversion_item_level(
    destiny_work_dict,
):
    """Test failed conversion of invalid JSON to JSON-line based."""
    test_invalid_json_destiny_works = [["invalid_dict_item"]]

    async def async_gen(data):
        for item in data:
            yield item

    destiny_data_async_generator = async_gen(test_invalid_json_destiny_works)
    result_generator = convert_destinyworks_to_jsonl_string(
        destiny_data_async_generator
    )

    with pytest.raises(JSONLConversionError) as error:
        _result = [item async for item in result_generator]

    assert "All items must be ReferenceFileInput instances" in str(error.value)


@pytest.mark.asyncio
async def test_convert_destinyworks_to_jsonl_string_empty_input():
    """Test successful conversion of an empty input to JSON-line based."""

    async def async_gen(data):
        for item in data:
            yield item

    empty_list = []
    response_generator = convert_destinyworks_to_jsonl_string(async_gen(empty_list))
    response = [item async for item in response_generator]
    result_bytes = b"".join(response)
    result = result_bytes.decode("utf-8")
    assert result == "", "Empty input should return an empty string"


@pytest.mark.asyncio
async def test_convert_destinyworks_to_jsonl_string_fails_non_serializable(
    mocker: MockerFixture, destiny_work_dict: dict
):
    """Test failed conversion of un-serializable JSON to JSON-line based."""
    test_data = [[ReferenceFileInput.model_validate(destiny_work_dict)]]

    async def async_gen(data):
        for item in data:
            yield item

    test_data_async_generator = async_gen(test_data)
    mocker.patch(
        "pydantic.BaseModel.model_dump_json",
        side_effect=TypeError("Object of type set is not JSON serializable"),
    )
    result_generator = convert_destinyworks_to_jsonl_string(test_data_async_generator)

    with pytest.raises(JSONLConversionError) as error:
        _result = [item async for item in result_generator]
    assert (
        str(error.value)
        == "Error converting JSON to JSONL: Object of type set is not JSON serializable"
    ), "We should see a non-serializable related error"
