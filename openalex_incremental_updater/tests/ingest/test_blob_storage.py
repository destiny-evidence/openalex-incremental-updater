from collections.abc import Generator

import pytest
from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    HttpResponseError,
    ResourceExistsError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from pytest_mock import MockerFixture

from openalex_incremental_updater.ingest.blob_storage import (
    BlobUploadError,
    blob_upload,
    get_blob_service_client,
)


@pytest.mark.asyncio
async def test_get_blob_service_client(
    mocker: MockerFixture, set_test_environment_variables: Generator
):
    """Test getting the blob service client."""
    mock_blob_service = mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.BlobServiceClient"
    )
    blob_service_client = mock_blob_service.return_value

    result = await get_blob_service_client()

    assert (
        result == blob_service_client
    ), "Check that the returned blob service client is correct"


@pytest.mark.asyncio
async def test_get_blob_service_client_failure_azure_error(
    mocker: MockerFixture, set_test_environment_variables: Generator
):
    """Test getting the blob service client."""
    mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.BlobServiceClient",
        side_effect=AzureError("Test error"),
    )

    with pytest.raises(BlobUploadError) as error:
        await get_blob_service_client()

    assert "Error getting blob client: Test error" in str(
        error.value
    ), "Check that the error message is correct"


@pytest.mark.asyncio
async def test_blob_upload_success(
    mocker: MockerFixture, set_test_environment_variables: Generator
):
    """Test successful blob upload."""
    test_data = (
        '{"key1": "value1", "key2": "value2"}\n{"key3": "value3", "key4": "value4"}\n'
    )

    async def async_gen(data):
        for line in data.splitlines(keepends=True):
            yield line.encode("utf-8")

    test_data_bytes_iter = async_gen(test_data)
    test_filename = "a_test_path/to_a/test_blob.jsonl"
    mock_blob_client = mocker.AsyncMock()
    mock_blob_service = mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.BlobServiceClient"
    )

    mock_blob_service.return_value.get_blob_client.return_value = mock_blob_client

    result = await blob_upload(test_data_bytes_iter, test_filename)
    assert result == test_filename, "Check that the returned filename matches the input"
    assert (
        mock_blob_client.commit_block_list.call_count == 1
    ), "Check that commit_block_list was called once"


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
@pytest.mark.asyncio
async def test_blob_upload_failure(
    mocker: MockerFixture,
    set_test_environment_variables: Generator,
    exception: type[Exception],
):
    """Test failed blob upload."""
    test_data = (
        '{"key1": "value1", "key2": "value2"}\n{"key3": "value3", "key4": "value4"}\n'
    )

    async def async_gen(data):
        for line in data.splitlines(keepends=True):
            yield line.encode("utf-8")

    test_data_bytes_iter = async_gen(test_data)
    lines = list(test_data.splitlines(keepends=True))
    chunk_size = len(lines[0].encode("utf-8"))

    test_filename = "a_test_path/to_a/test_blob.jsonl"

    mock_blob_client = mocker.AsyncMock()
    mock_blob_client.stage_block.side_effect = [{}, exception("Test uploading error")]

    mock_get_blob_service_client = mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.BlobServiceClient"
    )
    mock_get_blob_service_client.return_value.get_blob_client.return_value = (
        mock_blob_client
    )

    with pytest.raises(BlobUploadError) as error:
        await blob_upload(test_data_bytes_iter, test_filename, chunk_size=chunk_size)
    assert "Test uploading error" in str(error.value)
