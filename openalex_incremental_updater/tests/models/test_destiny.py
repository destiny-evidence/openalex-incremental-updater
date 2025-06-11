from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from openalex_incremental_updater.models.destiny import (
    DestinyOpenAlexWork,
    DestinyOpenAlexWorkMetadata,
    convert_inverted_abstract,
    convert_openalex_to_destiny,
    get_destiny_openalex_work,
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


@pytest.mark.parametrize("missing_field", ["doi", "pm_id", "other"])
@pytest.mark.parametrize("missing_field_value", [None, "", " ", "None", "null"])
def test_destiny_openalex_work_missing_identifier_fields_ignored(
    openalex_work_dict: dict, missing_field: str, missing_field_value: None | str
) -> None:
    """Test that empty identifier fields are ignored when creating an DestinyOpenAlexWork object."""
    expected_openalex_id = openalex_work_dict["ids"]["openalex"]
    invalid_openalex_work_dict = openalex_work_dict.copy()
    invalid_openalex_work_dict["ids"][missing_field] = missing_field_value

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
    assert missing_field not in [
        identifier["identifier_type"] for identifier in work.identifiers
    ], "Expect that the missing identifier field is not set on the object"


def test_get_destiny_openalex_work_success(
    openalex_work_dict: dict,
) -> None:
    """Test that the get_destiny_openalex_work function returns a DestinyOpenAlexWorkMetadata object."""
    correct_source_for_openalex_input = "openalex"
    expected_openalex_id = openalex_work_dict["ids"]["openalex"]
    expected_abstract = "This is an example abstract"
    expected_abstract_process = "uninverted"

    ids_dict = openalex_work_dict.get("ids") if openalex_work_dict.get("ids") else None
    authorships_dict = openalex_work_dict.get("authorships")
    primary_location = openalex_work_dict.get("primary_location")
    source = primary_location.get("source") if primary_location else None
    host_organisation_name = source.get("host_organization_name") if source else None

    locations = openalex_work_dict.get("locations")
    topics = openalex_work_dict.get("topics")
    processor_version = "initial_openalex_import"
    if ids_dict:
        doi = ids_dict.get("doi")
        openalex_id = ids_dict.get("openalex")
        microsoft_academic_graph = ids_dict.get("mag")
        pubmed_id = ids_dict.get("pmid")
        pubmed_central_id = ids_dict.get("pmcid")
    else:
        doi = None
        openalex_id = None
        microsoft_academic_graph = None
        pubmed_id = None
        pubmed_central_id = None

    work_metadata = DestinyOpenAlexWorkMetadata(
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
    )
    work = get_destiny_openalex_work(
        work_metadata, openalex_work_dict, source=correct_source_for_openalex_input
    )

    assert isinstance(
        work, DestinyOpenAlexWork
    ), "Expect that the returned object is of type DestinyOpenAlexWork"

    abstract_dict = next(
        enhancement_dict
        for enhancement_dict in work.enhancements
        if "abstract" in enhancement_dict["enhancement_type"]
    )

    assert (
        work.identifiers[0]["identifier"] == expected_openalex_id
    ), "Expect that the OpenAlex ID is set correctly in the identifiers"
    assert (
        abstract_dict["content"]["abstract"] == expected_abstract
    ), "Expect that the abstract is set correctly"
    assert (
        abstract_dict["content"]["process"] == expected_abstract_process
    ), "Expect that the abstract process is set correctly"


def test_get_destiny_openalex_work_blank_abstract_openalex_input_incorrect_source(
    openalex_work_dict: dict,
) -> None:
    """Test that the get_destiny_openalex_work function returns a DestinyOpenAlexWorkMetadata object."""
    bad_source_for_openalex_input = "pik_solr"
    expected_openalex_id = openalex_work_dict["ids"]["openalex"]
    expected_abstract = ""
    expected_abstract_process = "other"

    ids_dict = openalex_work_dict.get("ids") if openalex_work_dict.get("ids") else None
    authorships_dict = openalex_work_dict.get("authorships")
    primary_location = openalex_work_dict.get("primary_location")
    source = primary_location.get("source") if primary_location else None
    host_organisation_name = source.get("host_organization_name") if source else None

    locations = openalex_work_dict.get("locations")
    topics = openalex_work_dict.get("topics")
    processor_version = "initial_openalex_import"
    if ids_dict:
        doi = ids_dict.get("doi")
        openalex_id = ids_dict.get("openalex")
        microsoft_academic_graph = ids_dict.get("mag")
        pubmed_id = ids_dict.get("pmid")
        pubmed_central_id = ids_dict.get("pmcid")
    else:
        doi = None
        openalex_id = None
        microsoft_academic_graph = None
        pubmed_id = None
        pubmed_central_id = None

    work_metadata = DestinyOpenAlexWorkMetadata(
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
    )
    work = get_destiny_openalex_work(
        work_metadata, openalex_work_dict, source=bad_source_for_openalex_input
    )

    assert isinstance(
        work, DestinyOpenAlexWork
    ), "Expect that the returned object is of type DestinyOpenAlexWork"

    abstract_dict = next(
        enhancement_dict
        for enhancement_dict in work.enhancements
        if "abstract" in enhancement_dict["enhancement_type"]
    )

    assert (
        work.identifiers[0]["identifier"] == expected_openalex_id
    ), "Expect that the OpenAlex ID is set correctly in the identifiers"
    assert abstract_dict["content"]["abstract"] == expected_abstract, (
        "Expect that no abstract is returned when trying to directly get the abstract from openalex source input",
    )
    assert (
        abstract_dict["content"]["process"] == expected_abstract_process
    ), "Expect that the abstract process returns 'other' for a non-openalex source"
