"""Models associated with references."""

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)

from openalex_incremental_updater.models.openalex import OpenAlexWork


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
        default_factory=list,
        description="A list of `ExternalIdentifiers` for the Reference",
    )
    enhancements: list[dict] = Field(
        default_factory=list,
        description="A list of enhancements for the reference",
    )


def convert_openalex_to_destiny(
    openalex_work: OpenAlexWork,
) -> DestinyOpenAlexWork:
    """
    Convert OpenAlex works to a Destiny OpenAlex work.

    Args:
        openalex_work (list[dict]): The OpenAlex works to convert.

    Returns:
        DestinyOpenAlexWork: The converted Destiny OpenAlex work.

    """
    return DestinyOpenAlexWork(
        identifiers=[
            {
                "identifier_type": ExternalIdentifierType.DOI,
                "identifier": openalex_work.doi,
            },
            {
                "identifier_type": ExternalIdentifierType.OPEN_ALEX,
                "identifier": openalex_work.id,
            },
            {
                "identifier_type": ExternalIdentifierType.PM_ID,
                "identifier": openalex_work.ids.get("pmid")
                if openalex_work.ids
                else None,
            },
        ],
        enhancements=[
            {
                "source": "openalex",
                "processor_version": "1.0.0",
                "enhancement_type": EnhancementType.BIBLIOGRAPHIC,
                "content": {
                    "enhancement_type": EnhancementType.BIBLIOGRAPHIC,
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
                        for author in openalex_work.authorships
                    ],
                    "cited_by_count": openalex_work.cited_by_count,
                    "created_date": openalex_work.created_date,
                    "publication_date": openalex_work.publication_date,
                    "publication_year": openalex_work.publication_year,
                    "publisher": openalex_work.primary_location.get("source", {}).get(
                        "host_organization_name"
                    )
                    if openalex_work.primary_location
                    else None,
                },
            },
            {
                "source": "openalex",
                "processor_version": "1.0.0",
                "enhancement_type": EnhancementType.ABSTRACT,
                "content": {
                    "enhancement_type": EnhancementType.ABSTRACT,
                    "abstract": AbstractContentEnhancement(
                        abstract=convert_inverted_abstract(
                            openalex_work.abstract_inverted_index
                        ),
                        process=AbstractProcessType.UNINVERTED,
                    ),
                },
            },
            {
                "source": "openalex",
                "processor_version": "1.0.0",
                "enhancement_type": EnhancementType.LOCATION,
                "content": {
                    "enhancement_type": EnhancementType.LOCATION,
                    "locations": [
                        {
                            "is_oa": location.get("is_oa"),
                            "version": location.get("version"),
                            "landing_page_url": location.get("landing_page_url"),
                            "pdf_url": location.get("pdf_url"),
                            "license": location.get("license"),
                        }
                        for location in openalex_work.locations
                    ],
                },
            },
            {
                "source": "openalex",
                "processor_version": "1.0.0",
                "enhancement_type": EnhancementType.ANNOTATION,
                "content": {
                    "enhancement_type": EnhancementType.ANNOTATION,
                    "annotations": [
                        {
                            "annotation_type": annotation["annotation_type"],
                            "label": annotation["label"],
                            "data": annotation["data"],
                        }
                        for annotation in openalex_work.topics
                    ],
                },
            },
        ],
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
