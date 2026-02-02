import copy
from datetime import datetime
from typing import Any

import pytest
from destiny_sdk.enhancements import (
    AbstractContentEnhancement,
    AnnotationEnhancement,
    BibliographicMetadataEnhancement,
    LocationEnhancement,
    Pagination,
    PublicationVenue,
    PublicationVenueType,
)
from destiny_sdk.identifiers import (
    DOIIdentifier,
    OpenAlexIdentifier,
    OtherIdentifier,
    PubMedIdentifier,
)
from destiny_sdk.references import ReferenceFileInput
from pydantic import ValidationError

from openalex_incremental_updater.models.destiny import (
    DataSource,
    DestinyOpenAlexWorkMetadata,
    convert_inverted_abstract,
    convert_openalex_to_destiny,
    get_destiny_openalex_work,
    is_valid_nonempty_string,
    map_openalex_source_type_to_venue_type,
    prepare_destiny_locations,
    prepare_destiny_pagination,
    strip_url_prefix,
)


def test_destiny_openalex_work_valid_from_valid_openalex_work_dict(
    openalex_work_dict: dict,
) -> None:
    expected_creation_date = openalex_work_dict.get("created_date")
    expected_update_date = (
        datetime.fromisoformat(openalex_work_dict.get("updated_date", ""))
        .date()
        .isoformat()
    )
    expected_publication_year = openalex_work_dict.get("publication_year")
    expected_openalex_id = openalex_work_dict["ids"]["openalex"].rsplit("/", 1)[-1]
    expected_abstract = convert_inverted_abstract(
        openalex_work_dict["abstract_inverted_index"]
    )
    expected_publication_year = 2025
    expected_pagination_dict = Pagination(**openalex_work_dict.get("biblio", {}))
    destiny_work = convert_openalex_to_destiny(openalex_work_dict)

    openalex_id = None
    for identifier in destiny_work.identifiers:
        if isinstance(identifier, OpenAlexIdentifier):
            openalex_id = identifier.identifier
            break

    abstract = None
    publication_year = None
    created_date = None
    updated_date = None
    pagination = None
    for enhancement in destiny_work.enhancements:
        content = enhancement.content
        if isinstance(content, AbstractContentEnhancement):
            abstract = content.abstract
        elif isinstance(content, BibliographicMetadataEnhancement):
            publication_year = content.publication_year
            created_date = str(content.created_date) if content.created_date else None
            updated_date = str(content.updated_date) if content.updated_date else None
            pagination = content.pagination if content.pagination else None

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
        created_date == expected_creation_date
    ), "Expect that the test created date is set correctly"
    assert (
        updated_date == expected_update_date
    ), "Expect that the test updated date is set correctly"
    assert (
        pagination == expected_pagination_dict
    ), "Expect that the test pagination is set correctly"


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
    Test that unexpected fields are ignored when creating an ReferenceFileInput object.

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
    openalex_id = None
    for identifier in work.identifiers:
        if isinstance(identifier, OpenAlexIdentifier):
            openalex_id = identifier.identifier
            break

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
    """Test that empty identifier fields are ignored when creating an ReferenceFileInput object."""
    expected_openalex_id = openalex_work_dict["ids"]["openalex"].rsplit("/", 1)[-1]
    invalid_openalex_work_dict = openalex_work_dict.copy()
    invalid_openalex_work_dict["ids"][missing_field] = missing_field_value

    work = convert_openalex_to_destiny(invalid_openalex_work_dict)

    openalex_id = None
    for identifier in work.identifiers:
        if isinstance(identifier, OpenAlexIdentifier):
            openalex_id = identifier.identifier
            break

    identifier_types = [identifier.identifier_type for identifier in work.identifiers]

    assert (
        openalex_id == expected_openalex_id
    ), "Expect that the test ID is set correctly"
    assert not hasattr(
        work, "an_unexpected_field"
    ), "Expect that the unexpected field is not set on the object"
    assert (
        missing_field not in identifier_types
    ), "Expect that the missing identifier field is not set on the object"


def test_get_destiny_openalex_work_success(
    openalex_work_dict: dict,
    destiny_openalex_work_metadata: DestinyOpenAlexWorkMetadata,
) -> None:
    """Test that the get_destiny_openalex_work function returns a ReferenceFileInput object."""
    correct_source_for_openalex_input = DataSource.OPEN_ALEX
    expected_openalex_id = openalex_work_dict["ids"]["openalex"].rsplit("/", 1)[-1]
    expected_abstract = "This is an example abstract"
    expected_abstract_process = "uninverted"

    work = get_destiny_openalex_work(
        destiny_openalex_work_metadata,
        openalex_work_dict,
        data_source=correct_source_for_openalex_input,
    )

    assert isinstance(
        work, ReferenceFileInput
    ), "Expect that the returned object is of type ReferenceFileInput"

    abstract_content = None
    for enhancement in work.enhancements:
        if isinstance(enhancement.content, AbstractContentEnhancement):
            abstract_content = enhancement.content
            break

    first_identifier = work.identifiers[0] if work.identifiers else None
    first_identifier_value = first_identifier.identifier if first_identifier else None

    assert (
        first_identifier_value == expected_openalex_id
    ), "Expect that the OpenAlex ID is set correctly in the identifiers"
    assert abstract_content is not None, "Abstract content should be present"
    assert (
        abstract_content.abstract == expected_abstract
    ), "Expect that the abstract is set correctly"
    assert (
        abstract_content.process.value == expected_abstract_process
    ), "Expect that the abstract process is set correctly"


def test_get_destiny_openalex_work_blank_abstract_from_openalex_input_with_incorrect_source(
    openalex_work_dict: dict,
    destiny_openalex_work_metadata: DestinyOpenAlexWorkMetadata,
) -> None:
    """
    Test that the get_destiny_openalex_work function returns a ReferenceFileInput object.

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

    work = get_destiny_openalex_work(
        destiny_openalex_work_metadata,
        openalex_work_dict,
        data_source=bad_source_for_openalex_input,
    )

    work_annotations = None
    work_locations = None
    for enhancement in work.enhancements:
        content = enhancement.content
        if isinstance(content, AnnotationEnhancement):
            work_annotations = content.annotations
        elif isinstance(content, LocationEnhancement):
            work_locations = content.locations

    assert isinstance(
        work, ReferenceFileInput
    ), "Expect that the returned object is of type ReferenceFileInput"

    first_identifier = work.identifiers[0] if work.identifiers else None
    first_identifier_value = first_identifier.identifier if first_identifier else None
    assert (
        first_identifier_value == expected_openalex_id
    ), "Expect that the OpenAlex ID is set correctly in the identifiers"

    assert work_annotations is not None, "Annotations should be present"
    assert (
        work_annotations[0].data == expected_annotations
    ), "Expect that the annotations are still set correctly in the case of no abstract"

    assert work_locations is not None, "Locations should be present"
    first_location = work_locations[0] if work_locations else None
    assert first_location is not None, "First location should be present"
    first_location_dict = {
        "is_oa": first_location.is_oa,
        "landing_page_url": str(first_location.landing_page_url)
        if first_location.landing_page_url
        else None,
        "extra": first_location.extra,
    }
    assert (
        first_location_dict == expected_locations
    ), "Expect that the locations are still set correctly in the case of no abstract"

    has_abstract = any(
        isinstance(enhancement.content, AbstractContentEnhancement)
        for enhancement in work.enhancements
    )
    assert not has_abstract, "Expect that the abstract is not set in the enhancements"


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
    Test that the pubmed identifier is parsed as an integer in ReferenceFileInput.

    All other identifiers should be parsed as strings.
    """
    test_openalex_work_dict = openalex_work_dict.copy()
    openalex_identifier = openalex_work_dict["ids"].get("openalex").rsplit("/", 1)[-1]
    doi_identifier = openalex_work_dict["ids"].get("doi")
    # DOIIdentifier strips https://doi.org/ prefix automatically
    expected_doi_identifier = doi_identifier.replace("https://doi.org/", "")
    test_pmid_identifier = "https://pubmed.ncbi.nlm.nih.gov/123456789"
    test_microsoft_academic_graph_identifier = "2222222222"
    test_pubmed_central_identifier = "3333333333"

    expected_resulting_pmid = test_pmid_identifier.rsplit("/", 1)[-1]

    test_openalex_work_dict["ids"]["pmid"] = test_pmid_identifier
    test_openalex_work_dict["ids"]["mag"] = test_microsoft_academic_graph_identifier
    test_openalex_work_dict["ids"]["pmcid"] = test_pubmed_central_identifier

    destiny_work = convert_openalex_to_destiny(test_openalex_work_dict)

    destiny_pubmed_identifier = None
    destiny_openalex_identifier = None
    destiny_doi_identifier = None
    destiny_microsoft_academic_graph_identifier = None
    destiny_pubmed_central_identifier = None

    for identifier in destiny_work.identifiers:
        if isinstance(identifier, PubMedIdentifier):
            destiny_pubmed_identifier = identifier
        elif isinstance(identifier, OpenAlexIdentifier):
            destiny_openalex_identifier = identifier
        elif isinstance(identifier, DOIIdentifier):
            destiny_doi_identifier = identifier
        elif isinstance(identifier, OtherIdentifier):
            if identifier.other_identifier_name == "Microsoft Academic Graph ID":
                destiny_microsoft_academic_graph_identifier = identifier
            elif identifier.other_identifier_name == "Pubmed Central ID":
                destiny_pubmed_central_identifier = identifier

    assert (
        destiny_openalex_identifier is not None
    ), "OpenAlex identifier should be found"
    assert destiny_doi_identifier is not None, "DOI identifier should be found"
    assert (
        destiny_microsoft_academic_graph_identifier is not None
    ), "MAG identifier should be found"
    assert (
        destiny_pubmed_central_identifier is not None
    ), "PMC identifier should be found"
    assert destiny_pubmed_identifier is not None, "PubMed identifier should be found"

    assert isinstance(
        destiny_openalex_identifier.identifier, str
    ), "Expect that openalex_id is a string"
    assert isinstance(
        destiny_doi_identifier.identifier, str
    ), "Expect that doi_id is a string"
    assert isinstance(
        destiny_microsoft_academic_graph_identifier.identifier, str
    ), "Expect that mag_id is a string"
    assert isinstance(
        destiny_pubmed_central_identifier.identifier, str
    ), "Expect that pubmed_central_id is a string"
    assert (
        destiny_openalex_identifier.identifier == openalex_identifier
    ), "Expect that openalex_id is parsed correctly"
    assert (
        destiny_doi_identifier.identifier == expected_doi_identifier
    ), "Expect that doi_id is parsed correctly"
    assert (
        destiny_microsoft_academic_graph_identifier.identifier
        == test_microsoft_academic_graph_identifier
    ), "Expect that mag_id is parsed correctly"
    assert (
        destiny_pubmed_central_identifier.identifier == test_pubmed_central_identifier
    ), "Expect that pubmed_central_id is parsed correctly"

    assert isinstance(
        destiny_pubmed_identifier.identifier, int
    ), "Expect that pubmed_id is an integer"
    assert destiny_pubmed_identifier.identifier == int(
        expected_resulting_pmid
    ), "Expect that pubmed_id is parsed correctly"


def test_pubmed_identifier_none_case_handled(
    openalex_work_dict: dict,
) -> None:
    """
    Test that the pubmed identifier is parsed as an integer in ReferenceFileInput.

    All other identifiers should be parsed as strings.
    """
    test_openalex_work_dict = openalex_work_dict.copy()
    openalex_identifier = openalex_work_dict["ids"].get("openalex").rsplit("/", 1)[-1]
    doi_identifier = openalex_work_dict["ids"].get("doi")
    # DOIIdentifier strips https://doi.org/ prefix automatically
    expected_doi_identifier = doi_identifier.replace("https://doi.org/", "")
    test_pmid_identifier = None

    test_openalex_work_dict["ids"]["pmid"] = test_pmid_identifier

    destiny_work = convert_openalex_to_destiny(test_openalex_work_dict)

    destiny_openalex_identifier = None
    destiny_doi_identifier = None

    for identifier in destiny_work.identifiers:
        if isinstance(identifier, OpenAlexIdentifier):
            destiny_openalex_identifier = identifier
        elif isinstance(identifier, DOIIdentifier):
            destiny_doi_identifier = identifier

    assert (
        destiny_openalex_identifier is not None
    ), "OpenAlex identifier should be found"
    assert destiny_doi_identifier is not None, "DOI identifier should be found"

    assert isinstance(
        destiny_openalex_identifier.identifier, str
    ), "Expect that openalex_id is a string"
    assert isinstance(
        destiny_doi_identifier.identifier, str
    ), "Expect that doi_id is a string"
    assert (
        destiny_openalex_identifier.identifier == openalex_identifier
    ), "Expect that openalex_id is parsed correctly"
    assert (
        destiny_doi_identifier.identifier == expected_doi_identifier
    ), "Expect that doi_id is parsed correctly"

    # Pubmed ID shouldn't be present if it is None
    has_pubmed = any(
        isinstance(identifier, PubMedIdentifier)
        for identifier in destiny_work.identifiers
    )
    assert not has_pubmed, "Expect that pm_id is not present if it is None"


def test_pubmed_central_identifier_masquerading_as_pubmed_id(
    openalex_work_dict: dict,
) -> None:
    """
    Test that the pubmed identifier is parsed as an integer in ReferenceFileInput.

    All other identifiers should be parsed as strings.
    """
    test_openalex_work_dict = openalex_work_dict.copy()
    openalex_identifier = openalex_work_dict["ids"].get("openalex").rsplit("/", 1)[-1]
    doi_identifier = openalex_work_dict["ids"].get("doi")
    # DOIIdentifier strips https://doi.org/ prefix automatically
    expected_doi_identifier = doi_identifier.replace("https://doi.org/", "")
    test_pmid_identifier = "PMCID123456789"

    test_openalex_work_dict["ids"]["pmid"] = test_pmid_identifier

    destiny_work = convert_openalex_to_destiny(test_openalex_work_dict)

    destiny_openalex_identifier = None
    destiny_doi_identifier = None

    for identifier in destiny_work.identifiers:
        if isinstance(identifier, OpenAlexIdentifier):
            destiny_openalex_identifier = identifier
        elif isinstance(identifier, DOIIdentifier):
            destiny_doi_identifier = identifier

    assert (
        destiny_openalex_identifier is not None
    ), "OpenAlex identifier should be found"
    assert destiny_doi_identifier is not None, "DOI identifier should be found"

    assert isinstance(
        destiny_openalex_identifier.identifier, str
    ), "Expect that openalex_id is a string"
    assert isinstance(
        destiny_doi_identifier.identifier, str
    ), "Expect that doi_id is a string"
    assert (
        destiny_openalex_identifier.identifier == openalex_identifier
    ), "Expect that openalex_id is parsed correctly"
    assert (
        destiny_doi_identifier.identifier == expected_doi_identifier
    ), "Expect that doi_id is parsed correctly"

    # Pubmed ID shouldn't be present if it is None
    has_pubmed = any(
        isinstance(identifier, PubMedIdentifier)
        for identifier in destiny_work.identifiers
    )
    assert not has_pubmed, "Expect that pm_id is not present if it is None"


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


@pytest.mark.parametrize(
    "invalid_url",
    [
        "www.example.org/file.pdf",  # missing scheme (W12561570)
        "archive.example.org/handle/123",  # bare domain (W915423)
        "https://",  # empty scheme (W652607350)
        "http://[dl.example.pl/Content/123",  # invalid bracket (W7065886528)
        "132.248.52.100:8080/path",  # IP:port without scheme (W22238915)
        "not-a-url",  # completely invalid
    ],
)
def test_prepare_destiny_locations_skips_invalid_urls(invalid_url: str) -> None:
    """Test that invalid landing_page_url values are skipped without crashing."""
    metadata = DestinyOpenAlexWorkMetadata(
        openalex_id="W1234567890",  # required identifier
        locations=[
            {"landing_page_url": invalid_url, "is_oa": False},
        ],
        processor_version="test",
    )
    locations = prepare_destiny_locations(metadata)
    assert len(locations) == 0, f"Expected invalid URL {invalid_url!r} to be skipped"


def test_prepare_destiny_locations_preserves_valid_locations_when_one_invalid() -> None:
    """Test that valid locations are preserved when one location has invalid URL."""
    valid_urls = [
        "https://valid.example.com/paper.pdf",
        "https://another-valid.org/doc",
    ]
    invalid_urls = [
        "www.invalid-no-scheme.org/file.pdf",
    ]
    metadata = DestinyOpenAlexWorkMetadata(
        openalex_id="W1234567890",  # required identifier
        locations=[
            {"landing_page_url": valid_urls[0], "is_oa": True},
            {"landing_page_url": invalid_urls[0], "is_oa": False},
            {"landing_page_url": valid_urls[1], "is_oa": True},
        ],
        processor_version="test",
    )
    locations = prepare_destiny_locations(metadata)
    assert len(locations) == len(valid_urls), "Only valid locations should be kept"
    result_urls = [str(loc.landing_page_url) for loc in locations]
    for url in valid_urls:
        assert url in result_urls


def test_prepare_destiny_pagination_success_pagination_available(
    destiny_openalex_work_metadata: DestinyOpenAlexWorkMetadata,
) -> None:
    """Test the prepare_destiny_pagination function."""
    pagination = prepare_destiny_pagination(destiny_openalex_work_metadata)

    assert isinstance(
        pagination, Pagination
    ), "Expect that the returned object is of type Pagination"
    assert pagination.first_page == destiny_openalex_work_metadata.pagination.get(
        "first_page"
    ), "Expect that the first_page is set correctly"
    assert pagination.last_page == destiny_openalex_work_metadata.pagination.get(
        "last_page"
    ), "Expect that the last_page is set correctly"
    assert pagination.volume == destiny_openalex_work_metadata.pagination.get(
        "volume"
    ), "Expect that the volume is set correctly"
    assert pagination.issue == destiny_openalex_work_metadata.pagination.get(
        "issue"
    ), "Expect that the issue is set correctly"


def test_prepare_destiny_pagination_success_pagination_unavailable(
    destiny_openalex_work_metadata: DestinyOpenAlexWorkMetadata,
) -> None:
    """Test the prepare_destiny_pagination function."""
    work_metadata = copy.deepcopy(destiny_openalex_work_metadata)
    work_metadata.pagination = {}
    pagination = prepare_destiny_pagination(work_metadata)

    assert isinstance(
        pagination, Pagination
    ), "Expect that the returned object is of type Pagination"
    assert all(
        value is None
        for value in [
            pagination.first_page,
            pagination.last_page,
            pagination.volume,
            pagination.issue,
        ]
    ), "Expect that all pagination fields are None when pagination data is unavailable"


def test_is_xpac_annotation_created_when_true(
    openalex_work_dict: dict,
) -> None:
    """Test that is_xpac annotation is created when is_xpac is True."""
    test_work_dict = openalex_work_dict.copy()
    test_work_dict["is_xpac"] = True

    destiny_work = convert_openalex_to_destiny(test_work_dict)

    # Find the annotation enhancement
    is_xpac_annotation = None
    for enhancement in destiny_work.enhancements:
        if isinstance(enhancement.content, AnnotationEnhancement):
            for annotation in enhancement.content.annotations:
                if annotation.label == "is_xpac":
                    is_xpac_annotation = annotation
                    break

    assert is_xpac_annotation is not None, "is_xpac annotation should be present"
    assert is_xpac_annotation.scheme == "openalex", "Scheme should be 'openalex'"
    assert is_xpac_annotation.value is True, "Value should be True"


@pytest.mark.parametrize("is_xpac_value", [False, None])
def test_is_xpac_annotation_not_created_when_false_or_none(
    openalex_work_dict: dict,
    *,
    is_xpac_value: bool | None,
) -> None:
    """Test that is_xpac annotation is not created when is_xpac is False or None."""
    test_work_dict = openalex_work_dict.copy()
    test_work_dict["is_xpac"] = is_xpac_value

    destiny_work = convert_openalex_to_destiny(test_work_dict)

    # Collect all annotation labels and verify is_xpac is not among them
    annotation_labels = [
        annotation.label
        for enhancement in destiny_work.enhancements
        if isinstance(enhancement.content, AnnotationEnhancement)
        for annotation in enhancement.content.annotations
    ]
    assert (
        "is_xpac" not in annotation_labels
    ), f"is_xpac annotation should not be present when is_xpac is {is_xpac_value}"


@pytest.mark.parametrize(
    ("source_type", "expected_venue_type"),
    [
        ("journal", PublicationVenueType.JOURNAL),
        ("repository", PublicationVenueType.REPOSITORY),
        ("conference", PublicationVenueType.CONFERENCE),
        ("ebook platform", PublicationVenueType.EBOOK_PLATFORM),
        ("book series", PublicationVenueType.BOOK_SERIES),
        ("metadata", PublicationVenueType.OTHER),
        ("unknown_type", PublicationVenueType.OTHER),
        (None, PublicationVenueType.OTHER),
        ("", PublicationVenueType.OTHER),
    ],
)
def test_map_openalex_source_type_to_publication_venue_type(
    source_type: str | None, expected_venue_type: PublicationVenueType
) -> None:
    """Test that OpenAlex source types are correctly mapped to DESTINY PublicationVenueType."""
    result = map_openalex_source_type_to_venue_type(source_type)
    assert (
        result == expected_venue_type
    ), f"Expected {expected_venue_type} for {source_type!r}"


def test_destiny_openalex_work_with_publication_venue(
    openalex_work_dict: dict,
) -> None:
    """Test that convert_openalex_to_destiny includes publication_venue in bibliographic metadata."""
    destiny_work = convert_openalex_to_destiny(openalex_work_dict)

    # Find the bibliographic enhancement
    publication_venue = None
    for enhancement in destiny_work.enhancements:
        if isinstance(enhancement.content, BibliographicMetadataEnhancement):
            publication_venue = enhancement.content.publication_venue
            break

    assert publication_venue is not None, "Publication venue should be present"
    assert isinstance(publication_venue, PublicationVenue)
    assert publication_venue.display_name == "Test source"
    assert publication_venue.venue_type == PublicationVenueType.JOURNAL
    assert publication_venue.issn == ["1234-5678"]
    assert publication_venue.issn_l == "1234-5678"
    assert publication_venue.host_organization_name == "Test host organization"


def test_destiny_openalex_work_no_venue_when_no_primary_location(
    openalex_work_dict: dict,
) -> None:
    """Test that publication_venue is None when primary_location is missing."""
    test_work_dict = openalex_work_dict.copy()
    test_work_dict["primary_location"] = None

    destiny_work = convert_openalex_to_destiny(test_work_dict)

    # Find the bibliographic enhancement
    publication_venue = None
    for enhancement in destiny_work.enhancements:
        if isinstance(enhancement.content, BibliographicMetadataEnhancement):
            publication_venue = enhancement.content.publication_venue
            break

    assert (
        publication_venue is None
    ), "Publication venue should be None when no primary_location"
