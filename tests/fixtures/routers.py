"""Define fixtures for router tests."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest


@pytest.fixture(scope="session")
def single_openalex_work_response() -> dict:
    """Return a single OpenAlex work response."""
    test_datetime = datetime(2025, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
    test_date = test_datetime.date()
    return {
        "id": "https://openalex.org/TEST_ID",
        "doi": "https://doi.org/test_doi",
        "title": "Test Title",
        "display_name": "Test short title",
        "publication_year": str(test_date.year),
        "publication_date": str(test_date),
        "language": "en",
        "primary_topic": {
            "id": "https://openalex.org/T10430",
            "display_name": "Software Engineering Techniques and Practices",
            "score": 0.999,
            "subfield": {
                "id": "https://openalex.org/subfields/test_subfield",
                "display_name": "Software Testing",
            },
            "field": {
                "id": "https://openalex.org/fields/17",
                "display_name": "Computer Science",
            },
            "domain": {
                "id": "https://openalex.org/domains/3",
                "display_name": "Physical Sciences",
            },
        },
        "updated_date": test_datetime.strftime("%Y-%m-%dT%H:%M:%S.%f"),
        "created_date": str(test_date),
    }
