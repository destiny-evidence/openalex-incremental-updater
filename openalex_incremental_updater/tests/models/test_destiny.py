from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from openalex_incremental_updater.models.destiny import (
    DataSource,
    DestinyOpenAlexWork,
    DestinyOpenAlexWorkMetadata,
    convert_inverted_abstract,
    convert_openalex_to_destiny,
    get_destiny_openalex_work,
    is_valid_nonempty_string,
    strip_url_prefix,
)


def test_destiny_openalex_work_valid_from_valid_openalex_work_dict(
    openalex_work_dict: dict,
) -> None:
    expected_creation_date = datetime(2025, 1, 1, tzinfo=ZoneInfo("UTC")).date()
    expected_creation_date_string = expected_creation_date.isoformat()
    expected_publication_year = expected_creation_date.year
    expected_openalex_id = openalex_work_dict["ids"]["openalex"].rsplit("/", 1)[-1]
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
        if item["content"]["enhancement_type"] == "abstract"
    )
    publication_year = next(
        item["content"]["publication_year"]
        for item in destiny_work.enhancements
        if item["content"]["enhancement_type"] == "bibliographic"
    )
    created_date = next(
        item["content"]["created_date"]
        for item in destiny_work.enhancements
        if item["content"]["enhancement_type"] == "bibliographic"
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
    expected_openalex_id = openalex_work_dict["ids"]["openalex"].rsplit("/", 1)[-1]
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
    expected_openalex_id = openalex_work_dict["ids"]["openalex"].rsplit("/", 1)[-1]
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
    correct_source_for_openalex_input = DataSource.OPEN_ALEX
    expected_openalex_id = openalex_work_dict["ids"]["openalex"].rsplit("/", 1)[-1]
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
        work_metadata, openalex_work_dict, data_source=correct_source_for_openalex_input
    )

    assert isinstance(
        work, DestinyOpenAlexWork
    ), "Expect that the returned object is of type DestinyOpenAlexWork"

    abstract_dict = next(
        enhancement_dict
        for enhancement_dict in work.enhancements
        if "abstract" in enhancement_dict["content"]["enhancement_type"]
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


def test_get_destiny_openalex_work_blank_abstract_from_openalex_input_with_incorrect_source(
    openalex_work_dict: dict,
) -> None:
    """
    Test that the get_destiny_openalex_work function returns a DestinyOpenAlexWorkMetadata object.

    This test checks that when the source is not set to 'openalex' for openalex-type (inverted abstract)
    data, the abstract is not set and does not appear as an enhancement.
    """
    bad_source_for_openalex_input = DataSource.SOLR
    expected_openalex_id = openalex_work_dict["ids"]["openalex"].rsplit("/", 1)[-1]
    openalex_work_dict_locations = next(iter(openalex_work_dict.get("locations", {})))
    openalex_work_locations_with_null_values_removed = {
        key: value
        for key, value in openalex_work_dict_locations.items()
        if value not in (None, "", {}, [])
    }
    destiny_location_keys = [
        "is_oa",
        "version",
        "landing_page_url",
        "pdf_url",
        "license",
        "source",
    ]
    expected_locations = {
        key: value
        for key, value in openalex_work_locations_with_null_values_removed.items()
        if key in destiny_location_keys
    }
    if "source" in expected_locations:
        expected_locations["extra"] = expected_locations.pop("source")
    expected_annotations = next(iter(openalex_work_dict.get("topics", [])))

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
        work_metadata, openalex_work_dict, data_source=bad_source_for_openalex_input
    )

    work_annotations = next(
        enhancement.get("content").get("annotations")
        for enhancement in work.enhancements
        if enhancement.get("content", {}).get("enhancement_type") == "annotation"
    )

    work_locations = next(
        enhancement.get("content").get("locations")
        for enhancement in work.enhancements
        if enhancement.get("content", {}).get("enhancement_type") == "location"
    )

    assert isinstance(
        work, DestinyOpenAlexWork
    ), "Expect that the returned object is of type DestinyOpenAlexWork"
    assert (
        work.identifiers[0]["identifier"] == expected_openalex_id
    ), "Expect that the OpenAlex ID is set correctly in the identifiers"

    assert (
        next(iter(work_annotations))["data"] == expected_annotations
    ), "Expect that the annotations are still set correctly in the case of no abstract"
    assert (
        next(iter(work_locations)) == expected_locations
    ), "Expect that the locations are still set correctly in the case of no abstract"

    assert "abstract" not in [
        enhancement_dict["content"]["enhancement_type"]
        for enhancement_dict in work.enhancements
    ], "Expect that the abstract is not set in the enhancements"


@pytest.mark.parametrize(
    ("input_value", "expected_output"),
    [
        ("  ", False),
        ("", False),
        (None, False),
        ("None", False),
        ("null", False),
        (0, False),
        ("Valid String", True),
        ("Another valid string", True),
        ("12345", True),
        ("!@#$%^&*()", True),
    ],
)
def test_is_valid_nonempty_string(input_value: Any, *, expected_output: bool) -> None:
    """Test the is_valid_nonempty_string function."""
    assert (
        is_valid_nonempty_string(input_value) == expected_output
    ), "Confirm that valid strings return True and invalid strings return False"


def test_pubmed_identifier_parsed_as_integer(
    openalex_work_dict: dict,
) -> None:
    """
    Test that the pubmed identifier is parsed as an integer in DestinyOpenAlexWork.

    All other identifiers should be parsed as strings.
    """
    test_openalex_work_dict = openalex_work_dict.copy()
    openalex_identifier = openalex_work_dict["ids"].get("openalex").rsplit("/", 1)[-1]
    doi_identifier = openalex_work_dict["ids"].get("doi")
    test_pmid_identifier = "https://pubmed.ncbi.nlm.nih.gov/123456789"
    test_microsoft_academic_graph_identifier = "2222222222"
    test_pubmed_central_identifier = "3333333333"

    expected_resulting_pmid = test_pmid_identifier.rsplit("/", 1)[-1]

    test_openalex_work_dict["ids"]["pmid"] = test_pmid_identifier
    test_openalex_work_dict["ids"]["mag"] = test_microsoft_academic_graph_identifier
    test_openalex_work_dict["ids"]["pmcid"] = test_pubmed_central_identifier

    destiny_work = convert_openalex_to_destiny(test_openalex_work_dict)
    destiny_pubmed_identifier = next(
        identifier
        for identifier in destiny_work.identifiers
        if identifier["identifier_type"] == "pm_id"
    )
    destiny_openalex_identifier = next(
        identifier
        for identifier in destiny_work.identifiers
        if identifier["identifier_type"] == "open_alex"
    )
    destiny_doi_identifier = next(
        identifier
        for identifier in destiny_work.identifiers
        if identifier["identifier_type"] == "doi"
    )
    destiny_microsoft_academic_graph_identifier = next(
        identifier
        for identifier in destiny_work.identifiers
        if identifier["identifier_type"] == "other"
        and identifier["other_identifier_name"] == "Microsoft Academic Graph ID"
    )
    destiny_pubmed_central_identifier = next(
        identifier
        for identifier in destiny_work.identifiers
        if identifier["identifier_type"] == "other"
        and identifier["other_identifier_name"] == "Pubmed Central ID"
    )

    assert isinstance(
        destiny_openalex_identifier["identifier"], str
    ), "Expect that openalex_id is a string"
    assert isinstance(
        destiny_doi_identifier["identifier"], str
    ), "Expect that doi_id is a string"
    assert isinstance(
        destiny_microsoft_academic_graph_identifier["identifier"], str
    ), "Expect that mag_id is a string"
    assert isinstance(
        destiny_pubmed_central_identifier["identifier"], str
    ), "Expect that pubmed_central_id is a string"
    assert (
        destiny_openalex_identifier["identifier"] == openalex_identifier
    ), "Expect that openalex_id is parsed correctly"
    assert (
        destiny_doi_identifier["identifier"] == doi_identifier
    ), "Expect that doi_id is parsed correctly"
    assert (
        destiny_microsoft_academic_graph_identifier["identifier"]
        == test_microsoft_academic_graph_identifier
    ), "Expect that mag_id is parsed correctly"
    assert (
        destiny_pubmed_central_identifier["identifier"]
        == test_pubmed_central_identifier
    ), "Expect that pubmed_central_id is parsed correctly"

    assert isinstance(
        destiny_pubmed_identifier["identifier"], int
    ), "Expect that pubmed_id is an integer"
    assert destiny_pubmed_identifier["identifier"] == int(
        expected_resulting_pmid
    ), "Expect that pubmed_id is parsed correctly"


def test_pubmed_identifier_none_case_handled(
    openalex_work_dict: dict,
) -> None:
    """
    Test that the pubmed identifier is parsed as an integer in DestinyOpenAlexWork.

    All other identifiers should be parsed as strings.
    """
    test_openalex_work_dict = openalex_work_dict.copy()
    openalex_identifier = openalex_work_dict["ids"].get("openalex").rsplit("/", 1)[-1]
    doi_identifier = openalex_work_dict["ids"].get("doi")
    test_pmid_identifier = None

    test_openalex_work_dict["ids"]["pmid"] = test_pmid_identifier

    destiny_work = convert_openalex_to_destiny(test_openalex_work_dict)

    destiny_openalex_identifier = next(
        identifier
        for identifier in destiny_work.identifiers
        if identifier["identifier_type"] == "open_alex"
    )
    destiny_doi_identifier = next(
        identifier
        for identifier in destiny_work.identifiers
        if identifier["identifier_type"] == "doi"
    )

    assert isinstance(
        destiny_openalex_identifier["identifier"], str
    ), "Expect that openalex_id is a string"
    assert isinstance(
        destiny_doi_identifier["identifier"], str
    ), "Expect that doi_id is a string"
    assert (
        destiny_openalex_identifier["identifier"] == openalex_identifier
    ), "Expect that openalex_id is parsed correctly"
    assert (
        destiny_doi_identifier["identifier"] == doi_identifier
    ), "Expect that doi_id is parsed correctly"

    # Pubmed ID shouldn't be present if it is None
    assert "pm_id" not in [
        identifier["identifier_type"] for identifier in destiny_work.identifiers
    ], "Expect that pm_id is not present if it is None"


def test_pubmed_central_identifier_masquerading_as_pubmed_id(
    openalex_work_dict: dict,
) -> None:
    """
    Test that the pubmed identifier is parsed as an integer in DestinyOpenAlexWork.

    All other identifiers should be parsed as strings.
    """
    test_openalex_work_dict = openalex_work_dict.copy()
    openalex_identifier = openalex_work_dict["ids"].get("openalex").rsplit("/", 1)[-1]
    doi_identifier = openalex_work_dict["ids"].get("doi")
    test_pmid_identifier = "PMCID123456789"

    test_openalex_work_dict["ids"]["pmid"] = test_pmid_identifier

    destiny_work = convert_openalex_to_destiny(test_openalex_work_dict)

    destiny_openalex_identifier = next(
        identifier
        for identifier in destiny_work.identifiers
        if identifier["identifier_type"] == "open_alex"
    )
    destiny_doi_identifier = next(
        identifier
        for identifier in destiny_work.identifiers
        if identifier["identifier_type"] == "doi"
    )

    assert isinstance(
        destiny_openalex_identifier["identifier"], str
    ), "Expect that openalex_id is a string"
    assert isinstance(
        destiny_doi_identifier["identifier"], str
    ), "Expect that doi_id is a string"
    assert (
        destiny_openalex_identifier["identifier"] == openalex_identifier
    ), "Expect that openalex_id is parsed correctly"
    assert (
        destiny_doi_identifier["identifier"] == doi_identifier
    ), "Expect that doi_id is parsed correctly"

    # Pubmed ID shouldn't be present if it is None
    assert "pm_id" not in [
        identifier["identifier_type"] for identifier in destiny_work.identifiers
    ], "Expect that pm_id is not present if it is None"


@pytest.mark.parametrize(
    ("url", "expected_output"),
    [
        ("https://example.com/path", "path"),
        ("https://example.com/path/subdirectory/W123456789", "W123456789"),
        ("http://example.com/path", "path"),
        ("http://example.com/", ""),
        ("ftp://example.com/path", "ftp://example.com/path"),
        ("example.com/path", "example.com/path"),
        ("https://", "https://"),
        ("", ""),
        (None, None),
    ],
)
def test_strip_url_prefix(url: str, expected_output: str) -> None:
    """Test the strip_url_prefix function."""
    assert (
        strip_url_prefix(url) == expected_output
    ), f"Expected {expected_output} for {url}"
