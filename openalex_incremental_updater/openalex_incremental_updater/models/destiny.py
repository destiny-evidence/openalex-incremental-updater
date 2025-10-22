"""Models associated with references."""

from enum import StrEnum
from typing import Literal, Self

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


class Visibility(StrEnum):
    """
    The visibility of a data element in the repository.

    This is used to manage whether information should be publicly available or
    restricted (generally due to copyright constraints from publishers).

    TODO: Implement data governance layer to manage this.

    **Allowed values**:

    - `public`: Visible to the general public without authentication.
    - `restricted`: Requires authentication to be visible.
    - `hidden`: Is not visible, but may be passed to data mining processes.
    """

    PUBLIC = "public"
    RESTRICTED = "restricted"
    HIDDEN = "hidden"


class ExternalIdentifierType(StrEnum):
    """
    The type of identifier used to identify a reference.

    This is used to identify the type of identifier used in the `ExternalIdentifier`
    class.
    **Allowed values**:
    - `doi`: A DOI (Digital Object Identifier) which is a unique identifier for a
        document. The identifier itself is a string.
    - `pmid`: A PubMed ID which is a unique identifier for a document in PubMed. The identifier is an integer.
    - `openalex`: An OpenAlex ID which is a unique identifier for a document in
        OpenAlex. The identifier is a string.
    - `other`: Any other identifier not defined. The identifier is a string.
    """

    DOI = "doi"
    PM_ID = "pm_id"
    OPEN_ALEX = "open_alex"
    OTHER = "other"


class EnhancementType(StrEnum):
    """
    The type of enhancement.

    This is used to identify the type of enhancement in the `Enhancement` class.

    **Allowed values**:
    - `bibliographic`: Bibliographic metadata.
    - `abstract`: The abstract of a reference.
    - `annotation`: A free-form enhancement for tagging with labels.
    - `locations`: Locations where the reference can be found.
    """

    BIBLIOGRAPHIC = "bibliographic"
    ABSTRACT = "abstract"
    ANNOTATION = "annotation"
    LOCATION = "location"


class AbstractProcessType(StrEnum):
    """
    The process used to acquire the abstract.

    **Allowed values**:
    - `uninverted`
    - `closed_api`
    - `other`
    """

    UNINVERTED = "uninverted"
    CLOSED_API = "closed_api"
    OTHER = "other"


class AbstractContentEnhancement(BaseModel):
    """
    An enhancement which is specific to the abstract of a reference.

    This is separate from the `BibliographicMetadata` for two reasons:

    1. Abstracts are increasingly missing from sources like OpenAlex, and may be
    backfilled from other sources, without the bibliographic metadata.
    2. They are also subject to copyright limitations in ways which metadata are
    not, and thus need separate visibility controls.
    """

    enhancement_type: Literal[EnhancementType.ABSTRACT] = EnhancementType.ABSTRACT
    process: AbstractProcessType = Field(
        description="The process used to acquire the abstract."
    )
    abstract: str = Field(description="The abstract of the reference.")


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


class DestinyOpenAlexWork(BaseModel):
    """Schema representing a work in the Destiny system."""

    visibility: Visibility = Field(
        default=Visibility.PUBLIC,
        description="The visibility of the work in the Destiny system.",
    )
    identifiers: list[dict] = Field(
        default_factory=list[dict],
        description="A list of `ExternalIdentifiers` for the Reference",
    )
    enhancements: list[dict] = Field(
        default_factory=list[dict],
        description="A list of enhancements for the reference",
    )

    @model_validator(mode="after")
    def validate_identifiers(self) -> Self:
        """
        Validate the identifiers of the work.

        This method checks that the identifiers list is not empty and that it
        contains at least one identifier of type DOI, PM_ID, or OPEN_ALEX.

        Raises:
            ValueError: If the identifiers list is empty or does not contain a
                valid identifier type.

        Returns:
            self: The validated instance of DestinyOpenAlexWork.

        """
        if not self.identifiers:
            error_message = "Identifiers list cannot be empty."
            raise ValueError(error_message)
        if not any(
            identifier.get("identifier")
            if identifier["identifier_type"]
            in [
                ExternalIdentifierType.DOI.value,
                ExternalIdentifierType.PM_ID.value,
                ExternalIdentifierType.OPEN_ALEX.value,
            ]
            else False
            for identifier in self.identifiers
        ):
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
) -> DestinyOpenAlexWork:
    """
    Convert OpenAlex works to a Destiny OpenAlex work.

    Args:
        openalex_work (list[dict]): The OpenAlex works to convert.

    Returns:
        DestinyOpenAlexWork: The converted Destiny OpenAlex work.

    """
    ids_dict = openalex_work.get("ids") if openalex_work.get("ids") else None
    authorships_dict = openalex_work.get("authorships")
    primary_location = openalex_work.get("primary_location")
    source = primary_location.get("source") if primary_location else None
    host_organisation_name = source.get("host_organization_name") if source else None

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
        processor_version=processor_version,
    )

    return get_destiny_openalex_work(
        work_metadata, openalex_work, data_source=DataSource.OPEN_ALEX
    )


def create_core_destiny_openalex_work(
    metadata: DestinyOpenAlexWorkMetadata,
    destiny_work_identifiers: list[dict],
    data_source: DataSource,
    source_document: dict,
) -> DestinyOpenAlexWork:
    """
    Create a core DestinyOpenAlexWork object from metadata and identifiers.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): DestinyOpenAlexWorkMetadata object containing metadata.
        destiny_work_identifiers (list[dict]): List of identifiers for the work.
        data_source (DataSource): Source of the metadata.
        source_document (dict | None, optional): Source document containing the data of interest.

    Returns:
        DestinyOpenAlexWork: An instance of DestinyOpenAlexWork populated with the metadata and core identifiers.

    """
    return DestinyOpenAlexWork(
        visibility=Visibility.HIDDEN if metadata.is_retracted else Visibility.PUBLIC,
        identifiers=destiny_work_identifiers,
        enhancements=[
            {
                "source": data_source.value,
                "visibility": Visibility.RESTRICTED.value
                if metadata.is_retracted
                else Visibility.PUBLIC.value,
                "processor_version": metadata.processor_version,
                "content": {
                    "enhancement_type": EnhancementType.BIBLIOGRAPHIC.value,
                    "title": source_document.get("title"),
                    "cited_by_count": source_document.get("cited_by_count"),
                    "created_date": source_document.get("created_date"),
                    "publication_date": source_document.get("publication_date"),
                    "publication_year": source_document.get("publication_year"),
                    "publisher": metadata.host_organisation_name,
                },
            },
        ],
    )


def prepare_destiny_identifiers(metadata: DestinyOpenAlexWorkMetadata) -> list[dict]:
    """
    Prepare a list of identifiers for the Destiny OpenAlex work.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): The metadata containing identifiers.

    Returns:
        list[dict]: A list of dictionaries containing identifier type and value.

    """
    destiny_work_identifiers = [
        {
            "identifier_type": ExternalIdentifierType.OPEN_ALEX.value,
            "identifier": metadata.openalex_id,
        }
    ]  # type: list[dict]
    if is_valid_nonempty_string(metadata.doi):
        destiny_work_identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.DOI.value,
                "identifier": metadata.doi,
            }
        )
    if metadata.pubmed_id is not None:
        destiny_work_identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.PM_ID.value,
                "identifier": metadata.pubmed_id,
            }
        )

    return destiny_work_identifiers


def prepare_destiny_authorships(metadata: DestinyOpenAlexWorkMetadata) -> list[dict]:
    """
    Prepare a list of authorships for the Destiny OpenAlex work.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): The metadata containing authorships.

    Returns:
        list[dict]: A list of dictionaries containing authorship information.

    """
    return [
        {
            "display_name": author["author"].get("display_name", "")
            if author["author"]
            else "",
            "orcid": author["author"].get("orcid", "") if author["author"] else "",
            "position": author.get("author_position", "") if author else "",
        }
        for author in metadata.authorships_dict or {}
    ]


def prepare_destiny_locations(metadata: DestinyOpenAlexWorkMetadata) -> list[dict]:
    """
    Prepare a list of locations for the Destiny OpenAlex work.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): The metadata containing locations.

    Returns:
        list[dict]: A list of dictionaries containing location information.

    """
    return [
        {
            key: value
            for key, value in {
                "is_oa": location.get("is_oa", False),
                "version": location.get("version", ""),
                "landing_page_url": location.get("landing_page_url", ""),
                "pdf_url": location.get("pdf_url", ""),
                "license": location.get("license", ""),
                "extra": location.get("source", {}),
            }.items()
            if is_valid_nonempty_string(str(value))
        }
        for location in metadata.locations or {}
    ]


def prepare_destiny_annotations(metadata: DestinyOpenAlexWorkMetadata) -> list[dict]:
    """
    Prepare a list of annotations for the Destiny OpenAlex work.

    Args:
        metadata (DestinyOpenAlexWorkMetadata): The metadata containing annotations.

    Returns:
        list[dict]: A list of dictionaries containing annotation information.

    """
    annotation_content = []  # type: list[dict]
    for annotation in metadata.topics or {}:
        label = annotation.get("display_name", "")
        data = annotation
        label_valid = is_valid_nonempty_string(label)
        data_valid = bool(data)
        if not label_valid and not data_valid:
            annotation_content.append({})
        else:
            annotation_content.append(
                {
                    "annotation_type": "boolean",
                    "scheme": "openalex:topic",
                    "value": True,
                    "label": label,
                    "data": data,
                }
            )
    return annotation_content


def prepare_destiny_work_abstract_annotation(
    data_source: DataSource,
    source_document: dict,
) -> dict:
    """
    Prepare the abstract content for a Destiny OpenAlex work.

    This function creates the abstract content based on the source and source document.

    Args:
        data_source (DataSource): The source of the data coming in.
        source_document (dict): The source document containing the abstract data.

    Returns:
        dict: A dictionary containing the abstract content.

    """
    return {
        "enhancement_type": EnhancementType.ABSTRACT.value,
        "process": AbstractProcessType.UNINVERTED.value
        if data_source == DataSource.OPEN_ALEX
        else AbstractProcessType.OTHER.value,
        "abstract": convert_inverted_abstract(
            source_document.get("abstract_inverted_index", "")
        )
        if data_source == DataSource.OPEN_ALEX
        else source_document.get("abstract", ""),
    }


def get_destiny_openalex_work(
    metadata: DestinyOpenAlexWorkMetadata,
    source_document: dict,
    data_source: DataSource = DataSource.OPEN_ALEX,
) -> DestinyOpenAlexWork:
    """
    Get a DestinyOpenAlexWork object from provided metadata.

    Args:
        metadata (dict): A dictionary containing metadata for the OpenAlex work.
        source_document (dict): The source document containing the data of interest.
            This could be dervied from an OpenAlex work, Solr or similar.
        data_source (DataSource, optional): The source of the metadata, default is DataSource.OPEN_ALEX.

    Returns:
        DestinyOpenAlexWork: An instance of DestinyOpenAlexWork populated with the metadata.

    """
    destiny_work_identifiers = prepare_destiny_identifiers(metadata)
    destiny_work_authors = prepare_destiny_authorships(metadata)
    destiny_work_locations = prepare_destiny_locations(metadata)
    destiny_work_annotations = prepare_destiny_annotations(metadata)
    destiny_work_abstract = prepare_destiny_work_abstract_annotation(
        data_source, source_document
    )

    authors_dict_not_empty = any(
        author.get("display_name") or author.get("orcid") or author.get("position")
        for author in destiny_work_authors
    )

    locations_content_populated = any(
        bool(location_dict) for location_dict in destiny_work_locations
    )

    annotation_content_populated = any(
        bool(annotation_dict) for annotation_dict in destiny_work_annotations
    )

    core_destiny_work = create_core_destiny_openalex_work(
        metadata=metadata,
        destiny_work_identifiers=destiny_work_identifiers,
        data_source=data_source,
        source_document=source_document,
    )

    if authors_dict_not_empty:
        core_destiny_work.enhancements[0]["content"].update(
            {"authorship": destiny_work_authors}
        )

    if is_valid_nonempty_string(destiny_work_abstract.get("abstract")):
        core_destiny_work.enhancements.append(
            {
                "source": data_source.value,
                "visibility": Visibility.RESTRICTED.value
                if metadata.is_retracted
                else Visibility.PUBLIC.value,
                "processor_version": metadata.processor_version,
                "content": destiny_work_abstract,
            }
        )

    if locations_content_populated:
        core_destiny_work.enhancements.append(
            {
                "source": data_source.value,
                "visibility": Visibility.RESTRICTED.value
                if metadata.is_retracted
                else Visibility.PUBLIC.value,
                "processor_version": metadata.processor_version,
                "content": {
                    "enhancement_type": EnhancementType.LOCATION.value,
                    "locations": destiny_work_locations,
                },
            }
        )

    if annotation_content_populated:
        core_destiny_work.enhancements.append(
            {
                "source": data_source.value,
                "visibility": Visibility.RESTRICTED.value
                if metadata.is_retracted
                else Visibility.PUBLIC.value,
                "processor_version": metadata.processor_version,
                "content": {
                    "enhancement_type": EnhancementType.ANNOTATION.value,
                    "annotations": destiny_work_annotations,
                },
            },
        )

    if is_valid_nonempty_string(metadata.microsoft_academic_graph):
        core_destiny_work.identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.OTHER.value,
                "identifier": metadata.microsoft_academic_graph,
                "other_identifier_name": "Microsoft Academic Graph ID",
            }
        )
    if is_valid_nonempty_string(metadata.pubmed_central_id):
        core_destiny_work.identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.OTHER.value,
                "identifier": metadata.pubmed_central_id,
                "other_identifier_name": "Pubmed Central ID",
            }
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
