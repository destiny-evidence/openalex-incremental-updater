"""Define OpenAlex-specific data structures."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class OpenAlexWork(BaseModel):
    """Define the structure of an OpenAlex work."""

    id: str
    doi: str | None = None
    title: str | None = None
    display_name: str | None = None
    publication_year: int | None = None
    publication_date: date | None = None
    ids: dict | None = None
    language: str | None = None
    primary_location: dict | None = None
    type: str | None = None
    type_crossref: str | None = None
    indexed_in: list[str] | None = None
    open_access: dict | None = None
    authorships: list[dict] | None = None
    countries_distinct_count: int | None = None
    institutions_distinct_count: int | None = None
    corresponding_author_ids: list[str] | None = None
    corresponding_institution_ids: list[str] | None = None
    apc_list: dict[str, Any | None] | None = None
    apc_paid: dict[str, Any | None] | None = None
    fwci: float | None = None
    has_fulltext: bool | None = None
    cited_by_count: int | None = None
    citation_normalized_percentile: dict[str, float | bool] | None = None
    biblio: dict | None = None
    is_retracted: bool | None = None
    is_paratext: bool | None = None
    is_xpac: bool | None = None
    primary_topic: dict | None = None
    topics: list[dict] | None = None
    keywords: list[dict] | None = None
    concepts: list[dict] | None = None
    mesh: list[dict] | None = None
    locations_count: int | None = None
    locations: list[dict] | None = None
    best_oa_location: dict | None = None
    sustainable_development_goals: list[dict] | None = None
    grants: list[dict] | None = None
    datasets: list | None = None
    versions: list | None = None
    referenced_works_count: int | None = None
    referenced_works: list[str] | None = None
    related_works: list[str] | None = None
    abstract_inverted_index: dict[str, list[int]] | None = None
    cited_by_api_url: str | None = None
    counts_by_year: list[dict[str, int]] | None = None
    updated_date: datetime | None = None
    created_date: date
