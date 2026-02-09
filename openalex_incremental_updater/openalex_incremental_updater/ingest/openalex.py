"""Retrieve data from OpenAlex API."""

import copy
import uuid
from asyncio import Lock
from collections.abc import AsyncIterator, Callable
from datetime import date

import httpx
from destiny_sdk.references import ReferenceFileInput
from loguru import logger
from pydantic import ValidationError

from openalex_incremental_updater.core.config import get_settings
from openalex_incremental_updater.core.job_state import JobState
from openalex_incremental_updater.core.utils import async_timer
from openalex_incremental_updater.ingest import AsyncRetryClient, CreatedOrUpdated
from openalex_incremental_updater.models.destiny import (
    DESTINYReferenceDOIIdentifierError,
    convert_openalex_to_destiny,
)

_MAX_DOI_ERROR_EXAMPLES = 5

fetch_lock = Lock()


class UpstreamOpenAlexError(Exception):
    """Exception raised for errors in the OpenAlex API."""


def safe_result_conversion(
    results: list[dict],
    errors_dict: dict[str, dict],
    report: Callable | None = None,
) -> list[ReferenceFileInput]:
    """
    Convert OpenAlex results to Destiny ReferenceFileInputs safely.

    "Safe" in this sense is handling non-critical errors (like invalid DOIs) gracefully.

    On DOI validation errors, clear the DOI and retry the conversion so the reference is
    retained with any other identifiers (OpenAlex, PubMed, etc.)

    Errors are recorded with bounded aggregation.

    Args:
        results (list[dict]): List of OpenAlex result dictionaries.
        errors_dict (dict[str, dict): Dictionary to record errors.
        report (Callable | None): Optional reporting function to log errors.

    Returns:
        list[ReferenceFileInput]: List of converted ReferenceFileInput objects.

    """
    converted_results: list[ReferenceFileInput] = []
    doi_errors: dict = errors_dict.setdefault(
        "doi_errors", {"total": 0, "examples": []}
    )
    for result in results:
        try:
            converted_results.append(convert_openalex_to_destiny(result))
        except DESTINYReferenceDOIIdentifierError as doi_error:
            error_message = f"{doi_error}"

            invalid_doi = error_message.split(": ")[-1]
            logger.debug(f"Invalid DOI: {invalid_doi}")

            logger.warning(
                "Encountered invalid DOI during ingestion: {}",
                error_message,
            )

            doi_errors["total"] += 1

            doi_error_examples = doi_errors.get("examples", [])
            if len(doi_error_examples) < _MAX_DOI_ERROR_EXAMPLES:
                doi_error_examples.append(invalid_doi)
            cleaned = copy.deepcopy(result)

            if isinstance(cleaned.get("ids"), dict):
                cleaned["ids"]["doi"] = None
            cleaned["doi"] = None

            try:
                converted_results.append(convert_openalex_to_destiny(cleaned))
            except (
                ValidationError,
                ValueError,
                TypeError,
            ) as reference_conversion_error:
                dropped = errors_dict.setdefault("dropped_records", {"total": 0})
                dropped["total"] += 1
                error_message = (
                    "OpenAlex to Destiny conversion failed after clearing DOI"
                    f"{reference_conversion_error}"
                )
                logger.warning(error_message)

    if report and doi_errors.get("total", 0) > 0:
        report(errors=errors_dict)
    return converted_results


class OpenAlexDataFetcher:
    """Class to control data fetching from the OpenAlex API."""

    def __init__(self, retries: int = 5, backoff_factor: int = 5) -> None:
        """Class constructor."""
        self.settings = get_settings()
        self.retries = retries
        self.backoff_factor = backoff_factor

    @staticmethod
    def build_range_query(
        start_date: date, end_date: date, created_or_updated: CreatedOrUpdated
    ) -> str:
        """
        Build a query string to filter OpenAlex API data by a date range.

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
    async def fetch_works_filter(  # noqa: PLR0915
        self,
        openalex_filter: str | None,
        works_retrieved_limit: int | None = None,
        report: Callable | None = None,
    ) -> AsyncIterator[list[ReferenceFileInput]]:
        """
        Fetch data from the OpenAlex API using a custom filter.

        Args:
            openalex_filter (Optional[str]): The filter to apply to the API query.
            works_retrieved_limit (Optional[int]): The maximum number of works to retrieve. Defaults to None.

        Returns:
            AsyncIterator[list[ReferenceFileInput]]: The retrieved works.

        """
        errors_dict: dict[str, dict] = {}
        if report:
            report(status=JobState.PENDING, progress="Starting fetch job")

        async with fetch_lock:
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
                count_works_total = 0
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

                    count_works_total = retrieved_works["meta"]["count"]
                    number_of_results_in_current_batch = len(results)
                    counter_works_retrieved += number_of_results_in_current_batch
                    logger.info(
                        f"[Instance {instance_id}] Processed {counter_works_retrieved} results of {count_works_total}"
                    )
                    new_cursor = retrieved_works["meta"]["next_cursor"]
                    logger.info(f"[Instance {instance_id}] Next cursor: {new_cursor}")

                    cursor = new_cursor

                    if report:
                        report(
                            status=JobState.RUNNING,
                            progress=f"{counter_works_retrieved}/{count_works_total}",
                            total_works=count_works_total,
                        )

                    this_batch_hits_requested_results_limit = (
                        works_retrieved_limit is not None
                        and counter_works_retrieved >= works_retrieved_limit
                    )
                    if this_batch_hits_requested_results_limit:
                        logger.info(
                            f"Reached the limit of {works_retrieved_limit} works."
                        )
                        # This line just here to satisfy mypy that works_retrieved_limit is not None
                        limit = works_retrieved_limit if works_retrieved_limit else 0
                        number_of_results_under_limit = counter_works_retrieved - limit
                        required_number_of_results_from_final_batch = (
                            number_of_results_in_current_batch
                            - number_of_results_under_limit
                        )

                        final_limited_batch = results[
                            :required_number_of_results_from_final_batch
                        ]
                        converted_capped_results = safe_result_conversion(
                            final_limited_batch, report=report, errors_dict=errors_dict
                        )
                        yield converted_capped_results
                        break

                    converted_results = safe_result_conversion(
                        results, report=report, errors_dict=errors_dict
                    )
                    yield converted_results
                logger.info(
                    f"Finished paging. Retrieved {counter_works_retrieved} results."
                )

                # Validate completeness (skip if we intentionally limited results)
                exited_due_to_limit = (
                    works_retrieved_limit is not None
                    and counter_works_retrieved >= works_retrieved_limit
                )
                if (
                    not exited_due_to_limit
                    and counter_works_retrieved < count_works_total
                ):
                    msg = (
                        f"Incomplete fetch: retrieved {counter_works_retrieved} of "
                        f"{count_works_total} expected works"
                    )
                    raise UpstreamOpenAlexError(msg)
            logger.info("Completed streaming results.")
