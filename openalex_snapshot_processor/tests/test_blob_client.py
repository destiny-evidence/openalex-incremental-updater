"""Tests for blob_client.py."""

from unittest.mock import MagicMock, patch

import pytest

from openalex_snapshot_processor.blob_client import BlobUploadError, SnapshotBlobClient


@pytest.fixture
def blob_client(test_settings):
    """Return a SnapshotBlobClient with a mocked BlobServiceClient."""
    with patch(
        "openalex_snapshot_processor.blob_client._build_service_client"
    ) as mock_build:
        mock_bsc = MagicMock()
        mock_build.return_value = mock_bsc
        client = SnapshotBlobClient(test_settings)
        yield client


def test_upload_file_raw(blob_client, tmp_path) -> None:
    """upload_file should upload raw bytes when DECOMPRESS_ON_UPLOAD is False."""
    test_file = tmp_path / "batch.jsonl.gz"
    test_file.write_bytes(b"\x1f\x8b fake gzip content")

    mock_blob = MagicMock()
    blob_client._service_client.get_blob_client.return_value = mock_blob

    blob_client.upload_file(test_file, "snapshot_bulk/batch.jsonl.gz")

    mock_blob.upload_blob.assert_called_once()
    call_kwargs = mock_blob.upload_blob.call_args
    assert call_kwargs.kwargs["overwrite"] is True


def test_upload_file_decompress(test_settings, tmp_path) -> None:
    """upload_file should decompress when DECOMPRESS_ON_UPLOAD is True."""
    import gzip

    test_settings.DECOMPRESS_ON_UPLOAD = True

    test_file = tmp_path / "batch.jsonl.gz"
    with gzip.open(test_file, "wb") as f:
        f.write(b'{"id": "test"}\n')

    with patch("openalex_snapshot_processor.blob_client._build_service_client"):
        client = SnapshotBlobClient(test_settings)
        mock_blob = MagicMock()
        client._service_client.get_blob_client.return_value = mock_blob

        client.upload_file(test_file, "snapshot_bulk/batch.jsonl")

        mock_blob.upload_blob.assert_called_once()
        uploaded_data = mock_blob.upload_blob.call_args[0][0]
        assert b'{"id": "test"}' in uploaded_data


def test_upload_file_failure(blob_client, tmp_path) -> None:
    """upload_file should raise BlobUploadError on Azure SDK failure."""
    test_file = tmp_path / "batch.jsonl.gz"
    test_file.write_bytes(b"data")

    mock_blob = MagicMock()
    mock_blob.upload_blob.side_effect = Exception("Azure boom")
    blob_client._service_client.get_blob_client.return_value = mock_blob

    with pytest.raises(BlobUploadError, match="Azure boom"):
        blob_client.upload_file(test_file, "snapshot_bulk/batch.jsonl.gz")


def test_generate_sas_url(blob_client) -> None:
    """generate_sas_url should return a URL with account, container, and blob."""
    with patch(
        "openalex_snapshot_processor.blob_client.generate_blob_sas",
        return_value="sig=abc123",
    ):
        url = blob_client.generate_sas_url("snapshot_bulk/batch_00001.jsonl.gz")

    assert "fakeaccount" in url
    assert "fakecontainer" in url
    assert "snapshot_bulk/batch_00001.jsonl.gz" in url
    assert "sig=abc123" in url


def test_blob_exists(blob_client) -> None:
    """blob_exists should delegate to the Azure blob client."""
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    blob_client._service_client.get_blob_client.return_value = mock_blob

    assert blob_client.blob_exists("snapshot_bulk/batch_00001.jsonl.gz") is True
    mock_blob.exists.assert_called_once()
