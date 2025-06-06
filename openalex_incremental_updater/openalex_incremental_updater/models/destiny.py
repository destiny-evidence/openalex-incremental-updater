"""Models associated with references."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


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
        document.
    - `pmid`: A PubMed ID which is a unique identifier for a document in PubMed.
    - `openalex`: An OpenAlex ID which is a unique identifier for a document in
        OpenAlex.
    - `other`: Any other identifier not defined. This should be used sparingly.
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
    pubmed_id: str | None = Field(
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

    @model_validator(mode="after")
    def validate_enhancements(self) -> Self:
        """
        Validate the enhancements of the work.

        This method checks that the bibiliographic enhancements list is not empty and that it
        contains at least the authorship and created_date fields.

        Raises:
            ValueError: If the identifiers list is empty or does not contain a
                valid identifier type.

        Returns:
            self: The validated instance of DestinyOpenAlexWork.

        """
        if not self.enhancements:
            error_message = "Enhancements list cannot be empty."
            raise ValueError(error_message)
        if not any(
            enhancement.get("content")
            and enhancement["enhancement_type"] == EnhancementType.BIBLIOGRAPHIC.value
            and (enhancement["content"].get("created_date"))
            for enhancement in self.enhancements
        ):
            error_message = "At least one enhancement must be of type BIBLIOGRAPHIC with authorship or created_date."
            raise ValueError(error_message)
        return self


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

    return get_destiny_openalex_work(work_metadata, openalex_work)


def get_destiny_openalex_work(
    metadata: DestinyOpenAlexWorkMetadata,
    source_document: dict,
) -> DestinyOpenAlexWork:
    """
    Get a DestinyOpenAlexWork object from provided metadata.

    Args:
        metadata (dict): A dictionary containing metadata for the OpenAlex work.
        source_document (dict): The source document containing the data of interest.
            This could be dervied from an OpenAlex work, Solr or similar.
        source (str): The source of the metadata, default is "openalex".

    Returns:
        DestinyOpenAlexWork: An instance of DestinyOpenAlexWork populated with the metadata.

    """
    destiny_work_identifiers = [
        {
            "identifier_type": ExternalIdentifierType.OPEN_ALEX.value,
            "identifier": metadata.openalex_id,
        }
    ]

    if is_valid_string(metadata.doi):
        destiny_work_identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.DOI.value,
                "identifier": metadata.doi,
            }
        )
    if is_valid_string(metadata.pubmed_id):
        destiny_work_identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.PM_ID.value,
                "identifier": metadata.pubmed_id,
            }
        )

    destiny_work = DestinyOpenAlexWork(
        visibility=Visibility.HIDDEN if metadata.is_retracted else Visibility.PUBLIC,
        identifiers=destiny_work_identifiers,
        enhancements=[
            {
                "source": "openalex",
                "processor_version": metadata.processor_version,
                "enhancement_type": EnhancementType.BIBLIOGRAPHIC.value,
                "content": {
                    "enhancement_type": EnhancementType.BIBLIOGRAPHIC.value,
                    "title": source_document.get("title"),
                    "authorship": [
                        {
                            "display_name": author["author"].get("display_name")
                            if author["author"]
                            else None,
                            "orcid": author["author"].get("orcid")
                            if author["author"]
                            else None,
                            "position": author.get("author_position")
                            if author
                            else None,
                        }
                        for author in metadata.authorships_dict or {}
                    ],
                    "cited_by_count": source_document.get("cited_by_count"),
                    "created_date": source_document.get("created_date"),
                    "publication_date": source_document.get("publication_date"),
                    "publication_year": source_document.get("publication_year"),
                    "publisher": metadata.host_organisation_name,
                },
            },
            {
                "source": "openalex",
                "processor_version": metadata.processor_version,
                "enhancement_type": EnhancementType.ABSTRACT.value,
                "content": {
                    "enhancement_type": EnhancementType.ABSTRACT.value,
                    "process": AbstractProcessType.UNINVERTED.value,
                    "abstract": convert_inverted_abstract(
                        source_document.get("abstract_inverted_index")
                    ),
                },
            },
            {
                "source": "openalex",
                "processor_version": metadata.processor_version,
                "enhancement_type": EnhancementType.LOCATION.value,
                "content": {
                    "enhancement_type": EnhancementType.LOCATION.value,
                    "locations": [
                        {
                            "is_oa": location.get("is_oa"),
                            "version": location.get("version"),
                            "landing_page_url": location.get("landing_page_url"),
                            "pdf_url": location.get("pdf_url"),
                            "license": location.get("license"),
                        }
                        for location in metadata.locations or {}
                    ],
                },
            },
            {
                "source": "openalex",
                "processor_version": metadata.processor_version,
                "enhancement_type": EnhancementType.ANNOTATION.value,
                "content": {
                    "enhancement_type": EnhancementType.ANNOTATION.value,
                    "annotations": [
                        {
                            "annotation_type": "openalex:topic",
                            "label": annotation["display_name"],
                            "data": annotation,
                        }
                        for annotation in metadata.topics or {}
                    ],
                },
            },
        ],
    )
    if is_valid_string(metadata.microsoft_academic_graph):
        destiny_work.identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.OTHER.value,
                "identifier": metadata.microsoft_academic_graph,
            }
        )
    if is_valid_string(metadata.pubmed_central_id):
        destiny_work.identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.OTHER.value,
                "identifier": metadata.pubmed_central_id,
            }
        )
    return destiny_work


def is_valid_string(value: str | None) -> bool:
    """
    Check if a string is valid (not None and not empty).

    Args:
        value (str | None): The string to check.

    Returns:
        bool: True if the string is valid, False otherwise.

    """
    if value is None:
        return value is not None

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
