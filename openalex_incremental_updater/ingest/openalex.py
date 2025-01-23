"""Retrieve data from OpenAlex API."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import status
from loguru import logger

from openalex_incremental_updater.core.config import get_settings
from openalex_incremental_updater.core.utils import simple_timer
from openalex_incremental_updater.ingest import CreatedOrUpdated, RetrySession


class OpenAlexDataFetcher:
    """Class to control data fetching from the OpenAlex API."""

    def __init__(self) -> None:
        """Class constructor."""
        self.settings = get_settings()

    def fetch_data_free_tier(self) -> None:
        """
        Fetch data from the OpenAlex API.

        This function uses the free tier of the OpenAlex API and should be considered a fallback.
        """
        works_url = f"{self.settings.OPENALEX_API_URL}/works"
        mailto = self.settings.USER_EMAIL
        params = {
            "mailto": mailto,
        }
        cursor = "*"

        all_results = []
        count_api_queries = 0

        with RetrySession() as session:
            while cursor:
                params["cursor"] = cursor
                response = session.get(works_url, params=params)
                if response.status_code != status.HTTP_200_OK:
                    logger.error(f"Failed to fetch data: {response.text}")
                    break
                this_page_results = response.json()["results"]
                for result in this_page_results:
                    all_results.append(result)  # noqa: PERF402
                count_api_queries += 1

                cursor = response.json()["meta"]["next_cursor"]
        logger.info(
            f"Finished paging. Ran {count_api_queries} queries, retrieved {len(all_results)} results."
        )

    @simple_timer
    def fetch_data_from_date(
        self,
        fetch_date: date,
        created_or_updated: CreatedOrUpdated,
        works_retrieved_limit: int | None = None,
    ) -> list[dict]:
        """
        Fetch data from the OpenAlex API updated **on or after** a specific date.

        Args:
            fetch_date (date): The date from which to fetch data.
            created_or_updated (CreatedOrUpdated): The type of date to filter by.
            works_retrieved_limit (int, optional): The maximum number of works to retrieve. Defaults to None.

        """
        update_type = created_or_updated.value

        aggregate_results = []

        # OpenAlex API allows a maximum of 200 results per page
        per_page: str = str(
            min(200, works_retrieved_limit) if works_retrieved_limit else 200
        )

        with RetrySession() as session:
            headers = {
                "api_key": self.settings.OPENALEX_API_KEY.get_secret_value(),
            }
            session.headers.update(headers)
            cursor: str = "*"
            params = {
                "cursor": cursor,
                "per-page": per_page,
            }
            logger.info(f"Requesting all works {update_type} from {update_type}")

            counter_works_retrieved = 0
            last_known_cursor = None

            while params["cursor"]:
                filter_string = f"filter=from_{update_type}_date:{fetch_date}"
                filtered_works_url = (
                    f"{self.settings.OPENALEX_API_URL}/works?" + filter_string
                )
                response = session.get(filtered_works_url, params=params)
                retrieved_works = response.json()

                results = retrieved_works["results"]
                aggregate_results.append(results)
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
                params["cursor"] = retrieved_works["meta"]["next_cursor"]
                logger.info(
                    f"Latest `{update_type}_from` date retrieved: {creation_dates[0]}"
                )
                logger.info(f"Next cursor: {params['cursor']}")

                if params["cursor"]:
                    last_known_cursor = params["cursor"]
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

    def fetch_previous_day_data_snippet(self, snippet_length: int = 1000) -> list[dict]:
        """Fetch data from the OpenAlex API created yesterday."""
        date_yesterday = datetime.now(ZoneInfo("Europe/London")).date() - timedelta(
            days=2
        )
        return self.fetch_data_from_date(
            fetch_date=date_yesterday,
            created_or_updated=CreatedOrUpdated.CREATED,
            works_retrieved_limit=snippet_length,
        )


if __name__ == "__main__":
    fetcher = OpenAlexDataFetcher()
    results = fetcher.fetch_previous_day_data_snippet()
