import pytest
from destiny_sdk.references import ReferenceFileInput


@pytest.fixture
def destiny_work_dict(set_test_environment_variables: None) -> dict:
    return {
        "visibility": "public",
        "identifiers": [
            {"identifier_type": "doi", "identifier": "10.1234/sampledoi"},
            {"identifier_type": "open_alex", "identifier": "W1234567890"},
        ],
        "enhancements": [
            {
                "source": "openalex",
                "visibility": "public",
                "processor_version": "1.0.0",
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
def destiny_work(destiny_work_dict: dict) -> ReferenceFileInput:
    return ReferenceFileInput(**destiny_work_dict)


@pytest.fixture
def single_destiny_openalex_work_jsonl_string() -> str:
    return '{"visibility":"public","identifiers":[{"identifier":"W9876543210","identifier_type":"open_alex"},{"identifier":"10.5678/test_doi","identifier_type":"doi"}],"enhancements":[{"source":"openalex","visibility":"public","robot_version":null,"content":{"enhancement_type":"bibliographic","authorship":[{"display_name":"First Author","orcid":"https://orcid.org/example-orcid-first-author","position":"first"},{"display_name":"Last Author","orcid":"https://orcid.org/example-orcid-last-author","position":"last"}],"cited_by_count":null,"created_date":"2025-01-01","publication_date":"2025-01-01","publication_year":2025,"publisher":null,"title":"Test Title"}}]}\n'
