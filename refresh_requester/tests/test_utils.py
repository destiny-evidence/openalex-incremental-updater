from datetime import date

import pytest
from time_machine import travel

from refresh_requester.utils import (
    get_fetch_date,
    get_stop_date,
)


@travel("2025-06-18T12:00:00+00")
def test_get_fetch_date_no_date_set(mocker, test_settings) -> None:
    """
    Test the get_fetch_date function when no date is set in the settings.

    It should call determine_next_fetch_date to determine the fetch date.
    """
    test_datetime = date.today()
    test_settings.fetch_date = None
    determine_next_fetch_date_mock = mocker.patch(
        "refresh_requester.utils.determine_next_fetch_date",
        return_value=test_datetime,
    )

    result = get_fetch_date(test_settings)

    assert (
        determine_next_fetch_date_mock.call_count == 1
    ), "determine_next_fetch_date should be called once"
    assert (
        result == test_datetime
    ), "get_fetch_date should return the date from determine_next_fetch_date"


@travel("2025-06-18T12:00:00+00")
def test_get_fetch_date_date_set_in_settings(mocker, test_settings) -> None:
    """
    Test the get_fetch_date function when no date is set in the settings.

    It should call determine_next_fetch_date to determine the fetch date.
    """
    test_datetime = date.today()
    test_settings.fetch_date = test_datetime
    determine_next_fetch_date_mock = mocker.patch(
        "refresh_requester.utils.determine_next_fetch_date",
        return_value=test_datetime,
    )

    result = get_fetch_date(test_settings)

    assert (
        determine_next_fetch_date_mock.call_count == 0
    ), "should not be called when fetch_date is set in settings"
    assert (
        result == test_settings.fetch_date
    ), "get_fetch_date should return the date set in settings"


@travel("2025-06-18T12:00:00+00")
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


@travel("2025-06-18T12:00:00+00")
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
