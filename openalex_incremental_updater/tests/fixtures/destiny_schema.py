import pytest

from openalex_incremental_updater.models.destiny import DestinyOpenAlexWork


@pytest.fixture
def destiny_work_dict(set_test_environment_variables: None) -> dict:
    return {
        "visibility": "public",
        "identifiers": [
            {"identifier_type": "doi", "identifier": "10.1234/sampledoi"},
            {"identifier_type": "openalex", "identifier": "W1234567890"},
        ],
        "enhancements": [
            {
                "source": "openalex",
                "visibility": "public",
                "processor_version": "1.0.0",
                "enhancement_type": "bibliographic",
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
                    "publication_date": "2020-04-01",
                    "publication_year": 2020,
                    "publisher": "Example Publisher",
                },
            }
        ],
    }


@pytest.fixture
def destiny_work(destiny_work_dict: dict) -> DestinyOpenAlexWork:
    return DestinyOpenAlexWork(**destiny_work_dict)
