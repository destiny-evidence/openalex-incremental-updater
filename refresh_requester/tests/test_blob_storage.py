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
    DestinyBlobStorageClient,
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


def test_destinyblobstorageclient_init(mocker, test_settings) -> None:
    """Test DestinyBlobStorageClient initialization."""
    mocker.patch("refresh_requester.blob_storage.BlobServiceClient")
    client = DestinyBlobStorageClient()
    assert (
        client is not None
    ), "Check that DestinyBlobStorageClient initializes correctly"


def test_destinyblobstorageclient_list_all_blobs(mocker, test_settings) -> None:
    """Test DestinyBlobStorageClient list_all_blobs method."""
    mock_blob_service = mocker.patch("refresh_requester.blob_storage.BlobServiceClient")
    mock_container_client = mocker.Mock()
    mock_blob_service.return_value.get_container_client.return_value = (
        mock_container_client
    )

    mock_blob_names = [
        MockBlob("blob1.jsonl"),
        MockBlob("blob2.jsonl"),
        MockBlob("blob3.jsonl"),
    ]

    mock_container_client.list_blobs.return_value = mock_blob_names

    client = DestinyBlobStorageClient()
    blobs = client.list_all_blobs()

    assert blobs == [
        blob.name for blob in mock_blob_names
    ], "Check that all blobs are listed correctly"


def test_destinyblobstorageclient_get_single_blob_sas_token(
    mocker, test_settings
) -> None:
    """Test DestinyBlobStorageClient get_single_blob_sas_token method."""
    expected_sas_token = "test_sas_token"  # noqa: S105

    mock_blob_sas_generation = mocker.patch(
        "refresh_requester.blob_storage.generate_blob_sas"
    )
    mock_blob_sas_generation.return_value = expected_sas_token

    client = DestinyBlobStorageClient()
    sas_token = client.get_single_blob_sas_token("test_blob.jsonl")

    assert (
        sas_token == expected_sas_token
    ), "Check that the SAS token is generated correctly"


def test_destinyblobstorageclient_get_blob_sas_pair(mocker, test_settings) -> None:
    """Test DestinyBlobStorageClient get_blob_sas_pair method."""
    test_blob_name = "test_blob.jsonl"
    test_account_name = test_settings.STORAGE_BLOB_ACCOUNT
    test_container_name = test_settings.STORAGE_BLOB_CONTAINER
    expected_sas_token = "test_sas_token"  # noqa: S105
    expected_blob_url = f"https://{test_account_name}.blob.core.windows.net/{test_container_name}/{test_blob_name}?{expected_sas_token}"

    mock_blob_sas_generation = mocker.patch(
        "refresh_requester.blob_storage.generate_blob_sas"
    )
    mock_blob_sas_generation.return_value = expected_sas_token

    client = DestinyBlobStorageClient()
    sas_pair = client.get_blob_sas_pair(test_blob_name)

    assert (
        sas_pair["blob_name"] == test_blob_name
    ), "Check that the blob name is returned correctly"
    assert (
        sas_pair["sas_url"] == expected_blob_url
    ), "Check that the SAS URL is generated correctly"


def test_destinyblobstorageclient_get_all_blob_url_pairs(mocker, test_settings) -> None:
    """Test DestinyBlobStorageClient get_all_blob_url_pairs method."""
    mock_blob_sas_generation = mocker.patch(
        "refresh_requester.blob_storage.generate_blob_sas"
    )
    mock_blob_sas_generation.return_value = "test_sas_token"

    expected_sas_url = (
        f"https://{test_settings.STORAGE_BLOB_ACCOUNT}.blob.core.windows.net/"
        f"{test_settings.STORAGE_BLOB_CONTAINER}/{{blob_name}}?test_sas_token"
    )
    test_blobs = [
        "blob1.jsonl",
        "blob2.jsonl",
    ]
    mock_list_blobs = mocker.patch(
        "refresh_requester.blob_storage.DestinyBlobStorageClient.list_all_blobs"
    )
    mock_list_blobs.return_value = test_blobs

    client = DestinyBlobStorageClient()
    blob_pairs = client.get_all_blob_url_pairs()

    assert len(blob_pairs) == len(
        test_blobs
    ), "Check that all blob URL pairs are returned"
    assert blob_pairs[0]["blob_name"] == "blob1.jsonl", "Check first blob name"
    assert blob_pairs[1]["blob_name"] == "blob2.jsonl", "Check second blob name"
    assert blob_pairs[0]["sas_url"] == expected_sas_url.format(
        blob_name="blob1.jsonl"
    ), "Check first blob SAS URL"
    assert blob_pairs[1]["sas_url"] == expected_sas_url.format(
        blob_name="blob2.jsonl"
    ), "Check second blob SAS URL"
