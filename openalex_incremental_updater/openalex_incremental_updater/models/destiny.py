"""Models associated with references."""

from enum import StrEnum
from typing import Self

from destiny_sdk.enhancements import (
    AbstractContentEnhancement,
    AbstractProcessType,
    AnnotationEnhancement,
    AuthorPosition,
    Authorship,
    BibliographicMetadataEnhancement,
    BooleanAnnotation,
    EnhancementFileInput,
    Location,
    LocationEnhancement,
    Pagination,
)
from destiny_sdk.identifiers import (
    DOIIdentifier,
    ExternalIdentifier,
    OpenAlexIdentifier,
    OtherIdentifier,
    PubMedIdentifier,
)
from destiny_sdk.references import ReferenceFileInput
from destiny_sdk.visibility import Visibility
from loguru import logger
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError, model_validator


class UrlModel(BaseModel):
    """
    A model for validating URLs.

    This model is used to validate URLs in the `ExternalIdentifier` class.
    It ensures that the URL is a valid HTTP or HTTPS URL.
    """

    url: AnyHttpUrl = Field(
        description="A valid HTTP or HTTPS URL.",
    )


class DataSource(StrEnum):
    """
    The source of the data.

    This is used to identify the source of the data in the `ExternalIdentifier`
    class.
    **Allowed values**:
    - `openalex`: The OpenAlex data source.
    - `solr`: The Solr data source.
    """

    OPEN_ALEX = "openalex"
    SOLR = "pik-solr"


class DestinyOpenAlexWorkMetadata(BaseModel):
    """
    Metadata for a Destiny OpenAlex work.

    This class is used to validate and structure the metadata for a work.
    """

    is_retracted: bool = Field(
        default=False,
        description="Indicates whether the work has been retracted.",
    )
    openalex_id: str | None = Field(
        default=None,
        description="The OpenAlex ID of the work.",
    )
    doi: str | None = Field(
        default=None,
        description="The DOI of the work.",
    )
    microsoft_academic_graph: str | None = Field(
        default=None,
        description="The Microsoft Academic Graph ID of the work.",
    )
    pubmed_id: int | None = Field(
        default=None,
        description="The PubMed ID of the work.",
    )
    pubmed_central_id: str | None = Field(
        default=None,
        description="The PubMed Central ID of the work.",
    )
    authorships_dict: list[dict] | None = Field(
        default=None,
        description="A list of authorships for the work.",
    )
    host_organisation_name: str | None = Field(
        default=None,
        description="The name of the host organization for the work.",
    )
    locations: list[dict] | None = Field(
        default=None,
        description="A list of locations for the work.",
    )
    topics: list[dict] | None = Field(
        default=None,
        description="A list of topics for the work.",
    )
    pagination: dict | None = Field(
        default=None,
        description="Pagination details for the work.",
    )
    processor_version: str = Field(
        default="initial_openalex_import",
        description="The version of the processor that created this metadata.",
    )

    @model_validator(mode="after")
    def validate_identifiers(self) -> Self:
        """
        Validate the identifiers of the work.

        This method checks that the metadata contains at least one identifier of type DOI, PM_ID, or OPEN_ALEX.

        Raises:
            ValueError: If the identifiers list is empty or does not contain a
                valid identifier type.

        Returns:
            self: The validated instance of DestinyOpenAlexWork.

        """
        if not self.openalex_id and not self.doi and not self.pubmed_id:
            error_message = (
                "At least one identifier must be of type DOI, PM_ID, or OPEN_ALEX."
            )
            raise ValueError(error_message)
        return self


def strip_url_prefix(url: AnyHttpUrl | None) -> str | None:
    """
    Strip the URL prefix from a given URL.

    Args:
        url (AnyHttpUrl | None): The URL to strip.

    Returns:
        str | None: The stripped URL or None if the input is None.

    """
    if url is None:
        return None

    try:
        validated_url_model = UrlModel(url=url)
        validated_url = str(validated_url_model.url)
        return validated_url.rsplit("/", 1)[-1]
    except ValidationError:
        return str(url)


def convert_openalex_to_destiny(
    openalex_work: dict,
) -> ReferenceFileInput:
    """
    Convert OpenAlex works to a Destiny OpenAlex work.

    Args:
        openalex_work (list[dict]): The OpenAlex works to convert.

    Returns:
        ReferenceFileInput: The converted Destiny OpenAlex work.

    """
    ids_dict = openalex_work.get("ids") if openalex_work.get("ids") else None
    authorships_dict = openalex_work.get("authorships")
    primary_location = openalex_work.get("primary_location")
    source = primary_location.get("source") if primary_location else None
    host_organisation_name = source.get("host_organization_name") if source else None
    pagination = openalex_work.get("biblio") if openalex_work.get("biblio") else None

    locations = openalex_work.get("locations")
    topics = openalex_work.get("topics")
    processor_version = "initial_openalex_import"
    if ids_dict:
        doi = ids_dict.get("doi")
        openalex_id = ids_dict.get("openalex")
        microsoft_academic_graph = ids_dict.get("mag")
        pubmed_id_candidate = ids_dict.get("pmid")
        pubmed_central_id = ids_dict.get("pmcid")
    else:
        doi = None
        openalex_id = None
        microsoft_academic_graph = None
        pubmed_id_candidate = None
        pubmed_central_id = None

    openalex_id = strip_url_prefix(openalex_id)

    pubmed_id_string = strip_url_prefix(pubmed_id_candidate)

    if pubmed_id_string is not None:
        try:
            pubmed_id = int(pubmed_id_string)
        except ValueError as invalid_pmid:
            logger.error(
                f"Invalid PubMed ID: {pubmed_id_string} for DOI {doi}. Error: {invalid_pmid}"
            )
            pubmed_id = None
    else:
        pubmed_id = None

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
        pagination=pagination,
        processor_version=processor_version,
    )

    return get_destiny_openalex_work(
        work_metadata, openalex_work, data_source=DataSource.OPEN_ALEX
    )


def create_core_destiny_openalex_work(
    metadata: DestinyOpenAlexWorkMetadata,
    destiny_work_identifiers: list[ExternalIdentifier],
    data_source: DataSource,
    source_document: dict,
) -> ReferenceFileInput:
    """
    Create a core ReferenceFileInput object from metadata and identifiers.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): DestinyOpenAlexWorkMetadata object containing metadata.
        destiny_work_identifiers (list[ExternalIdentifier]): List of identifiers for the work.
        data_source (DataSource): Source of the metadata.
        source_document (dict | None, optional): Source document containing the data of interest.

    Returns:
        ReferenceFileInput: An instance of ReferenceFileInput populated with the metadata and core identifiers.

    """
    pagination_data = prepare_destiny_pagination(metadata)
    bibliographic_enhancement = BibliographicMetadataEnhancement(
        title=source_document.get("title"),
        cited_by_count=source_document.get("cited_by_count"),
        created_date=source_document.get("created_date"),
        publication_date=source_document.get("publication_date"),
        publication_year=source_document.get("publication_year"),
        publisher=metadata.host_organisation_name,
        pagination=pagination_data,
    )

    return ReferenceFileInput(
        visibility=Visibility.HIDDEN if metadata.is_retracted else Visibility.PUBLIC,
        identifiers=destiny_work_identifiers,
        enhancements=[
            EnhancementFileInput(
                source=data_source.value,
                visibility=Visibility.RESTRICTED
                if metadata.is_retracted
                else Visibility.PUBLIC,
                processor_version=metadata.processor_version,
                content=bibliographic_enhancement,
            ),
        ],
    )


def prepare_destiny_identifiers(
    metadata: DestinyOpenAlexWorkMetadata,
) -> list[ExternalIdentifier]:
    """
    Prepare a list of identifiers for the Destiny OpenAlex work.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): The metadata containing identifiers.

    Returns:
        list[ExternalIdentifier]: A list of ExternalIdentifier objects.

    """
    destiny_work_identifiers: list[ExternalIdentifier] = []

    if is_valid_nonempty_string(metadata.openalex_id):
        destiny_work_identifiers.append(
            OpenAlexIdentifier(identifier=metadata.openalex_id)
        )
    if is_valid_nonempty_string(metadata.doi):
        destiny_work_identifiers.append(DOIIdentifier(identifier=metadata.doi))
    if metadata.pubmed_id is not None:
        destiny_work_identifiers.append(PubMedIdentifier(identifier=metadata.pubmed_id))

    return destiny_work_identifiers


def prepare_destiny_authorships(
    metadata: DestinyOpenAlexWorkMetadata,
) -> list[Authorship]:
    """
    Prepare a list of authorships for the Destiny OpenAlex work.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): The metadata containing authorships.

    Returns:
        list[Authorship]: A list of Authorship objects.

    """
    authorships: list[Authorship] = []
    for author in metadata.authorships_dict or []:
        author_data = author.get("author") or {}
        display_name = author_data.get("display_name", "")
        orcid = author_data.get("orcid", None)
        position_str = author.get("author_position", "")

        if not display_name or not position_str:
            logger.warning(
                f"Skipping authorship with missing data: display_name={display_name!r}, position={position_str!r}"
            )
            continue

        try:
            position = AuthorPosition(position_str)
        except ValueError:
            logger.warning(
                f"Skipping authorship with invalid position: {position_str!r}"
            )
            continue

        authorships.append(
            Authorship(
                display_name=display_name,
                orcid=orcid,
                position=position,
            )
        )
    return authorships


def prepare_destiny_locations(metadata: DestinyOpenAlexWorkMetadata) -> list[Location]:
    """
    Prepare a list of locations for the Destiny OpenAlex work.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): The metadata containing locations.

    Returns:
        list[Location]: A list of Location objects.

    """
    locations: list[Location] = []
    for location in metadata.locations or []:
        is_oa = location.get("is_oa", False)
        version = location.get("version")
        landing_page_url = location.get("landing_page_url")
        pdf_url = location.get("pdf_url")
        license_val = location.get("license")
        extra = location.get("source")

        loc = Location(
            is_oa=is_oa,
            version=version if is_valid_nonempty_string(version) else None,
            landing_page_url=landing_page_url
            if is_valid_nonempty_string(landing_page_url)
            else None,
            pdf_url=pdf_url if is_valid_nonempty_string(pdf_url) else None,
            license=license_val if is_valid_nonempty_string(license_val) else None,
            extra=extra if extra else None,
        )
        locations.append(loc)
    return locations


def prepare_destiny_pagination(
    metadata: DestinyOpenAlexWorkMetadata,
) -> Pagination:
    """
    Prepare a list of pagination details for the Destiny OpenAlex work.

    Paginations map to OpenAlex's `Work.biblio` object.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): The metadata containing pagination details.

    Returns:
        Pagination: A Pagination object with pagination
            information for journal articles.

    """
    pagination_dict = metadata.pagination or {}
    volume = pagination_dict.get("volume", None)
    issue = pagination_dict.get("issue", None)
    first_page = pagination_dict.get("first_page", None)
    last_page = pagination_dict.get("last_page", None)

    return Pagination(
        first_page=first_page if is_valid_nonempty_string(first_page) else None,
        issue=issue if is_valid_nonempty_string(issue) else None,
        last_page=last_page if is_valid_nonempty_string(last_page) else None,
        volume=volume if is_valid_nonempty_string(volume) else None,
    )


def prepare_destiny_annotations(
    metadata: DestinyOpenAlexWorkMetadata,
) -> list[BooleanAnnotation]:
    """
    Prepare a list of annotations for the Destiny OpenAlex work.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): The metadata containing annotations.

    Returns:
        list[BooleanAnnotation]: A list of BooleanAnnotation objects.

    """
    annotations: list[BooleanAnnotation] = []
    for annotation in metadata.topics or []:
        label = annotation.get("display_name", "")
        data = annotation
        if not is_valid_nonempty_string(label):
            continue
        annotations.append(
            BooleanAnnotation(
                scheme="openalex:topic",
                value=True,
                label=label,
                data=data,
            )
        )
    return annotations


def prepare_destiny_work_abstract_enhancement(
    data_source: DataSource,
    source_document: dict,
) -> AbstractContentEnhancement | None:
    """
    Prepare the abstract content for a Destiny OpenAlex work.

    This function creates the abstract content based on the source and source document.

    Args:
        data_source (DataSource): The source of the data coming in.
        source_document (dict): The source document containing the abstract data.

    Returns:
        AbstractContentEnhancement | None: The abstract enhancement or None if no abstract.

    """
    if data_source == DataSource.OPEN_ALEX:
        abstract_text = convert_inverted_abstract(
            source_document.get("abstract_inverted_index", "")
        )
        process = AbstractProcessType.UNINVERTED
    else:
        abstract_text = source_document.get("abstract", "")
        process = AbstractProcessType.OTHER

    if not is_valid_nonempty_string(abstract_text):
        return None

    return AbstractContentEnhancement(
        process=process,
        abstract=abstract_text,
    )


def get_destiny_openalex_work(
    metadata: DestinyOpenAlexWorkMetadata,
    source_document: dict,
    data_source: DataSource = DataSource.OPEN_ALEX,
) -> ReferenceFileInput:
    """
    Get a ReferenceFileInput object from provided metadata.

    Args:
        metadata (dict): A dictionary containing metadata for the OpenAlex work.
        source_document (dict): The source document containing the data of interest.
            This could be dervied from an OpenAlex work, Solr or similar.
        data_source (DataSource, optional): The source of the metadata, default is DataSource.OPEN_ALEX.

    Returns:
        ReferenceFileInput: An instance of ReferenceFileInput populated with the metadata.

    """
    destiny_work_identifiers = prepare_destiny_identifiers(metadata)
    destiny_work_authors = prepare_destiny_authorships(metadata)
    destiny_work_locations = prepare_destiny_locations(metadata)
    destiny_work_annotations = prepare_destiny_annotations(metadata)
    destiny_work_abstract = prepare_destiny_work_abstract_enhancement(
        data_source, source_document
    )

    core_destiny_work = create_core_destiny_openalex_work(
        metadata=metadata,
        destiny_work_identifiers=destiny_work_identifiers,
        data_source=data_source,
        source_document=source_document,
    )

    visibility = Visibility.RESTRICTED if metadata.is_retracted else Visibility.PUBLIC

    if destiny_work_authors:
        bibliographic_content = core_destiny_work.enhancements[0].content
        if isinstance(bibliographic_content, BibliographicMetadataEnhancement):
            bibliographic_content.authorship = destiny_work_authors

    if destiny_work_abstract:
        core_destiny_work.enhancements.append(
            EnhancementFileInput(
                source=data_source.value,
                visibility=visibility,
                processor_version=metadata.processor_version,
                content=destiny_work_abstract,
            )
        )

    if destiny_work_locations:
        core_destiny_work.enhancements.append(
            EnhancementFileInput(
                source=data_source.value,
                visibility=visibility,
                processor_version=metadata.processor_version,
                content=LocationEnhancement(locations=destiny_work_locations),
            )
        )

    if destiny_work_annotations:
        core_destiny_work.enhancements.append(
            EnhancementFileInput(
                source=data_source.value,
                visibility=visibility,
                processor_version=metadata.processor_version,
                content=AnnotationEnhancement(annotations=destiny_work_annotations),
            ),
        )

    if is_valid_nonempty_string(metadata.microsoft_academic_graph):
        core_destiny_work.identifiers.append(
            OtherIdentifier(
                identifier=metadata.microsoft_academic_graph,
                other_identifier_name="Microsoft Academic Graph ID",
            )
        )
    if is_valid_nonempty_string(metadata.pubmed_central_id):
        core_destiny_work.identifiers.append(
            OtherIdentifier(
                identifier=metadata.pubmed_central_id,
                other_identifier_name="Pubmed Central ID",
            )
        )
    return core_destiny_work


def is_valid_nonempty_string(value: str | None) -> bool:
    """
    Check if a string is valid (not None and not empty).

    Args:
        value (str | None): The string to check.

    Returns:
        bool: True if the string is valid, False otherwise.

    """
    if value is None:
        return value is not None

    if not isinstance(value, str):
        return False

    value_not_null = value.strip().lower() != "null"
    value_not_empty_string = value.strip() != ""
    value_not_strnone = value.lower() != "none"
    return (
        value is not None
        and value_not_null
        and value_not_empty_string
        and value_not_strnone
    )


def convert_inverted_abstract(
    inverted_abstract: dict[str, list[int]] | None,
) -> str:
    """
    Convert an inverted abstract to a human-readable string.

    Args:
        inverted_abstract (dict): The inverted abstract to convert.

    Returns:
        str: The human-readable string.

    """
    if not inverted_abstract:
        return ""
    word_position_map = {}
    for word, positions in inverted_abstract.items():
        for position in positions:
            word_position_map[position] = word
    ordered_text = [word for _, word in sorted(word_position_map.items())]

    return " ".join(ordered_text)
