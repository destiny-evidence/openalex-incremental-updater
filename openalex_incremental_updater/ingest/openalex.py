"""Retrieve data from OpenAlex API."""

from datetime import date, datetime

import httpx
from loguru import logger

from openalex_incremental_updater.core.config import get_settings
from openalex_incremental_updater.core.utils import async_timer
from openalex_incremental_updater.ingest import AsyncRetryClient, CreatedOrUpdated
from openalex_incremental_updater.models.openalex import OpenAlexWork


class UpstreamOpenAlexError(Exception):
    """Exception raised for errors in the OpenAlex API."""


class OpenAlexDataFetcher:
    """Class to control data fetching from the OpenAlex API."""

    def __init__(self, retries: int = 5, backoff_factor: int = 5) -> None:
        """Class constructor."""
        self.settings = get_settings()
        self.retries = retries
        self.backoff_factor = backoff_factor

    @async_timer
    async def fetch_works_from_date(
        self,
        fetch_date: date,
        created_or_updated: CreatedOrUpdated,
        works_retrieved_limit: int | None = None,
    ) -> list[OpenAlexWork]:
        """
        Fetch data from the OpenAlex API updated **on or after** a specific date.

        Args:
            fetch_date (date): The date from which to fetch data.
            created_or_updated (CreatedOrUpdated): The type of date to filter by.
            works_retrieved_limit (int, optional): The maximum number of works to retrieve. Defaults to None.

        Returns:
            list[OpenAlexWork]: The retrieved works.

        """
        update_type = created_or_updated.value

        aggregate_results = []

        # OpenAlex API allows a maximum of 200 results per page
        per_page: str = str(
            min(200, works_retrieved_limit) if works_retrieved_limit else 200
        )

        async with AsyncRetryClient(
            retries=self.retries, backoff_factor=self.backoff_factor
        ) as session:
            cursor: str = "*"
            logger.info(f"Requesting all works {update_type} from {fetch_date}")
            counter_works_retrieved = 0
            last_known_cursor = None
            headers = {
                "api_key": self.settings.OPENALEX_API_KEY.get_secret_value(),
            }
            session.headers.update(headers)
            while cursor:
                filter_string = f"filter=from_{update_type}_date:{fetch_date}"
                works_url = f"{self.settings.OPENALEX_API_URL}/works"
                query_string = f"{filter_string}&cursor={cursor}&per-page={per_page}"
                final_url = f"{works_url}?{query_string}"
                response = await session.get(final_url)
                logger.info(f"response url was {response.url}")
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as http_error:
                    error_message = str(http_error)
                    logger.error(f"OpenAlex API query failed: {error_message}")
                    raise UpstreamOpenAlexError(error_message) from http_error

                retrieved_works = response.json()

                results = retrieved_works["results"]
                aggregate_results.extend(results)
                # Note that from the API updated_date is a datetime and created_date is a date
                # Taking the first 10 characters of the datetime string to get the date only
                # as YYYY-MM-DD == 10 chars
                creation_dates = [
                    datetime.strptime(x[f"{update_type}_date"][:10], "%Y-%m-%d").date()
                    for x in results
                ]
                creation_dates.sort(reverse=True)
                count_works_total = retrieved_works["meta"]["count"]
                counter_works_retrieved += len(results)
                logger.info(
                    f"Processed {counter_works_retrieved} results of {count_works_total}"
                )
                cursor = retrieved_works["meta"]["next_cursor"]
                if len(creation_dates) > 0:
                    logger.info(
                        f"Latest `{update_type}_from` date retrieved: {creation_dates[0]}"
                    )
                else:
                    logger.info("No results retrieved.")
                logger.info(f"Next cursor: {cursor}")

                if cursor:
                    last_known_cursor = cursor
                if (
                    works_retrieved_limit
                    and counter_works_retrieved >= works_retrieved_limit
                ):
                    logger.info(f"Reached the limit of {works_retrieved_limit} works.")
                    return aggregate_results

        logger.info(f"Last known cursor: {last_known_cursor}")
        # Persist the cursor _somewhere_ to resume later in case of failures?
        logger.info(f"Finished paging. Retrieved {counter_works_retrieved} results.")
        return aggregate_results

    async def fetch_works_open_filter(
        self, openalex_filter: str | None, works_retrieved_limit: int | None = None
    ) -> list[OpenAlexWork]:
        """
        Fetch data from the OpenAlex API using a custom filter.

        Args:
            openalex_filter (Optional[str]): The filter to apply to the API query.
            works_retrieved_limit (Optional[int]): The maximum number of works to retrieve. Defaults to None.

        Returns:
            list[OpenAlexWork]: The retrieved works.

        """
        aggregate_results = []

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
            logger.info(f"Requesting all works with filter {openalex_filter}")

            base_works_url = f"{self.settings.OPENALEX_API_URL}/works"
            query_string = (
                f"{base_works_url}?filter={openalex_filter}"
                if openalex_filter
                else base_works_url
            )

            counter_works_retrieved = 0
            last_known_cursor = None
            while cursor:
                filtered_works_url = (
                    query_string + f"&cursor={cursor}&per-page={per_page}"
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
                counter_works_retrieved += len(results)
                logger.info(
                    f"Processed {counter_works_retrieved} results of {count_works_total}"
                )
                cursor = retrieved_works["meta"]["next_cursor"]
                logger.info(f"Next cursor: {cursor}")

                if cursor:
                    last_known_cursor = cursor
                if (
                    works_retrieved_limit
                    and counter_works_retrieved >= works_retrieved_limit
                ):
                    logger.info(f"Reached the limit of {works_retrieved_limit} works.")
                    return aggregate_results

        logger.info(f"Last known cursor: {last_known_cursor}")
        # Persist the cursor _somewhere_ temporary to quickly resume later in case of failures?
        logger.info(f"Finished paging. Retrieved {counter_works_retrieved} results.")

        return aggregate_results
