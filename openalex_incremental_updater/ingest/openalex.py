"""Retrieve data from OpenAlex API."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from fastapi import status
from loguru import logger

from openalex_incremental_updater.core.config import get_settings

settings = get_settings()


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

    with requests.Session() as session:
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


def fetch_data_from_created_date(created_date: date) -> None:
    """
    Fetch data from the OpenAlex API created **on or after** a specific date.

    Args:
        created_date (datetime): The date to fetch data from.

    """
    with requests.Session() as session:
        headers = {
            "api_key": settings.OPENALEX_API_KEY.get_secret_value(),
        }
        session.headers.update(headers)
        params = {
            "cursor": "*",
        }

        counter_works_retrieved = 0
        while params["cursor"]:
            filter_string = f"filter=from_created_date:{created_date}"
            filtered_works_url = f"{settings.OPENALEX_API_URL}/works?" + filter_string
            logger.info(f"Requesting all works created from {created_date}")
            response = session.get(filtered_works_url, params=params)
            created_works = response.json()

            results = created_works["results"]
            count_works_total = created_works["meta"]["count"]
            counter_works_retrieved += len(results)
            logger.info(
                f"Processed {counter_works_retrieved} results of {count_works_total}"
            )

            params["cursor"] = created_works["meta"]["next_cursor"]

    # Need to output the cursor to a file to resume later in case of failures...
    logger.info(f"Finished paging. Retrieved {counter_works_retrieved} results.")


def fetch_previous_day_data() -> None:
    """Fetch data from the OpenAlex API created yesterday."""
    date_yesterday = datetime.now(ZoneInfo("Europe/London")).date() - timedelta(days=1)
    fetch_data_from_created_date(date_yesterday)


if __name__ == "__main__":
    fetch_previous_day_data()
