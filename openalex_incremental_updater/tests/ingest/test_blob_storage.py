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
    blob_upload_multipart,
    get_blob_service_client,
)


@pytest.mark.asyncio
async def test_get_blob_service_client(
    mocker: MockerFixture, set_test_environment_variables: Generator
):
    """Test getting the blob service client."""
    mock_blob_service_instance = mocker.MagicMock()
    mock_blob_service_instance.close = mocker.AsyncMock()

    mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.BlobServiceClient",
        return_value=mock_blob_service_instance,
    )

    async with get_blob_service_client() as client:
        assert (
            client == mock_blob_service_instance
        ), "Check that the returned blob service client is correct"


@pytest.mark.asyncio
async def test_get_blob_service_client_failure_azure_error(
    mocker: MockerFixture, set_test_environment_variables: Generator
):
    """Test getting the blob service client."""
    mock_blob_service_instance = mocker.MagicMock()
    mock_blob_service_instance.close = mocker.AsyncMock()

    mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.BlobServiceClient",
        side_effect=AzureError("Test error"),
    )

    with pytest.raises(BlobUploadError) as error:
        async with get_blob_service_client():
            pass

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

    mock_blob_service_instance = mocker.MagicMock()
    mock_blob_service_instance.close = mocker.AsyncMock()
    mock_blob_service_instance.get_blob_client.return_value = mock_blob_client

    mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.BlobServiceClient",
        return_value=mock_blob_service_instance,
    )

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

    mock_blob_service_instance = mocker.MagicMock()
    mock_blob_service_instance.close = mocker.AsyncMock()
    mock_blob_service_instance.get_blob_client.return_value = mock_blob_client
    mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.BlobServiceClient",
        return_value=mock_blob_service_instance,
    )

    with pytest.raises(BlobUploadError) as error:
        await blob_upload(test_data_bytes_iter, test_filename, chunk_size=chunk_size)
    assert "Test uploading error" in str(error.value)


@pytest.mark.parametrize(
    "original_exception",
    [
        AzureError("Azure error during upload"),
        ClientAuthenticationError("Auth error during upload"),
        HttpResponseError("HTTP error during upload"),
        ResourceExistsError("Resource exists error during upload"),
        ResourceNotFoundError("Resource not found error during upload"),
        ServiceRequestError("Service request error during upload"),
    ],
)
@pytest.mark.asyncio
async def test_blob_upload_failure_delete_raises(
    mocker: MockerFixture,
    set_test_environment_variables: Generator,
    original_exception: Exception,
):
    """If deleting the blob raises, ensure original upload error is still raised."""
    test_data = '{"key1": "value1"}\n'

    async def async_gen(data):
        for line in data.splitlines(keepends=True):
            yield line.encode("utf-8")

    test_data_bytes_iter = async_gen(test_data)
    chunk_size = len(test_data.encode("utf-8"))

    test_filename = "a_test_path/to_a/test_blob.jsonl"

    mock_blob_client = mocker.AsyncMock()
    mock_blob_client.stage_block.side_effect = original_exception
    mock_blob_client.delete_blob.side_effect = Exception("Delete failed")

    mock_blob_service_instance = mocker.MagicMock()
    mock_blob_service_instance.close = mocker.AsyncMock()
    mock_blob_service_instance.get_blob_client.return_value = mock_blob_client
    mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.BlobServiceClient",
        return_value=mock_blob_service_instance,
    )

    with pytest.raises(BlobUploadError) as error:
        await blob_upload(test_data_bytes_iter, test_filename, chunk_size=chunk_size)

    assert str(original_exception) in str(
        error.value
    ), "Check that the original error message is in the raised BlobUploadError"
    assert (
        mock_blob_client.delete_blob.await_count == 1
    ), "Check that delete_blob was attempted exactly once"


@pytest.mark.asyncio
async def test_blob_upload_multipart_single_part(
    mocker: MockerFixture, set_test_environment_variables: Generator
):
    """Test multipart upload with fewer lines than batch_size produces one part."""
    lines = [b'{"key": "value1"}\n', b'{"key": "value2"}\n']
    mock_blob_upload = mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.blob_upload",
        side_effect=lambda _, filename: filename,
    )

    async def async_gen():
        for line in lines:
            yield line

    result = await blob_upload_multipart(async_gen(), "base_name", batch_size=10)
    assert result == ["base_name_part_001.jsonl"]
    assert mock_blob_upload.call_count == 1


@pytest.mark.asyncio
async def test_blob_upload_multipart_multiple_parts(
    mocker: MockerFixture, set_test_environment_variables: Generator
):
    """Test multipart upload splits correctly across multiple parts."""
    lines = [f'{{"key": "value{i}"}}\n'.encode() for i in range(25)]
    mock_blob_upload = mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.blob_upload",
        side_effect=lambda _, filename: filename,
    )

    async def async_gen():
        for line in lines:
            yield line

    result = await blob_upload_multipart(async_gen(), "base_name", batch_size=10)
    assert result == [
        "base_name_part_001.jsonl",
        "base_name_part_002.jsonl",
        "base_name_part_003.jsonl",
    ]
    expected_parts = 3
    assert mock_blob_upload.call_count == expected_parts


@pytest.mark.asyncio
async def test_blob_upload_multipart_empty_input(
    mocker: MockerFixture, set_test_environment_variables: Generator
):
    """Test multipart upload with empty input still produces one part."""
    mock_blob_upload = mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.blob_upload",
        side_effect=lambda _, filename: filename,
    )

    async def async_gen():
        return
        yield

    result = await blob_upload_multipart(async_gen(), "base_name", batch_size=10)
    assert result == ["base_name_part_001.jsonl"]
    assert mock_blob_upload.call_count == 1


@pytest.mark.asyncio
async def test_blob_upload_multipart_exact_boundary(
    mocker: MockerFixture, set_test_environment_variables: Generator
):
    """Test multipart upload when line count exactly equals batch_size."""
    lines = [f'{{"key": "value{i}"}}\n'.encode() for i in range(10)]
    mock_blob_upload = mocker.patch(
        "openalex_incremental_updater.ingest.blob_storage.blob_upload",
        side_effect=lambda _, filename: filename,
    )

    async def async_gen():
        for line in lines:
            yield line

    result = await blob_upload_multipart(async_gen(), "base_name", batch_size=10)
    assert result == ["base_name_part_001.jsonl"]
    assert mock_blob_upload.call_count == 1
