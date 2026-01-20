"""Retrieve data from OpenAlex API."""

import uuid
from asyncio import Lock
from collections.abc import Callable
from datetime import date

import httpx
from destiny_sdk.references import ReferenceFileInput
from loguru import logger

from openalex_incremental_updater.core.config import get_settings
from openalex_incremental_updater.core.job_state import JobState
from openalex_incremental_updater.core.utils import async_timer
from openalex_incremental_updater.ingest import AsyncRetryClient, CreatedOrUpdated
from openalex_incremental_updater.models.destiny import convert_openalex_to_destiny

fetch_lock = Lock()


class UpstreamOpenAlexError(Exception):
    """Exception raised for errors in the OpenAlex API."""


class OpenAlexDataFetcher:
    """Class to control data fetching from the OpenAlex API."""

    def __init__(self, retries: int = 5, backoff_factor: int = 5) -> None:
        """Class constructor."""
        self.settings = get_settings()
        self.retries = retries
        self.backoff_factor = backoff_factor

    @staticmethod
    def build_query(fetch_date: date, created_or_updated: CreatedOrUpdated) -> str:
        """
        Build a query string to filter OpenAlex API data by date.

        Args:
            fetch_date (date): The date to filter by.
            created_or_updated (CreatedOrUpdated): The type of date to filter by.

        Returns:
            str: The query string.

        """
        update_type = created_or_updated.value
        return f"from_{update_type}_date:{fetch_date}"

    @staticmethod
    def build_range_query(
        start_date: date, end_date: date, created_or_updated: CreatedOrUpdated
    ) -> str:
        """
        Build a query string to filter OpenAlex API data by date.

        Args:
            start_date (date): The start date to filter by.
            end_date (date): The end date to filter by.
            created_or_updated (CreatedOrUpdated): The type of date to filter by.

        Returns:
            str: The query string.

        """
        update_type = created_or_updated.value
        return f"from_{update_type}_date:{start_date},to_{update_type}_date:{end_date}"

    @async_timer
    async def fetch_works_filter(
        self,
        openalex_filter: str | None,
        works_retrieved_limit: int | None = None,
        report: Callable | None = None,
    ) -> list[ReferenceFileInput]:
        """
        Fetch data from the OpenAlex API using a custom filter.

        Args:
            openalex_filter (Optional[str]): The filter to apply to the API query.
            works_retrieved_limit (Optional[int]): The maximum number of works to retrieve. Defaults to None.

        Returns:
            list[ReferenceFileInput]: The retrieved works.

        """
        if report:
            report(status=JobState.PENDING, progress="Starting fetch job")
        async with fetch_lock:
            aggregate_results = []

            # OpenAlex API limits the number of results per page to 200
            per_page: str = str(
                min(200, works_retrieved_limit) if works_retrieved_limit else 200
            )

            async with AsyncRetryClient(
                retries=self.retries, backoff_factor=self.backoff_factor
            ) as session:
                headers = {
                    "api_key": self.settings.OPENALEX_API_KEY.get_secret_value(),
                }
                session.headers.update(headers)
                cursor: str = "*"
                instance_id = uuid.uuid4().hex[:8]
                logger.info(
                    f"[Instance {instance_id}] Requesting all works with filter {openalex_filter}"
                )

                base_works_url = f"{self.settings.OPENALEX_API_URL}/works"
                query_string = (
                    f"{base_works_url}?filter={openalex_filter}"
                    if openalex_filter
                    else base_works_url
                )

                counter_works_retrieved = 0
                last_known_cursor = None
                total_works_to_download = 0
                while cursor:
                    filtered_works_url = (
                        query_string + f"&cursor={cursor}&per-page={per_page}"
                    )
                    logger.debug(
                        f"[Instance {instance_id}] Fetching URL: {filtered_works_url}"
                    )
                    response = await session.get(filtered_works_url)

                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as http_error:
                        error_message = str(http_error)
                        logger.error(f"OpenAlex API query failed: {error_message}")
                        raise UpstreamOpenAlexError(error_message) from http_error

                    retrieved_works = response.json()

                    results = retrieved_works["results"]
                    aggregate_results.extend(results)

                    count_works_total = retrieved_works["meta"]["count"]
                    total_works_to_download = count_works_total
                    counter_works_retrieved += len(results)
                    logger.info(
                        f"[Instance {instance_id}] Processed {counter_works_retrieved} results of {count_works_total}"
                    )
                    cursor = retrieved_works["meta"]["next_cursor"]
                    logger.info(f"[Instance {instance_id}] Next cursor: {cursor}")

                    if report:
                        report(
                            status=JobState.RUNNING,
                            progress=f"{counter_works_retrieved}/{count_works_total}",
                            total_works=count_works_total,
                        )
                    if cursor:
                        last_known_cursor = cursor
                    if (
                        works_retrieved_limit
                        and counter_works_retrieved >= works_retrieved_limit
                    ):
                        logger.info(
                            f"Reached the limit of {works_retrieved_limit} works."
                        )
                        return self.process_aggregate_results(aggregate_results)

            logger.info(f"Last known cursor: {last_known_cursor}")
            logger.info(
                f"Finished paging. Retrieved {counter_works_retrieved} results."
            )
            if report:
                report(
                    status=JobState.DOWNLOADED,
                    progress=f"{counter_works_retrieved} works retrieved",
                    total_works=total_works_to_download,
                )

            return self.process_aggregate_results(aggregate_results)

    def process_aggregate_results(
        self, aggregate_results: list[dict]
    ) -> list[ReferenceFileInput]:
        """
        Process the aggregate results from the OpenAlex API to match the Destiny data model.

        Args:
            aggregate_results (list[dict]): The aggregate results from the OpenAlex API.

        Returns:
            list[DestinyWork]: The processed results in the Destiny data model format.

        """
        return [convert_openalex_to_destiny(result) for result in aggregate_results]
