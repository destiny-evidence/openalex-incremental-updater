"""Models associated with references."""

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
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
    The process used to acquyire the abstract.

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


class DestinyOpenAlexWork(BaseModel):
    """Schema representing a work in the Destiny system."""

    identifiers: list[dict] = Field(
        default_factory=list[dict],
        description="A list of `ExternalIdentifiers` for the Reference",
    )
    enhancements: list[dict] = Field(
        default_factory=list[dict],
        description="A list of enhancements for the reference",
    )


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

    destiny_work = DestinyOpenAlexWork(
        identifiers=[
            {
                "identifier_type": ExternalIdentifierType.DOI.value,
                "identifier": doi,
            },
            {
                "identifier_type": ExternalIdentifierType.OPEN_ALEX.value,
                "identifier": openalex_id,
            },
            {
                "identifier_type": ExternalIdentifierType.PM_ID.value,
                "identifier": pubmed_id,
            },
        ],
        enhancements=[
            {
                "source": "openalex",
                "processor_version": "1.0.0",
                "enhancement_type": EnhancementType.BIBLIOGRAPHIC.value,
                "content": {
                    "enhancement_type": EnhancementType.BIBLIOGRAPHIC.value,
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
                        for author in authorships_dict or {}
                    ],
                    "cited_by_count": openalex_work.get("cited_by_count"),
                    "created_date": openalex_work.get("created_date"),
                    "publication_date": openalex_work.get("publication_date"),
                    "publication_year": openalex_work.get("publication_year"),
                    "publisher": host_organisation_name,
                },
            },
            {
                "source": "openalex",
                "processor_version": "1.0.0",
                "enhancement_type": EnhancementType.ABSTRACT.value,
                "content": {
                    "enhancement_type": EnhancementType.ABSTRACT.value,
                    "process": AbstractProcessType.UNINVERTED.value,
                    "abstract": convert_inverted_abstract(
                        openalex_work.get("abstract_inverted_index")
                    ),
                },
            },
            {
                "source": "openalex",
                "processor_version": "1.0.0",
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
                        for location in locations or {}
                    ],
                },
            },
            {
                "source": "openalex",
                "processor_version": "1.0.0",
                "enhancement_type": EnhancementType.ANNOTATION.value,
                "content": {
                    "enhancement_type": EnhancementType.ANNOTATION.value,
                    "annotations": [
                        {
                            "annotation_type": "openalex:topic",
                            "label": annotation["display_name"],
                            "data": annotation,
                        }
                        for annotation in topics or {}
                    ],
                },
            },
        ],
    )
    if microsoft_academic_graph:
        destiny_work.identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.OTHER.value,
                "identifier": microsoft_academic_graph,
            }
        )
    if pubmed_central_id:
        destiny_work.identifiers.append(
            {
                "identifier_type": ExternalIdentifierType.OTHER.value,
                "identifier": pubmed_central_id,
            }
        )
    return destiny_work


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
