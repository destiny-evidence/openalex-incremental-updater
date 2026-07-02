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
from time_machine import travel

from refresh_requester.blob_storage import (
    BlobUploadError,
    DestinyBlobStorageClient,
    blob_upload,
    check_previous_file_dates,
    determine_next_fetch_date,
    format_metadata_blob_name,
    list_blobs_in_storage,
    metadata_blob_prefix,
)


class MockBlob:
    def __init__(self, name: str):
        self.name = name


@pytest.mark.parametrize(
    ("metadata_blobs", "expected_result"),
    [
        (
            [
                "ingestion_metadata/destiny_repository_openalex_ingestion_batch_from_2025-03-01_to_2025-03-01.jsonl"
            ],
            date(2025, 3, 1),
        ),
        (
            [
                "ingestion_metadata/destiny_repository_openalex_ingestion_batch_from_2025-03-01_to_2025-03-01.jsonl",
                "ingestion_metadata/destiny_repository_openalex_ingestion_batch_from_2025-03-02_to_2025-03-02.jsonl",
                "ingestion_metadata/destiny_repository_openalex_ingestion_batch_from_2025-03-03_to_2025-03-03.jsonl",
            ],
            date(2025, 3, 3),
        ),
        (
            [
                "ingestion_metadata/destiny_repository_openalex_ingestion_batch_from_2025-03-01_to_2025-03-05.jsonl",
                "openalex_refresh_from_date_2025-03-01_to_2025-03-01_refreshed_on_2025-03-02.jsonl",
                "ingestion_metadata/destiny_repository_solr_ingestion_batch_from_2025-03-01_to_2025-06-01.jsonl",
            ],
            date(2025, 3, 5),
        ),
    ],
)
def test_check_previous_file_dates_metadata_blobs_found(
    mocker, metadata_blobs, expected_result, test_settings
):
    """Check `check_previous_file_dates` returns latest date found in blob names."""
    mocker.patch(
        "refresh_requester.blob_storage.list_blobs_in_storage",
        return_value=metadata_blobs,
    )

    result = check_previous_file_dates(test_settings)

    assert (
        result == expected_result
    ), f"Expected the same date as the latest stop date, got {result}"


def test_check_previous_file_dates_malformed_metadata_blob_skipped(
    mocker, caplog, test_settings
):
    """
    Test that metadata blobs with an unparseable stop date are skipped with a warning.

    A malformed blob name must not crash the pipeline; it should be skipped
    and a warning logged, with valid blobs still used.
    """
    metadata_prefix = metadata_blob_prefix("openalex")
    valid_metadata_blob_name = metadata_prefix + "2025-06-01.jsonl"
    invalid_metadata_blob_name = metadata_prefix + "not-a-date.jsonl"
    blob_names = [valid_metadata_blob_name, invalid_metadata_blob_name]

    valid_blob_metadata_derived_date_string = (
        valid_metadata_blob_name[len(metadata_blob_prefix("openalex")) :]
        .removesuffix(".jsonl")
        .split("_to_")[-1]
    )
    expected_valid_date = date.fromisoformat(valid_blob_metadata_derived_date_string)

    mocker.patch(
        "refresh_requester.blob_storage.list_blobs_in_storage",
        return_value=blob_names,
    )

    with caplog.at_level("WARNING"):
        result = check_previous_file_dates(test_settings)

    assert result == expected_valid_date, "Valid metadata blob should still be used"
    assert invalid_metadata_blob_name in caplog.text


def test_check_previous_file_dates_returns_none_no_files_found(mocker, test_settings):
    """Test check_previous_file_dates function returns None if no files are found."""
    mocker.patch(
        "refresh_requester.blob_storage.list_blobs_in_storage", return_value=[]
    )

    result = check_previous_file_dates(test_settings)

    assert result is None, "Expected None when no metadata blobs are found"


@pytest.mark.parametrize(
    "blob_name_list",
    [
        [
            "openalex_refresh_2025-03-01.jsonl",
            "openalex_refresh_2025-03-02.jsonl",
            "openalex_refresh_2025-03-03.jsonl",
        ],
        [
            "openalex_refresh_2025-03-01_part1.jsonl",
            "openalex_refresh_2025-03-01_part2.jsonl",
            "openalex_refresh_2025-03-02_part1.jsonl",
        ],
    ],
)
def test_list_blobs_in_storage(mocker, blob_name_list, test_settings):
    """Test list_blobs_in_storage function works as expected."""
    mock_container_client = mocker.Mock()
    mock_blob_service = mocker.patch("refresh_requester.blob_storage.BlobServiceClient")

    mock_blob_service.return_value.get_container_client.return_value = (
        mock_container_client
    )

    mock_blob_names = [MockBlob(name) for name in blob_name_list]

    mock_container_client.list_blobs.return_value = mock_blob_names

    result = list_blobs_in_storage(test_settings)

    assert result == [blob.name for blob in mock_blob_names]


def test_list_blobs_in_storage_with_prefix_filter(mocker, test_settings):
    """
    Test list_blobs_in_storage passes prefix_filter as name_starts_with to the SDK.

    The Azure SDK handles the actual server-side filtering via name_starts_with.
    This test verifies that the correct keyword argument is used and that the
    function returns only what the Azure SDK gives back.
    """
    all_blob_names = [
        "openalex_refresh_2025-03-01.jsonl",
        "openalex_refresh_2025-03-02.jsonl",
        "ingestion_metadata/destiny_repository_openalex_ingestion_batch_from_2025-03-01_to_2025-03-01.jsonl",
    ]
    prefix_filter = metadata_blob_prefix("openalex")
    all_blobs = [MockBlob(name) for name in all_blob_names]

    mock_container_client = mocker.Mock()
    mock_blob_service = mocker.patch("refresh_requester.blob_storage.BlobServiceClient")
    mock_blob_service.return_value.get_container_client.return_value = (
        mock_container_client
    )

    def blob_storage_list_blobs(name_starts_with: str | None = None) -> list[MockBlob]:
        """
        Mock function to simulate Azure Blob Storage list_blobs behavior with name_starts_with filtering.

        Args:
            name_starts_with (str | None): The prefix to filter blobs by. If None, all blobs are returned.

        Returns:
            list[MockBlob]: A list of MockBlob objects that match the prefix filter.

        """
        if name_starts_with:
            return [b for b in all_blobs if b.name.startswith(name_starts_with)]
        return all_blobs

    mock_container_client.list_blobs.side_effect = blob_storage_list_blobs

    result = list_blobs_in_storage(test_settings, prefix_filter=prefix_filter)

    mock_container_client.list_blobs.assert_called_once_with(
        name_starts_with=prefix_filter
    )
    expected = [name for name in all_blob_names if name.startswith(prefix_filter)]
    assert result == expected


def test_blob_upload_success(mocker, test_settings):
    """Test successful blob upload."""
    test_data = (
        '{"key1": "value1", "key2": "value2"},{"key3": "value3", "key4": "value4"}'
    )
    test_filename = "a_test_path/to_a/test_blob.jsonl"
    mock_blob_client = mocker.Mock()
    mock_blob_service = mocker.patch("refresh_requester.blob_storage.BlobServiceClient")

    mock_blob_service.return_value.get_blob_client.return_value = mock_blob_client

    result = blob_upload(test_settings, test_data, test_filename)
    assert result == test_filename, "Check that the returned filename matches the input"
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
    test_filename = "a_test_path/to_a/test_blob.jsonl"

    mock_blob_client = mocker.Mock()
    mock_blob_client.upload_blob.side_effect = exception("Test uploading error")

    mock_get_blob_service_client = mocker.patch(
        "refresh_requester.blob_storage.get_blob_service_client"
    )
    mock_get_blob_service_client.return_value.get_blob_client.return_value = (
        mock_blob_client
    )

    with pytest.raises(BlobUploadError) as error:
        blob_upload(test_settings, test_data, test_filename)
    assert "Test uploading error" in str(error.value)


def test_destinyblobstorageclient_init(mocker, test_settings) -> None:
    """Test DestinyBlobStorageClient initialization."""
    mocker.patch("refresh_requester.blob_storage.BlobServiceClient")
    client = DestinyBlobStorageClient(test_settings)
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

    client = DestinyBlobStorageClient(test_settings)
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

    client = DestinyBlobStorageClient(test_settings)
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

    client = DestinyBlobStorageClient(test_settings)
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

    client = DestinyBlobStorageClient(test_settings)
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


@travel("2026-05-20T12:00:00+00")
def test_determine_next_fetch_date_no_stop_date(mocker, test_settings):
    """Test determine_next_fetch_date returns fetch date if no stop date is set."""
    date_yesterday = date.today() - timedelta(days=1)
    fetch_date = date_yesterday
    mocker.patch(
        "refresh_requester.blob_storage.check_previous_file_dates", return_value=None
    )
    result = determine_next_fetch_date(test_settings)
    assert (
        result == fetch_date
    ), "Expected fetch date to be returned when no stop date is set"


@travel("2026-05-20T12:00:00+00")
def test_determine_next_fetch_date_previous_stop_date_found(mocker, test_settings):
    """Test determine_next_fetch_date returns the day after the latest stop date."""
    date_yesterday = date.today() - timedelta(days=1)
    date_two_days_ago = date.today() - timedelta(days=2)
    mocker.patch(
        "refresh_requester.blob_storage.check_previous_file_dates",
        return_value=date_two_days_ago,
    )
    result = determine_next_fetch_date(test_settings)
    assert (
        result == date_yesterday
    ), "Expect the day after the latest stop date to be returned"


@pytest.mark.parametrize(
    ("data_source", "expected_prefix"),
    [
        (
            "openalex",
            "ingestion_metadata/destiny_repository_openalex_ingestion_batch_from_",
        ),
        ("solr", "ingestion_metadata/destiny_repository_solr_ingestion_batch_from_"),
    ],
)
def test_metadata_blob_prefix(data_source, expected_prefix) -> None:
    """Test the metadata_blob_prefix function."""
    result = metadata_blob_prefix(data_source)

    assert (
        result == expected_prefix
    ), "The metadata blob prefix should match the expected format"


def test_format_metadata_blob_name() -> None:
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
