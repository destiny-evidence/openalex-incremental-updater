"""Define common utility functions for the app."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import HttpUrl

from refresh_requester.blob_storage import determine_next_fetch_date
from refresh_requester.config import Settings


def get_fetch_date(settings: Settings) -> date:
    """
    Get the date to fetch data from.

    If `settings.fetch_date` is provided, use that.
    Otherwise, determine the next fetch date based on previous file dates in blob storage.

    Args:
        settings (Settings): Pydantic settings object containing configuration.

    Returns:
        date: The date to fetch data from, either from settings or determined by previous file dates.

    """
    if settings.fetch_date:
        return settings.fetch_date
    return determine_next_fetch_date()


def get_stop_date(settings: Settings, fetch_date: date) -> date:
    """
    Get the stop date for the refresh request.

    This is typically the same as the fetch date, but
    may be more recent if the fetch date is in the past
    and we want to request a refresh up to the current date.

    Args:
        settings (Settings): Pydantic settings object containing configuration.
        fetch_date (date): The date to fetch data from.

    Returns:
        date: The stop date for the refresh request.

    """
    if settings.stop_date:
        return settings.stop_date

    today = datetime.now(tz=ZoneInfo("UTC")).date()
    yesterday = today - timedelta(days=1)

    if fetch_date == today:
        return fetch_date

    return yesterday


def format_endpoint_url(url: HttpUrl) -> HttpUrl:
    """
    Format the endpoint URL to ensure it does not end with a slash.

    Args:
        url (HttpUrl): The URL to format.

    Returns:
        HttpUrl: The formatted URL without a trailing slash.

    """
    url_str = str(url)
    if url_str.endswith("/"):
        return HttpUrl(url_str[:-1])
    return HttpUrl(url_str)


def format_metadata_blob_name(
    data_source: str, fetch_date: date, stop_date: date | None
) -> str:
    """
    Format the metadata blob name.

    Args:
        data_source (str): The data source for the metadata.
        fetch_date (date): The fetch date for the metadata.
        stop_date (date | None): The stop date for the metadata.

    Returns:
        str: The formatted metadata blob name.

    """
    if stop_date is None:
        return f"ingestion_metadata/destiny_repository_{data_source}_ingestion_batch_from_{fetch_date}.jsonl"
    return f"ingestion_metadata/destiny_repository_{data_source}_ingestion_batch_from_{fetch_date}_to_{stop_date}.jsonl"
