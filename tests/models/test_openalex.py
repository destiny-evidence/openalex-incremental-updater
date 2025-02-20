from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from openalex_incremental_updater.models.openalex import OpenAlexWork


def test_openalex_work_valid_json_success() -> None:
    expected_creation_date = datetime(2025, 2, 13, tzinfo=ZoneInfo("UTC")).date()
    expected_creation_date_string = expected_creation_date.isoformat()
    expected_publication_year = expected_creation_date.year
    valid_response: dict[str, Any] = {
        "id": "123",
        "title": "Test Title",
        "publication_year": expected_publication_year,
        "created_date": expected_creation_date_string,
    }

    work = OpenAlexWork(**valid_response)
    assert work.id == "123", "Expect that the test ID is set correctly"
    assert work.title == "Test Title", "Expect that the test title is set correctly"
    assert (
        work.publication_year == expected_publication_year
    ), "Expect that the test publication year is set correctly"
    assert (
        work.created_date == expected_creation_date
    ), "Expect that the test created date is set correctly"


def test_openalex_work_missing_required_field_failure() -> None:
    expected_creation_date = datetime(2025, 2, 13, tzinfo=ZoneInfo("UTC")).date()
    expected_creation_date_string = expected_creation_date.isoformat()
    expected_publication_year = expected_creation_date.year
    invalid_response_missing_id: dict[str, Any] = {
        "title": "Test Title",
        "publication_year": expected_publication_year,
        "created_date": expected_creation_date_string,
    }

    with pytest.raises(ValidationError) as validation_error:
        OpenAlexWork(**invalid_response_missing_id)

    assert "1 validation error" in str(validation_error.value)
    assert "id" in str(validation_error.value)


def test_openalex_work_incorrect_data_type_failure() -> None:
    expected_creation_date = datetime(2025, 2, 13, tzinfo=ZoneInfo("UTC")).date()
    expected_creation_date_string = expected_creation_date.isoformat()
    expected_publication_year = expected_creation_date.year
    invalid_response_missing_id: dict[str, Any] = {
        "id": 123,
        "title": 456,
        "publication_year": expected_publication_year,
        "created_date": expected_creation_date_string,
    }

    with pytest.raises(ValidationError) as validation_error:
        OpenAlexWork(**invalid_response_missing_id)

    assert "2 validation errors" in str(validation_error.value)
    assert "id" in str(validation_error.value)
    assert "title" in str(validation_error.value)


def test_openalex_work_unexpected_fields_ignored_success() -> None:
    """
    Test that unexpected fields are ignored when creating an OpenAlexWork object.

    By default, Pydantic will ignore unexpected fields when creating an object.
    In this way, if OpenAlex adds additional fields to their API response, we can be more confident
    our pipeline will not break due to unexpected fields, as long as required fields are still present.
    """
    expected_creation_date = datetime(2025, 2, 13, tzinfo=ZoneInfo("UTC")).date()
    expected_creation_date_string = expected_creation_date.isoformat()
    expected_publication_year = expected_creation_date.year
    invalid_response: dict[str, Any] = {
        "id": "123",
        "title": "Test Title",
        "publication_year": expected_publication_year,
        "created_date": expected_creation_date_string,
        "an_unexpected_field": "This should not be here",
    }

    work = OpenAlexWork(**invalid_response)

    assert work.id == "123", "Expect that the test ID is set correctly"
    assert work.title == "Test Title", "Expect that the test title is set correctly"

    assert not hasattr(
        work, "an_unexpected_field"
    ), "Expect that the unexpected field is not set on the object"
