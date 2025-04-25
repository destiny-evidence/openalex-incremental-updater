import pytest


@pytest.fixture
def solr_work_dict() -> dict:
    return {
        "id": "example-openalex-id",
        "title": "Example Title",
        "abstract": "Example abstract text.",
        "title_abstract": "Example Title Example abstract text.",
        "authorships": '[{"author": {"display_name": "Example Author 1", "id": "https://openalex.org/example-author-id-1", "orcid": "https://orcid.org/example-author-orcid-1"}, "author_position": "first", "countries": [], "institutions": [], "is_corresponding": false, "raw_affiliation_string": null, "raw_affiliation_strings": [], "raw_author_name": "Example Author 1"}, {"author": {"display_name": "Example Author 2", "id": "https://openalex.org/example-author-id-2", "orcid": "https://orcid.org/example-author-orcid-2"}, "author_position": "middle", "countries": [], "institutions": [], "is_corresponding": false, "raw_affiliation_string": null, "raw_affiliation_strings": [], "raw_author_name": "Example Author 2"}, {"author": {"display_name": "Example Author 3", "id": "https://openalex.org/example-author-id-3", "orcid": "https://orcid.org/example-author-orcid-3"}, "author_position": "last", "countries": [], "institutions": [], "is_corresponding": false, "raw_affiliation_string": null, "raw_affiliation_strings": [], "raw_author_name": "Example Author 3"}]',
        "indexed_in": '["datacite"]',
        "locations": '[{"is_oa": true, "is_primary": true, "landing_page_url": "https://example-landing-page-1", "source": {"display_name": "Example Source 1", "host_organization": "Example host organization ID 1", "host_organization_name": "Example host organiztion 1", "id": "https://openalex.org/example-host-org-id-1", "type": "repository"}}, {"is_oa": false, "is_primary": false, "landing_page_url": "https://example-landing-page-2", "source": {"display_name": "Example Source 2", "host_organization": "Example host organization ID 2", "host_organization_name": "Example host organiztion 2", "id": "https://openalex.org/example-host-org-id-2", "type": "metadata"}}]',
        "topics": '[{"id": "Example Topic ID 1", "display_name": "Example Topic 1", "score": 0.3305, "subfield": {"id": "Example Topic Subfield ID 1", "display_name": "Example Topic Subfield 1"}, "field": {"id": "Example Topic Field ID 1", "display_name": "Example Topic Field 1"}, "domain": {"id": "Example Topic Domain ID 1", "display_name": "Example Topic Domain 1"}}]',
        "is_retracted": False,
        "publisher_id": "https://openalex.org/example-publisher-id",
        "is_accepted": False,
        "cited_by_count": 0,
        "is_paratext": False,
        "is_published": False,
        "language": "en",
        "source": "Figshare",
        "type": "dataset",
        "mag": "None",
        "publication_year": 2025,
        "_version_": 123456789,
        "publication_date": "2025-01-01T00:00:00Z",
        "publisher": "Figshare (United Kingdom)",
        "is_oa": True,
        "created_date": "2025-01-01T00:00:00Z",
        "updated_date": "2025-01-04T01:00:00.380Z",
        "source_id": "https://openalex.org/example-source-id",
        "doi": "https://doi.org/example-doi",
    }
