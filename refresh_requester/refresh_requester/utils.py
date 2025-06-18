"""Define common utility functions for the app."""

from datetime import date

from refresh_requester.blob_storage import check_previous_file_dates
from refresh_requester.config import Settings


def get_fetch_date(settings: Settings) -> date:
    """
    Get the date to fetch data from.

    If `settings.fetch_date` is provided, use that. Otherwise, check previous file dates in blob storage.

    Args:
        settings (Settings): Pydantic settings object containing configuration.

    Returns:
        date: The date to fetch data from, either from settings or determined by previous file dates.

    """
    if settings.fetch_date:
        return settings.fetch_date
    return check_previous_file_dates()
