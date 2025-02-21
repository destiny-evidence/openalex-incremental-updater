"""API Router definitions for the OpenAlex Incremental Updater - version 1."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from openalex_incremental_updater.core.config import get_settings
from openalex_incremental_updater.ingest.openalex import (
    CreatedOrUpdated,
    OpenAlexDataFetcher,
    UpstreamOpenAlexError,
)
from openalex_incremental_updater.models.openalex import OpenAlexWork

settings = get_settings()

router = APIRouter(prefix=settings.API_V1_STR, tags=["v1"])


@router.get("/openalex_works_ingest_from_date")
async def get_openalex_works_ingest_from_date(
    fetch_date: Annotated[
        date,
        Query(description="Date to fetch data from. Must be in ISO format YYYY-MM-DD."),
    ],
    ingest_type: Annotated[
        CreatedOrUpdated,
        Query(
            description="Method of determining ingest data. Must be one of 'created' or 'updated'."
        ),
    ],
    limit: Annotated[
        int | None, Query(description="Maximum number of records to ingest.")
    ] = None,
) -> list[OpenAlexWork]:
    """
    Fetch Works from the OpenAlex API with a date filter and ingest them into the repository.

    Args:
        fetch_date (date): Date to fetch data from. Must be in the format YYYY-MM-DD.
        ingest_type (str): Method of determining ingest data. Must be one of "created" or "updated".
        limit (int): Maximum number of records to ingest.

    Returns:
        list[OpenAlexWork]: List of OpenAlexWork objects.

    """
    fetcher = OpenAlexDataFetcher()
    try:
        results = await fetcher.fetch_works_from_date(
            fetch_date=fetch_date,
            created_or_updated=ingest_type,
            works_retrieved_limit=limit,
        )
    except UpstreamOpenAlexError as error:
        error_message = str(error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
        ) from error
    else:
        return results


@router.get("/openalex_works_open_filter")
async def get_openalex_works_ingest_open_filter(
    openalex_query_string: Annotated[
        str,
        Query(description="OpenAlex API-compliant query string."),
    ],
    limit: Annotated[int, Query(description="Maximum number of records to ingest.")],
) -> list[OpenAlexWork]:
    """
    Fetch data from the OpenAlex API and ingest it into the repository.

    Requires a user-defined filter string to be passed in the query parameter.
    It is left to the user to ensure that the filter string is correctly formatted.

    Args:
        openalex_query_string (str): OpenAlex API-compliant query string.
        limit (int): Maximum number of records to ingest.

    Returns:
        JSONResponse: Response with status code and message.

    """
    fetcher = OpenAlexDataFetcher()
    try:
        results = await fetcher.fetch_works_open_filter(
            openalex_filter=openalex_query_string, works_retrieved_limit=limit
        )
    except UpstreamOpenAlexError as error:
        error_message = str(error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
        ) from error
    else:
        return results
