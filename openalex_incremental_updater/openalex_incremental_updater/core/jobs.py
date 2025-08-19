"""Manage background jobs for the application."""

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from openalex_incremental_updater.core.job_state import JobManager
from openalex_incremental_updater.core.logger import logger
from openalex_incremental_updater.ingest.blob_storage import blob_upload
from openalex_incremental_updater.ingest.data import (
    convert_destinyworks_to_jsonl_string,
)
from openalex_incremental_updater.ingest.openalex import (
    CreatedOrUpdated,
    OpenAlexDataFetcher,
    UpstreamOpenAlexError,
)
from openalex_incremental_updater.models.destiny import DestinyOpenAlexWork


async def run_background_openalex_ingest_job(
    job_manager: JobManager,
    job_id: str,
    report: Callable,
    start_date: date,
    end_date: date,
    ingest_type: CreatedOrUpdated,
    limit: int | None = None,
) -> None:
    """
    Run a background job to ingest OpenAlex works.

    Args:
        job_id (str): The unique ID for the job.
        report_status (Callable): A callback function to report progress.
        start_date (date): Start date to fetch data from.
        end_date (date): End date to fetch data to.
        ingest_type (CreatedOrUpdated): Method of determining ingest data. Must be one of "created" or "updated".
        limit (int | None, optional): Maximum number of records to ingest. Defaults to None.

    """
    logger.info("Starting background OpenAlex ingest job")
    try:
        job_result = await openalex_works_ingest_date_range(
            report, start_date, end_date, ingest_type, limit
        )
    except UpstreamOpenAlexError as error:
        error_message = str(error)
        logger.error("Ingest job failed: {}", error_message)
        job_manager.set_progress(job_id, status="failed", progress="failed")
        job_manager.fail(job_id, error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
        ) from error
    logger.info("Ingest job completed successfully. Uploading to blob storage...")
    job_manager.set_progress(job_id, status="uploading", progress="uploading")
    date_today = datetime.now(ZoneInfo("UTC")).date()
    uploaded_blob_name = await run_openalex_refresh_blob_upload_job(
        job_result, start_date, end_date, date_today
    )
    logger.info("Blob upload completed successfully.")
    job_manager.set_progress(job_id, status="succeeded", progress="upload complete")
    job_manager.succeed(job_id, result=uploaded_blob_name)


async def openalex_works_ingest_date_range(
    report: Callable,
    start_date: date,
    end_date: date,
    ingest_type: CreatedOrUpdated,
    limit: int | None = None,
) -> str:
    """
    Fetch Works from the OpenAlex API with a date range filter and ingest them into the repository.

    Args:
        report (Callable): A callback function to report progress.
        start_date (date): Start date to fetch data from. Must be in the format YYYY-MM-DD.
        end_date (date): End date to fetch data to. Must be in the format YYYY-MM-DD.
        ingest_type (CreatedOrUpdated): Method of determining ingest data. Must be one of "created" or "updated".
        limit (int): Maximum number of records to ingest. Defaults to None.

    Returns:
        str: JSONL-ified response from the API, representing a list of DestinyOpenAlexWork objects.

    """
    openalex_query = OpenAlexDataFetcher.build_range_query(
        start_date, end_date, ingest_type
    )
    fetcher = OpenAlexDataFetcher()
    logger.info("Fetching OpenAlex works from {} to {}", start_date, end_date)
    try:
        results = await fetcher.fetch_works_filter(
            openalex_filter=openalex_query,
            works_retrieved_limit=limit,
            report=report,
        )
    except UpstreamOpenAlexError as error:
        error_message = str(error)
        logger.error("Error fetching OpenAlex works: {}", error_message)
        raise error from error
    else:
        return convert_destinyworks_to_jsonl_string(results)


async def openalex_works_ingest_from_date(
    fetch_date: date,
    ingest_type: CreatedOrUpdated,
    limit: int | None = None,
) -> list[DestinyOpenAlexWork]:
    """
    Fetch Works from the OpenAlex API with a date filter and ingest them into the repository.

    Args:
        fetch_date (date): Date to fetch data from. Must be in the format YYYY-MM-DD.
        ingest_type (CreatedOrUpdated): Method of determining ingest data. Must be one of "created" or "updated".
        limit (int): Maximum number of records to ingest. Defaults to None.

    Returns:
        list[DestinyOpenAlexWork]: List of DestinyOpenAlexWork objects.

    """
    openalex_query = OpenAlexDataFetcher.build_query(fetch_date, ingest_type)
    fetcher = OpenAlexDataFetcher()
    try:
        results = await fetcher.fetch_works_filter(
            openalex_filter=openalex_query,
            works_retrieved_limit=limit,
        )
    except UpstreamOpenAlexError as error:
        error_message = str(error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
        ) from error
    else:
        return results


async def openalex_works_ingest_open_filter(
    openalex_query_string: str,
    limit: int,
) -> list[DestinyOpenAlexWork]:
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
        results = await fetcher.fetch_works_filter(
            openalex_filter=openalex_query_string, works_retrieved_limit=limit
        )
    except UpstreamOpenAlexError as error:
        error_message = str(error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
        ) from error
    else:
        return results


async def run_openalex_refresh_blob_upload_job(
    data: str, fetch_date: date, stop_date: date, refresh_date: date
) -> str:
    """
    Run the blob upload job.

    Args:
        data (list[str]): The response from the API, converted to JSON-lines
        fetch_date (date): The date at which the data was fetched
        stop_date (date): The date at which the data was fetched until (inclusive)
        refresh_date (date): The date at which the data was refreshed

    Returns:
        str: The filename of the uploaded blob

    """
    blob_name = f"openalex_refresh_from_date_{fetch_date}_to_{stop_date}_refreshed_on_{refresh_date}.jsonl"
    uploaded_blob = blob_upload(data, blob_name)
    logger.info(
        f"Data uploaded to blob storage from {fetch_date} to {stop_date}, uploaded {refresh_date}"
    )
    logger.info(f"Uploaded blob: {uploaded_blob}")
    return uploaded_blob
