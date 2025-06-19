from datetime import date

from freezegun import freeze_time

from refresh_requester.utils import get_fetch_date


@freeze_time("2025-06-18")
def test_get_fetch_date_no_date_set(mocker, test_settings) -> None:
    """
    Test the get_fetch_date function when no date is set in the settings.

    It should call check_previous_file_dates to determine the fetch date.
    """
    test_datetime = date.today()  # noqa: DTZ011
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
    test_datetime = date.today()  # noqa: DTZ011
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
