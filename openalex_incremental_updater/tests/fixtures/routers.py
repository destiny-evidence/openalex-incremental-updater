"""Define fixtures for router tests."""

import copy
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from openalex_incremental_updater.models.destiny import convert_openalex_to_destiny


@pytest.fixture
def single_openalex_work_response(set_test_environment_variables: None) -> dict:
    """Return a single OpenAlex work."""
    test_datetime = datetime(2025, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
    test_date = test_datetime.date()

    return {
        "id": "https://openalex.org/W9876543210",
        "doi": "https://doi.org/10.5678/test_doi",
        "title": "Test Title",
        "display_name": "Test short title",
        "publication_year": test_date.year,
        "publication_date": str(test_date),
        "ids": {
            "openalex": "https://openalex.org/W9876543210",
            "doi": "https://doi.org/10.5678/test_doi",
        },
        "language": "en",
        "primary_location": None,
        "type": None,
        "type_crossref": None,
        "indexed_in": None,
        "open_access": None,
        "authorships": [
            {
                "author_position": "first",
                "author": {
                    "id": "https://openalex.org/example-first-author-id",
                    "display_name": "First Author",
                    "orcid": "https://orcid.org/example-orcid-first-author",
                },
                "institutions": [],
                "countries": [],
                "is_corresponding": False,
                "raw_author_name": "First Author",
                "raw_affiliation_strings": [],
                "affiliations": [],
            },
            {
                "author_position": "last",
                "author": {
                    "id": "https://openalex.org/example-last-author-id",
                    "display_name": "Last Author",
                    "orcid": "https://orcid.org/example-orcid-last-author",
                },
                "institutions": [],
                "countries": [],
                "is_corresponding": False,
                "raw_author_name": "Last Author",
                "raw_affiliation_strings": [],
                "affiliations": [],
            },
        ],
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
        "biblio": {
            "volume": "999",
            "issue": "999",
            "first_page": "1",
            "last_page": "10",
        },
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
def single_destinyopenalex_work_response(
    single_openalex_work_response: dict, set_test_environment_variables: None
) -> dict:
    """Return a single OpenAlex work."""
    return json.loads(
        convert_openalex_to_destiny(single_openalex_work_response).model_dump_json()
    )


@pytest.fixture
def double_openalex_work_response(
    single_openalex_work_response: dict, set_test_environment_variables: None
) -> list[dict]:
    """Return two OpenAlex works."""
    return [copy.deepcopy(single_openalex_work_response) for _ in range(2)]


@pytest.fixture
def double_destinyopenalex_work_response_dicts(
    double_openalex_work_response: dict, set_test_environment_variables: None
) -> list[dict]:
    """Return a single OpenAlex work."""
    return [
        json.loads(
            convert_openalex_to_destiny(openalex_work_response).model_dump_json()
        )
        for openalex_work_response in double_openalex_work_response
    ]
