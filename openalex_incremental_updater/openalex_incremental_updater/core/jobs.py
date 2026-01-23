"""Manage background jobs for the application."""

from collections.abc import AsyncIterator, Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from openalex_incremental_updater.core.job_state import JobManager
from openalex_incremental_updater.core.logger import logger
from openalex_incremental_updater.ingest.blob_storage import blob_upload
from openalex_incremental_updater.ingest.data import (
    JSONLConversionError,
    convert_destinyworks_to_jsonl_string,
)
from openalex_incremental_updater.ingest.openalex import (
    CreatedOrUpdated,
    OpenAlexDataFetcher,
    UpstreamOpenAlexError,
)


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
        job_manager (JobManager): The job manager to track job state.
        job_id (str): The unique ID for the job.
        report (Callable): A callback function to report progress.
        start_date (date): Start date to fetch data from.
        end_date (date): End date to fetch data to.
        ingest_type (CreatedOrUpdated): Method of determining ingest data. Must be one of "created" or "updated".
        limit (int | None): Maximum number of records to ingest. Defaults to None.

    """
    logger.info("Starting background OpenAlex ingest job")
    date_today = datetime.now(ZoneInfo("UTC")).date()
    total_ingested = 0
    uploaded_blob_name: str | None = None
    job_progress = job_manager.get(job_id).get("progress", {})
    try:
        job_result = openalex_works_ingest_date_range(
            report, start_date, end_date, ingest_type, limit
        )

        logger.info("Streaming data from ingest to blob storage")

        uploaded_blob_name = await run_openalex_refresh_blob_upload_job(
            job_result, start_date, end_date, date_today
        )

        total_ingested = job_progress.get("total_works", 0)
        logger.info(f"Upload complete. {job_progress=}, {total_ingested=}")
    except (UpstreamOpenAlexError, JSONLConversionError) as error:
        error_message = str(error)
        logger.error("Ingest job failed: {}", error_message)
        job_manager.set_progress(job_id, status="failed", progress="failed")
        job_manager.fail(job_id, error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
        ) from error
    logger.info("Blob upload completed successfully.")
    if uploaded_blob_name is None:
        error_message = "Blob upload did not complete successfully."
        logger.error(error_message)
        job_manager.set_progress(job_id, status="failed", progress="failed")
        job_manager.fail(job_id, Exception(error_message))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message,
        )

    job_manager.set_progress(
        job_id,
        status="succeeded",
        progress="upload complete",
        total_works=total_ingested,
    )
    job_manager.succeed(job_id, result=uploaded_blob_name)


async def openalex_works_ingest_date_range(
    report: Callable,
    start_date: date,
    end_date: date,
    ingest_type: CreatedOrUpdated,
    limit: int | None = None,
) -> AsyncIterator[bytes]:
    """
    Fetch Works from the OpenAlex API with a date range filter and ingest them into the repository.

    Args:
        report (Callable): A callback function to report progress.
        start_date (date): Start date to fetch data from. Must be in the format YYYY-MM-DD.
        end_date (date): End date to fetch data to. Must be in the format YYYY-MM-DD.
        ingest_type (CreatedOrUpdated): Method of determining ingest data. Must be one of "created" or "updated".
        limit (int | None): Maximum number of records to ingest. Defaults to None.

    Returns:
        AsyncIterator[bytes]: JSONL-ified response from the API, representing a list of DestinyOpenAlexWork objects.

    """
    openalex_query = OpenAlexDataFetcher.build_range_query(
        start_date, end_date, ingest_type
    )
    fetcher = OpenAlexDataFetcher()
    logger.info("Fetching OpenAlex works from {} to {}", start_date, end_date)
    try:
        results = fetcher.fetch_works_filter(
            openalex_filter=openalex_query,
            works_retrieved_limit=limit,
            report=report,
        )

        async for item in convert_destinyworks_to_jsonl_string(results):
            yield item

    except UpstreamOpenAlexError as ingest_error:
        error_message = str(ingest_error)
        logger.error("Error fetching OpenAlex works: {}", error_message)
        raise

    except JSONLConversionError as jsonl_error:
        error_message = str(jsonl_error)
        logger.error("Error converting works to JSONL: {}", error_message)
        raise


async def run_openalex_refresh_blob_upload_job(
    data: AsyncIterator[bytes], fetch_date: date, stop_date: date, refresh_date: date
) -> str:
    """
    Run the blob upload job.

    Args:
        data (AsyncIterator[bytes]): The response from the API, converted to JSON-lines
        fetch_date (date): The date at which the data was fetched
        stop_date (date): The date at which the data was fetched until (inclusive)
        refresh_date (date): The date at which the data was refreshed

    Returns:
        str: The filename of the uploaded blob

    """
    blob_name = f"openalex_refresh_from_date_{fetch_date}_to_{stop_date}_refreshed_on_{refresh_date}.jsonl"
    uploaded_blob = await blob_upload(data, blob_name)
    logger.info(
        f"Data uploaded to blob storage from {fetch_date} to {stop_date}, uploaded {refresh_date}"
    )
    logger.info(f"Uploaded blob: {uploaded_blob}")
    return uploaded_blob
