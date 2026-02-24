"""
OpenAlex → DESTINY transform pipeline.

Converts raw OpenAlex work JSON dicts into destiny-sdk ``ReferenceFileInput``
objects ready for JSONL serialisation. All transform logic for the snapshot
CLI is consolidated here so there is a single import path.

Public entry point::

    from openalex_snapshot_processor.cli.openalex_transforms import (
        openalex_to_reference_file_input,
    )

    ref = openalex_to_reference_file_input(work_dict)
    if ref:
        line = ref.model_dump_json()
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Any

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
from destiny_sdk.visibility import Visibility

if TYPE_CHECKING:
    from destiny_sdk.identifiers import ExternalIdentifier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ISO_DATE_LENGTH = 10  # Length of an ISO 8601 date string (YYYY-MM-DD)

_VENUE_TYPE_MAP: dict[str, PublicationVenueType] = {
    "journal": PublicationVenueType.JOURNAL,
    "repository": PublicationVenueType.REPOSITORY,
    "conference": PublicationVenueType.CONFERENCE,
    "ebook platform": PublicationVenueType.EBOOK_PLATFORM,
    "book series": PublicationVenueType.BOOK_SERIES,
}

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


class ValidationErrorType(str, Enum):
    """Types of validation errors."""

    INVALID_OPENALEX_ID = "invalid_openalex_id"
    INVALID_DOI = "invalid_doi"
    INVALID_PMID = "invalid_pmid"
    INVALID_DATE = "invalid_date"
    MALFORMED_JSON = "malformed_json"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    CORRUPTED_FILE = "corrupted_file"


@dataclass
class ValidationError:
    """A validation error for a record or field."""

    error_type: ValidationErrorType
    openalex_id: str | None
    field: str | None
    value: str | None
    message: str


# ---------------------------------------------------------------------------
# Low-level utilities
# ---------------------------------------------------------------------------


def extract_openalex_id(openalex_url: str) -> str:
    """
    Extract bare W-ID from an OpenAlex URL.

    >>> extract_openalex_id("https://openalex.org/W12345")
    'W12345'
    """
    return openalex_url.replace("https://openalex.org/", "").replace(
        "http://openalex.org/", ""
    )


def convert_inverted_abstract(inverted: dict[str, list[int]] | None) -> str:
    """
    Reconstruct plain-text abstract from an OpenAlex inverted index.

    >>> convert_inverted_abstract({"Hello": [0], "world": [1]})
    'Hello world'
    >>> convert_inverted_abstract(None)
    ''
    """
    if not inverted:
        return ""
    word_map: dict[int, str] = {}
    for word, positions in inverted.items():
        for pos in positions:
            word_map[pos] = word
    return " ".join(word for _, word in sorted(word_map.items()))


def is_valid_nonempty_string(value: str | None) -> bool:
    """Check if a string is non-None, non-empty, and not 'null'/'none'."""
    if value is None or not isinstance(value, str):
        return False
    stripped = value.strip().lower()
    return stripped not in ("", "null", "none")


def parse_date_safe(
    date_str: str | None,
    field_name: str,
    openalex_id: str,
    errors: list[ValidationError],
) -> date | None:
    """Parse an ISO date string, appending to *errors* on failure."""
    if not date_str:
        return None
    try:
        date_part = (
            date_str[:ISO_DATE_LENGTH] if len(date_str) >= ISO_DATE_LENGTH else date_str
        )
        return date.fromisoformat(date_part)
    except (ValueError, TypeError) as e:
        errors.append(
            ValidationError(
                error_type=ValidationErrorType.INVALID_DATE,
                openalex_id=openalex_id,
                field=field_name,
                value=str(date_str)[:50],
                message=str(e),
            )
        )
        return None


# ---------------------------------------------------------------------------
# Identifier creation
# ---------------------------------------------------------------------------


def create_identifiers(work: dict[str, Any]) -> list[ExternalIdentifier]:
    """Create SDK ``ExternalIdentifier`` objects from an OpenAlex work."""
    identifiers: list[ExternalIdentifier] = []
    ids = work.get("ids", {})

    # OpenAlex ID (required)
    openalex_url = ids.get("openalex") or work.get("id")
    if openalex_url:
        openalex_id = openalex_url.split("/")[-1]
        with contextlib.suppress(ValueError, TypeError):
            identifiers.append(OpenAlexIdentifier(identifier=openalex_id))

    # DOI
    if doi := ids.get("doi"):
        doi_value = doi.replace("https://doi.org/", "")
        with contextlib.suppress(ValueError, TypeError):
            identifiers.append(DOIIdentifier(identifier=doi_value))

    # PMID
    if pmid := ids.get("pmid"):
        pmid_value = pmid.replace("https://pubmed.ncbi.nlm.nih.gov/", "")
        with contextlib.suppress(ValueError, TypeError):
            identifiers.append(PubMedIdentifier(identifier=pmid_value))

    # PMCID as "other"
    if pmcid := ids.get("pmcid"):
        pmcid_value = pmcid.replace(
            "https://www.ncbi.nlm.nih.gov/pmc/articles/",
            "",
        )
        with contextlib.suppress(ValueError, TypeError):
            identifiers.append(
                OtherIdentifier(
                    identifier=pmcid_value,
                    other_identifier_name="pmcid",
                )
            )

    # MAG ID as "other"
    if mag := ids.get("mag"):
        with contextlib.suppress(ValueError, TypeError):
            identifiers.append(
                OtherIdentifier(
                    identifier=str(mag),
                    other_identifier_name="mag",
                )
            )

    return identifiers


# ---------------------------------------------------------------------------
# Enhancement creators
# ---------------------------------------------------------------------------


def extract_authorships(
    work: dict[str, Any],
    openalex_id: str,
    errors: list[ValidationError],
) -> list[Authorship]:
    """Extract authorship data from an OpenAlex work using SDK models."""
    authorships_raw = work.get("authorships", [])
    if not authorships_raw:
        return []

    result: list[Authorship] = []
    for i, auth in enumerate(authorships_raw):
        author = auth.get("author", {})
        display_name = author.get("display_name", "")
        orcid = author.get("orcid")

        if not display_name or not display_name.strip():
            continue

        if i == 0:
            position = AuthorPosition.FIRST
        elif i == len(authorships_raw) - 1:
            position = AuthorPosition.LAST
        else:
            position = AuthorPosition.MIDDLE

        try:
            result.append(
                Authorship(
                    display_name=display_name,
                    orcid=orcid,
                    position=position,
                )
            )
        except Exception as e:  # noqa: BLE001
            errors.append(
                ValidationError(
                    error_type=ValidationErrorType.INVALID_DATE,
                    openalex_id=openalex_id,
                    field="authorships",
                    value=str(author)[:100],
                    message=f"Invalid authorship: {e}",
                )
            )

    return result


def _build_publication_venue(source: dict[str, Any]) -> PublicationVenue:
    """Build a ``PublicationVenue`` from a source dict."""
    venue_type_str = source.get("type")
    return PublicationVenue(
        display_name=source.get("display_name"),
        venue_type=_VENUE_TYPE_MAP.get(venue_type_str, PublicationVenueType.OTHER)
        if venue_type_str
        else None,
        issn=source.get("issn"),
        issn_l=source.get("issn_l"),
        host_organization_name=source.get("host_organization_name"),
    )


def create_bibliographic_enhancement(
    work: dict[str, Any],
    openalex_id: str,
    errors: list[ValidationError],
) -> BibliographicMetadataEnhancement | None:
    """Create bibliographic metadata enhancement using SDK model."""
    title = work.get("title") or work.get("display_name")
    pub_year = work.get("publication_year")
    pub_date = parse_date_safe(
        work.get("publication_date"), "publication_date", openalex_id, errors
    )
    cited_by = work.get("cited_by_count")
    created_date = parse_date_safe(
        work.get("created_date"), "created_date", openalex_id, errors
    )
    updated_date = parse_date_safe(
        work.get("updated_date"), "updated_date", openalex_id, errors
    )
    authorships = extract_authorships(work, openalex_id, errors)

    publisher = None
    publication_venue = None
    if (primary_loc := work.get("primary_location")) and (
        source := primary_loc.get("source")
    ):
        publisher = source.get("host_organization_name")
        publication_venue = _build_publication_venue(source)

    pagination = None
    if biblio := work.get("biblio"):
        pagination = Pagination(
            volume=biblio.get("volume"),
            issue=biblio.get("issue"),
            first_page=biblio.get("first_page"),
            last_page=biblio.get("last_page"),
        )

    if not any([title, pub_year, pub_date, cited_by, authorships]):
        return None

    try:
        return BibliographicMetadataEnhancement(
            title=title,
            publication_year=pub_year,
            publication_date=pub_date,
            cited_by_count=cited_by,
            created_date=created_date,
            updated_date=updated_date,
            authorship=authorships if authorships else None,
            publisher=publisher,
            pagination=pagination,
            publication_venue=publication_venue,
        )
    except Exception as e:  # noqa: BLE001
        errors.append(
            ValidationError(
                error_type=ValidationErrorType.MALFORMED_JSON,
                openalex_id=openalex_id,
                field="bibliographic",
                value=None,
                message=f"Failed to create bibliographic enhancement: {e}",
            )
        )
        return None


def create_abstract_enhancement(
    work: dict[str, Any],
) -> AbstractContentEnhancement | None:
    """Create abstract enhancement using SDK model."""
    abstract_text = work.get("abstract")
    if not abstract_text:
        inverted = work.get("abstract_inverted_index")
        if inverted:
            abstract_text = convert_inverted_abstract(inverted)

    if not abstract_text or not abstract_text.strip():
        return None

    return AbstractContentEnhancement(
        process=AbstractProcessType.UNINVERTED,
        abstract=abstract_text,
    )


def create_annotation_enhancement(
    work: dict[str, Any],
) -> AnnotationEnhancement | None:
    """Create annotation enhancement from topics using SDK model."""
    annotations: list[BooleanAnnotation] = [
        BooleanAnnotation(
            scheme="openalex:topic",
            label=topic_name,
            value=True,
            data=topic,
        )
        for topic in work.get("topics", [])
        if (topic_name := topic.get("display_name"))
    ]

    if not annotations:
        return None

    return AnnotationEnhancement(annotations=annotations)


def create_location_enhancement(
    work: dict[str, Any],
    openalex_id: str,
    errors: list[ValidationError],
) -> LocationEnhancement | None:
    """Create location enhancement using SDK model for all locations."""
    locations_raw = work.get("locations", [])
    if not locations_raw:
        return None

    locations: list[Location] = []
    for loc_data in locations_raw:
        is_oa = loc_data.get("is_oa", False)
        version = loc_data.get("version")
        landing_page_url = loc_data.get("landing_page_url")
        pdf_url = loc_data.get("pdf_url")
        license_val = loc_data.get("license")
        extra = loc_data.get("source")

        try:
            loc = Location(
                is_oa=is_oa,
                version=version if is_valid_nonempty_string(version) else None,
                landing_page_url=(
                    landing_page_url
                    if is_valid_nonempty_string(landing_page_url)
                    else None
                ),
                pdf_url=pdf_url if is_valid_nonempty_string(pdf_url) else None,
                license=license_val if is_valid_nonempty_string(license_val) else None,
                extra=extra if extra else None,
            )
            locations.append(loc)
        except Exception as e:  # noqa: BLE001
            errors.append(
                ValidationError(
                    error_type=ValidationErrorType.MALFORMED_JSON,
                    openalex_id=openalex_id,
                    field="locations",
                    value=str(loc_data)[:100],
                    message=f"Invalid location: {e}",
                )
            )

    if not locations:
        return None

    return LocationEnhancement(locations=locations)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def openalex_to_reference_file_input(
    work: dict[str, Any],
) -> ReferenceFileInput | None:
    """
    Convert an OpenAlex work dict to a DESTINY ``ReferenceFileInput``.

    Returns ``None`` when the work has no usable identifiers.
    """
    identifiers = create_identifiers(work)
    if not identifiers:
        return None

    openalex_url = work.get("ids", {}).get("openalex") or work.get("id", "")
    openalex_id = openalex_url.split("/")[-1] if openalex_url else "unknown"

    errors: list[ValidationError] = []
    enhancements: list[EnhancementFileInput] = []

    if bib := create_bibliographic_enhancement(work, openalex_id, errors):
        enhancements.append(
            EnhancementFileInput(
                source="openalex",
                visibility=Visibility.PUBLIC,
                content=bib,
            )
        )

    if abstract := create_abstract_enhancement(work):
        enhancements.append(
            EnhancementFileInput(
                source="openalex",
                visibility=Visibility.PUBLIC,
                content=abstract,
            )
        )

    if annotation := create_annotation_enhancement(work):
        enhancements.append(
            EnhancementFileInput(
                source="openalex",
                visibility=Visibility.PUBLIC,
                content=annotation,
            )
        )

    if location := create_location_enhancement(work, openalex_id, errors):
        enhancements.append(
            EnhancementFileInput(
                source="openalex",
                visibility=Visibility.PUBLIC,
                content=location,
            )
        )

    return ReferenceFileInput(
        identifiers=identifiers,
        enhancements=enhancements if enhancements else None,
    )
