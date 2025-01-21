"""Retrieve data from OpenAlex API."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import status
from loguru import logger
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from openalex_incremental_updater.core.config import get_settings
from openalex_incremental_updater.core.utils import simple_timer

settings = get_settings()


class RetrySession(Session):
    """Define a requests.Session with retry capabilities."""

    def __init__(self, retries: int = 5, backoff_factor: float = 0.1) -> None:
        """Class constructor."""
        super().__init__()
        self.retries = retries
        self.backoff_factor = backoff_factor

        self.setup()

    def setup(self) -> None:
        """Define retry behaviour and attach to the session."""
        retry_settings = Retry(
            total=self.retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_502_BAD_GATEWAY,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_504_GATEWAY_TIMEOUT,
            ],
        )
        self.mount("https://", HTTPAdapter(max_retries=retry_settings))


def fetch_data_free_tier() -> None:
    """
    Fetch data from the OpenAlex API.

    Bit of a proof of concept since we'll use an API key.
    """
    works_url = f"{settings.OPENALEX_API_URL}/works"
    mailto = settings.USER_EMAIL
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
def fetch_data_from_created_date(
    created_date: date, works_retrieved_limit: int | None = None
) -> None:
    """
    Fetch data from the OpenAlex API created **on or after** a specific date.

    Args:
        created_date (datetime): The date to fetch data from.
        works_retrieved_limit (int, optional): The maximum number of works to retrieve. Defaults to None.

    """
    with RetrySession() as session:
        headers = {
            "api_key": settings.OPENALEX_API_KEY.get_secret_value(),
        }
        session.headers.update(headers)
        cursor: str = "*"
        params = {
            "cursor": cursor,
            "per-page": "200",  # max allowed by OpenAlex
        }
        logger.info(f"Requesting all works created from {created_date}")

        counter_works_retrieved = 0
        last_known_cursor = None

        while params["cursor"]:
            filter_string = f"filter=from_created_date:{created_date}"
            filtered_works_url = f"{settings.OPENALEX_API_URL}/works?" + filter_string
            response = session.get(filtered_works_url, params=params)
            created_works = response.json()

            results = created_works["results"]
            creation_dates = [
                datetime.strptime(x["created_date"], "%Y-%m-%d").date() for x in results
            ]
            creation_dates.sort(reverse=True)
            count_works_total = created_works["meta"]["count"]
            counter_works_retrieved += len(results)
            logger.info(
                f"Processed {counter_works_retrieved} results of {count_works_total}"
            )
            params["cursor"] = created_works["meta"]["next_cursor"]
            logger.info(f"Latest `created_from` date retrieved: {creation_dates[0]}")
            logger.info(f"Next cursor: {params['cursor']}")

            if params["cursor"]:
                last_known_cursor = params["cursor"]
            if (
                works_retrieved_limit
                and counter_works_retrieved >= works_retrieved_limit
            ):
                logger.info(f"Reached the limit of {works_retrieved_limit} works.")
                break

    logger.info(f"Last known cursor: {last_known_cursor}")
    # Persist the cursor _somewhere_ to resume later in case of failures?
    logger.info(f"Finished paging. Retrieved {counter_works_retrieved} results.")


def fetch_previous_day_data() -> None:
    """Fetch data from the OpenAlex API created yesterday."""
    date_yesterday = datetime.now(ZoneInfo("Europe/London")).date() - timedelta(days=2)
    fetch_data_from_created_date(
        created_date=date_yesterday, works_retrieved_limit=1000
    )


if __name__ == "__main__":
    fetch_previous_day_data()
