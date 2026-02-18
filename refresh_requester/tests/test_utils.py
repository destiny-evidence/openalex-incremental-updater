from datetime import date

import pytest
from freezegun import freeze_time

from refresh_requester.utils import (
    format_metadata_blob_name,
    get_fetch_date,
    get_stop_date,
)


@freeze_time("2025-06-18")
def test_get_fetch_date_no_date_set(mocker, test_settings) -> None:
    """
    Test the get_fetch_date function when no date is set in the settings.

    It should call check_previous_file_dates to determine the fetch date.
    """
    test_datetime = date.today()
    test_settings.fetch_date = None
    check_previous_file_dates_mock = mocker.patch(
        "refresh_requester.utils.check_previous_file_dates",
        return_value=test_datetime,
    )

    result = get_fetch_date(test_settings)

    assert (
        check_previous_file_dates_mock.call_count == 1
    ), "check_previous_file_dates should be called once"
    assert (
        result == test_datetime
    ), "get_fetch_date should return the date from check_previous_file_dates"


@freeze_time("2025-06-18")
def test_get_fetch_date_date_set_in_settings(mocker, test_settings) -> None:
    """
    Test the get_fetch_date function when no date is set in the settings.

    It should call check_previous_file_dates to determine the fetch date.
    """
    test_datetime = date.today()
    test_settings.fetch_date = test_datetime
    check_previous_file_dates_mock = mocker.patch(
        "refresh_requester.utils.check_previous_file_dates",
        return_value=test_datetime,
    )

    result = get_fetch_date(test_settings)

    assert (
        check_previous_file_dates_mock.call_count == 0
    ), "check_previous_file_dates should not be called when fetch_date is set in settings"
    assert (
        result == test_settings.fetch_date
    ), "get_fetch_date should return the date set in settings"


@freeze_time("2025-06-18")
@pytest.mark.parametrize(
    ("fetch_date", "expected_stop_date"),
    [
        ("2025-06-16", "2025-06-17"),
        ("2025-06-12", "2025-06-17"),
        ("2025-06-17", "2025-06-17"),
        ("2025-06-18", "2025-06-18"),
    ],
)
def test_get_stop_date_no_date_set(
    test_settings, fetch_date, expected_stop_date
) -> None:
    """
    Test the get_stop_date function when no date is set in the settings.

    It should return yesterday's date if the fetch date is in the past, or the fetch date if it is today or yesterday.
    This ensures that when we request a refresh run it will process data from the last processed
    date up to the current date, without leaving any gaps or overlaps in the data.
    """
    test_settings.fetch_date = None
    test_settings.stop_date = None
    test_fetch_date = date.fromisoformat(fetch_date)

    expected_stop_date = date.fromisoformat(expected_stop_date)

    result = get_stop_date(test_settings, test_fetch_date)

    assert (
        result == expected_stop_date
    ), "get_stop_date should return yesterday's date when no stop_date is set in settings and fetch_date is in the past"


@freeze_time("2025-06-18")
@pytest.mark.parametrize(
    ("fetch_date", "stop_date"),
    [
        ("2025-06-16", "2025-06-16"),
        ("2025-06-12", "2025-06-14"),
    ],
)
def test_get_stop_date_date_set_in_settings(
    test_settings, fetch_date, stop_date
) -> None:
    """
    Test the get_stop_date function when the date is set in the settings.

    It should return the date set in the settings, regardless of the fetch date.
    This allows us to specify a custom stop date for the refresh request if needed, such as
    if we want to request a refresh up to a specific date in the past.
    """
    test_fetch_date = date.fromisoformat(fetch_date)
    test_stop_date = date.fromisoformat(stop_date)

    test_settings.stop_date = test_stop_date

    result = get_stop_date(test_settings, test_fetch_date)

    assert (
        result == test_settings.stop_date
    ), "get_stop_date should return the date set in settings"


def test_format_metadata_blob_name_with_stop_date() -> None:
    """
    Test the format_metadata_blob_name function.

    It should return the correct blob name based on the provided parameters.
    """
    data_source = "openalex"
    fetch_date = date(2025, 3, 1)
    stop_date = date(2025, 3, 31)

    expected_blob_name = (
        "ingestion_metadata/destiny_repository_"
        f"{data_source}_ingestion_batch_from_{fetch_date}_to_{stop_date}.jsonl"
    )

    result = format_metadata_blob_name(data_source, fetch_date, stop_date)

    assert (
        result == expected_blob_name
    ), "The formatted blob name should match the expected format"


def test_format_metadata_blob_name_without_stop_date() -> None:
    """Test the format_metadata_blob_name function."""
    data_source = "openalex"
    fetch_date = date(2025, 3, 1)

    expected_blob_name = (
        "ingestion_metadata/destiny_repository_"
        f"{data_source}_ingestion_batch_from_{fetch_date}.jsonl"
    )

    result = format_metadata_blob_name(data_source, fetch_date, None)

    assert (
        result == expected_blob_name
    ), "The formatted blob name should match the expected format"
