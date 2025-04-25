from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from openalex_incremental_updater.models.destiny import (
    convert_inverted_abstract,
    convert_openalex_to_destiny,
)


def test_destiny_openalex_work_valid_from_valid_openalex_work_dict(
    openalex_work_dict: dict,
) -> None:
    expected_creation_date = datetime(2025, 1, 1, tzinfo=ZoneInfo("UTC")).date()
    expected_creation_date_string = expected_creation_date.isoformat()
    expected_publication_year = expected_creation_date.year
    expected_openalex_id = openalex_work_dict["ids"]["openalex"]
    expected_abstract = convert_inverted_abstract(
        openalex_work_dict["abstract_inverted_index"]
    )
    expected_publication_year = 2025
    destiny_work = convert_openalex_to_destiny(openalex_work_dict)
    openalex_id_dict = next(
        (
            item
            for item in destiny_work.identifiers
            if item.get("identifier_type") == "open_alex"
        ),
        None,
    )
    openalex_id = openalex_id_dict.get("identifier", None) if openalex_id_dict else None
    abstract = next(
        item["content"]["abstract"]
        for item in destiny_work.enhancements
        if item["enhancement_type"] == "abstract"
    )
    publication_year = next(
        item["content"]["publication_year"]
        for item in destiny_work.enhancements
        if item["enhancement_type"] == "bibliographic"
    )
    created_date = next(
        item["content"]["created_date"]
        for item in destiny_work.enhancements
        if item["enhancement_type"] == "bibliographic"
    )

    assert (
        openalex_id == expected_openalex_id
    ), "Expect that the test ID is set correctly"
    assert (
        abstract == expected_abstract
    ), "Expect that the test abstract is set correctly"
    assert (
        publication_year == expected_publication_year
    ), "Expect that the test publication year is set correctly"
    assert (
        created_date == expected_creation_date_string
    ), "Expect that the test created date is set correctly"


def test_destiny_openalex_work_missing_required_identifiers_failure(
    openalex_work_dict: dict,
) -> None:
    missing_fields_dict = openalex_work_dict.copy()
    missing_fields_dict.pop("ids", None)

    with pytest.raises(ValidationError) as validation_error:
        convert_openalex_to_destiny(missing_fields_dict)

    assert "1 validation error" in str(validation_error.value)
    assert "At least one identifier must be of type DOI, PM_ID, or OPEN_ALEX" in str(
        validation_error.value
    )


@pytest.mark.parametrize(
    "missing_field",
    [["authorships"], ["created_date"], ["authorships", "created_date"]],
)
def test_destiny_openalex_work_missing_required_enhancements_failure(
    missing_field: list[str], openalex_work_dict: dict
) -> None:
    missing_fields_dict = openalex_work_dict.copy()
    for field in missing_field:
        missing_fields_dict.pop(field, None)

    with pytest.raises(ValidationError) as validation_error:
        convert_openalex_to_destiny(missing_fields_dict)

    assert "1 validation error" in str(
        validation_error.value
    ), "Expect that the validation error is raised"
    assert "At least one enhancement must be of type BIBLIOGRAPHIC" in str(
        validation_error.value
    )


def test_destiny_openalex_work_unexpected_fields_ignored_success(
    openalex_work_dict: dict,
) -> None:
    """
    Test that unexpected fields are ignored when creating an DestinyOpenAlexWork object.

    By default, Pydantic will ignore unexpected fields when creating an object.
    In this way, if DestinyOpenAlex adds additional fields to their API response, we can be more confident
    our pipeline will not break due to unexpected fields, as long as required fields are still present.
    """
    expected_openalex_id = openalex_work_dict["ids"]["openalex"]
    invalid_openalex_work_dict = openalex_work_dict.copy()
    invalid_openalex_work_dict.update(
        {"an_unexpected_field": "This should not be here"}
    )

    work = convert_openalex_to_destiny(invalid_openalex_work_dict)
    openalex_id_dict = next(
        (item for item in work.identifiers if item["identifier_type"] == "open_alex"),
        None,
    )
    openalex_id = openalex_id_dict.get("identifier", None) if openalex_id_dict else None

    assert (
        openalex_id == expected_openalex_id
    ), "Expect that the test ID is set correctly"
    assert not hasattr(
        work, "an_unexpected_field"
    ), "Expect that the unexpected field is not set on the object"
