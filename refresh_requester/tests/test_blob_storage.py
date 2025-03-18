from datetime import date, timedelta

import pytest
from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    HttpResponseError,
    ResourceExistsError,
    ResourceNotFoundError,
    ServiceRequestError,
)

from refresh_requester.blob_storage import (
    BlobUploadError,
    blob_upload,
    check_previous_file_dates,
    list_blobs_in_storage,
)


class MockBlob:
    def __init__(self, name: str):
        self.name = name


def test_check_previous_file_dates_success_files_found(mocker):
    """Test check_previous_file_dates function returns the latest date when files are found."""
    test_date_earliest = date(2025, 3, 1)
    test_date_middle = date(2025, 3, 2)
    test_date_latest = date(2025, 3, 3)

    mock_blob_names = [
        f"openalex_refresh_{test_date_earliest.isoformat()}.jsonl",
        f"openalex_refresh_{test_date_middle.isoformat()}.jsonl",
        f"openalex_refresh_{test_date_latest.isoformat()}.jsonl",
    ]

    mocker.patch(
        "refresh_requester.blob_storage.list_blobs_in_storage",
        return_value=mock_blob_names,
    )

    result = check_previous_file_dates()

    assert result == test_date_latest


def test_check_previous_file_dates_success_no_files_found_return_yesterday(
    mocker, freezer
):
    """Test check_previous_file_dates function returns the previous days date if no files are found."""
    test_date_today = date(2025, 3, 2)
    test_date_yesterday = test_date_today - timedelta(days=1)
    freezer.move_to(test_date_today)
    mocker.patch(
        "refresh_requester.blob_storage.list_blobs_in_storage", return_value=[]
    )

    result = check_previous_file_dates()

    assert result == test_date_yesterday


def test_list_blobs_in_storage(mocker, test_settings):
    """Test list_blobs_in_storage function works as expected."""
    mock_container_client = mocker.Mock()
    mock_blob_service = mocker.patch("refresh_requester.blob_storage.BlobServiceClient")

    mock_blob_service.return_value.get_container_client.return_value = (
        mock_container_client
    )

    mock_blob_names = [
        MockBlob("openalex_refresh_2025-03-01.jsonl"),
        MockBlob("openalex_refresh_2025-03-02.jsonl"),
        MockBlob("openalex_refresh_2025-03-03.jsonl"),
    ]

    mock_container_client.list_blobs.return_value = mock_blob_names

    result = list_blobs_in_storage()

    assert result == [blob.name for blob in mock_blob_names]


def test_blob_upload_success(mocker, test_settings):
    """Test successful blob upload."""
    test_data = (
        '{"key1": "value1", "key2": "value2"},{"key3": "value3", "key4": "value4"}'
    )
    test_updated_date = date(2025, 3, 1)
    test_fetch_date = date(2025, 2, 27)
    mock_blob_client = mocker.Mock()
    mock_blob_service = mocker.patch("refresh_requester.blob_storage.BlobServiceClient")

    mock_blob_service.return_value.get_blob_client.return_value = mock_blob_client

    blob_upload(test_data, test_fetch_date, test_updated_date)

    mock_blob_client.upload_blob.assert_called_once_with(test_data, overwrite=True)


@pytest.mark.parametrize(
    "exception",
    [
        AzureError,
        ClientAuthenticationError,
        HttpResponseError,
        ResourceExistsError,
        ResourceNotFoundError,
        ServiceRequestError,
    ],
)
def test_blob_upload_failure(mocker, test_settings, exception):
    """Test failed blob upload."""
    test_data = {"key1": "value1", "key2": "value2"}
    test_updated_date = date(2025, 3, 1)
    test_fetch_date = date(2025, 2, 27)

    mock_blob_client = mocker.Mock()
    mock_blob_client.upload_blob.side_effect = exception("Test uploading error")

    mock_get_blob_service_client = mocker.patch(
        "refresh_requester.blob_storage.get_blob_service_client"
    )
    mock_get_blob_service_client.return_value.get_blob_client.return_value = (
        mock_blob_client
    )

    with pytest.raises(BlobUploadError) as error:
        blob_upload(test_data, test_fetch_date, test_updated_date)
    assert "Test uploading error" in str(error.value)
