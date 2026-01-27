import pytest

from openalex_incremental_updater.models.destiny import DestinyOpenAlexWorkMetadata


@pytest.fixture
def destiny_openalex_work_metadata(
    openalex_work_dict: dict,
) -> "DestinyOpenAlexWorkMetadata":
    ids_dict = openalex_work_dict.get("ids") if openalex_work_dict.get("ids") else None
    authorships_dict = openalex_work_dict.get("authorships")
    primary_location = openalex_work_dict.get("primary_location")
    source = primary_location.get("source") if primary_location else None
    host_organisation_name = source.get("host_organization_name") if source else None

    locations = openalex_work_dict.get("locations")
    topics = openalex_work_dict.get("topics")
    pagination = (
        openalex_work_dict.get("biblio") if openalex_work_dict.get("biblio") else None
    )
    processor_version = "initial_openalex_import"
    if ids_dict:
        doi = ids_dict.get("doi")
        openalex_id = ids_dict.get("openalex").rsplit("/", 1)[-1]
        microsoft_academic_graph = ids_dict.get("mag")
        pubmed_id = ids_dict.get("pmid")
        pubmed_central_id = ids_dict.get("pmcid")
    else:
        doi = None
        openalex_id = None
        microsoft_academic_graph = None
        pubmed_id = None
        pubmed_central_id = None

    return DestinyOpenAlexWorkMetadata(
        doi=doi,
        openalex_id=openalex_id,
        microsoft_academic_graph=microsoft_academic_graph,
        pubmed_id=pubmed_id,
        pubmed_central_id=pubmed_central_id,
        authorships_dict=authorships_dict,
        host_organisation_name=host_organisation_name,
        locations=locations,
        topics=topics,
        processor_version=processor_version,
        pagination=pagination,
    )
