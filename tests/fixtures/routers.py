"""Define fixtures for router tests."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest


@pytest.fixture
def single_openalex_work_response(set_test_environment_variables: None) -> dict:
    """Return a single OpenAlex work."""
    test_datetime = datetime(2025, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
    test_date = test_datetime.date()

    return {
        "id": "https://openalex.org/TEST_ID",
        "doi": "https://doi.org/test_doi",
        "title": "Test Title",
        "display_name": "Test short title",
        "publication_year": test_date.year,
        "publication_date": str(test_date),
        "ids": None,
        "language": "en",
        "primary_location": None,
        "type": None,
        "type_crossref": None,
        "indexed_in": None,
        "open_access": None,
        "authorships": None,
        "countries_distinct_count": None,
        "institutions_distinct_count": None,
        "corresponding_author_ids": None,
        "corresponding_institution_ids": None,
        "apc_list": None,
        "apc_paid": None,
        "fwci": None,
        "has_fulltext": None,
        "cited_by_count": None,
        "citation_normalized_percentile": None,
        "biblio": None,
        "is_retracted": None,
        "is_paratext": None,
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
        "topics": None,
        "keywords": None,
        "concepts": None,
        "mesh": None,
        "locations_count": None,
        "locations": None,
        "best_oa_location": None,
        "sustainable_development_goals": None,
        "grants": None,
        "datasets": None,
        "versions": None,
        "referenced_works_count": None,
        "referenced_works": None,
        "related_works": None,
        "abstract_inverted_index": None,
        "cited_by_api_url": None,
        "counts_by_year": None,
        "updated_date": test_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
        "created_date": str(test_date),
    }


@pytest.fixture
def double_openalex_work_response(set_test_environment_variables: None) -> list[dict]:
    """Return two OpenAlex works."""
    test_datetime = datetime(2025, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
    test_date = test_datetime.date()

    test_response = {
        "id": "https://openalex.org/TEST_ID",
        "doi": "https://doi.org/test_doi",
        "title": "Test Title",
        "display_name": "Test short title",
        "publication_year": test_date.year,
        "publication_date": str(test_date),
        "ids": None,
        "language": "en",
        "primary_location": None,
        "type": None,
        "type_crossref": None,
        "indexed_in": None,
        "open_access": None,
        "authorships": None,
        "countries_distinct_count": None,
        "institutions_distinct_count": None,
        "corresponding_author_ids": None,
        "corresponding_institution_ids": None,
        "apc_list": None,
        "apc_paid": None,
        "fwci": None,
        "has_fulltext": None,
        "cited_by_count": None,
        "citation_normalized_percentile": None,
        "biblio": None,
        "is_retracted": None,
        "is_paratext": None,
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
        "topics": None,
        "keywords": None,
        "concepts": None,
        "mesh": None,
        "locations_count": None,
        "locations": None,
        "best_oa_location": None,
        "sustainable_development_goals": None,
        "grants": None,
        "datasets": None,
        "versions": None,
        "referenced_works_count": None,
        "referenced_works": None,
        "related_works": None,
        "abstract_inverted_index": None,
        "cited_by_api_url": None,
        "counts_by_year": None,
        "updated_date": test_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
        "created_date": str(test_date),
    }
    return [test_response, test_response]
