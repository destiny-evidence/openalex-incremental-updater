"""Define OpenAlex-specific data structures."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class OpenAlexWork(BaseModel):
    """Define the structure of an OpenAlex work."""

    id: str
    doi: str
    title: str
    display_name: str
    publication_year: int
    publication_date: date
    ids: dict
    language: str
    primary_location: dict
    type: str
    type_crossref: str
    indexed_in: list[str]
    open_access: dict
    authorships: list[dict]
    countries_distinct_count: int
    institutions_distinct_count: int
    corresponding_author_ids: list[str]
    corresponding_institution_ids: list[str]
    apc_list: dict[str, Any | None]
    apc_paid: dict[str, Any | None]
    fwci: float
    has_fulltext: bool
    cited_by_count: int
    citation_normalized_percentile: dict[str, float | bool]
    biblio: dict
    is_retracted: bool
    is_paratext: bool
    primary_topic: dict
    topics: list[dict]
    keywords: list[dict]
    concepts: list[dict]
    mesh: list[dict]
    locations_count: int
    locations: list[dict]
    best_oa_location: dict
    sustainable_development_goals: list[dict]
    grants: list[dict]
    datasets: list
    versions: list
    referenced_works_count: int
    referenced_works: list[str]
    related_works: list[str]
    abstract_inverted_index: dict[str, list[int]]
    cited_by_api_url: str
    counts_by_year: list[dict[str, int]]
    updated_date: datetime
    created_date: date
