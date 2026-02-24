"""Tests for dr_client.py."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from openalex_snapshot_processor.dr_client import DRClient, DRClientError

# Pre-generate valid v4 UUIDs for test data
RECORD_UUID = uuid4()
BATCH_UUID = uuid4()


@pytest.fixture
def mock_session():
    """Return a mocked requests.Session."""
    return MagicMock()


@pytest.fixture
def dr_client(test_settings, mock_session):
    """Return a DRClient with mocked session and token fetch."""
    mock_session.headers = {}
    with patch(
        "openalex_snapshot_processor.dr_client._create_retry_session",
        return_value=mock_session,
    ):
        mock_session.get.return_value = MagicMock(
            json=MagicMock(return_value={"access_token": "fake-token"}),
        )
        client = DRClient(test_settings)
        mock_session.reset_mock()
        yield client


def test_init_fetches_token(test_settings) -> None:
    """DRClient.__init__ should fetch a token immediately."""
    mock_sess = MagicMock()
    mock_sess.headers = {}
    mock_sess.get.return_value = MagicMock(
        json=MagicMock(return_value={"access_token": "init-token"}),
    )
    with patch(
        "openalex_snapshot_processor.dr_client._create_retry_session",
        return_value=mock_sess,
    ):
        client = DRClient(test_settings)

    assert client._session.headers["Authorization"] == "Bearer init-token"


def test_create_import_record(dr_client, mock_session) -> None:
    """create_import_record should POST and return an ImportRecordRead."""
    mock_session.post.return_value = MagicMock(
        json=MagicMock(
            return_value={
                "id": str(RECORD_UUID),
                "processor_name": "Test Feeder",
                "processor_version": "0.0.1",
                "source_name": "test-source",
                "expected_reference_count": -1,
                "status": "created",
            }
        ),
    )

    record = dr_client.create_import_record()

    mock_session.post.assert_called_once()
    call_url = mock_session.post.call_args[0][0]
    assert "/imports/records/" in call_url
    assert record.id == RECORD_UUID


def test_register_batch(dr_client, mock_session) -> None:
    """register_batch should POST with SAS URL and return ImportBatchRead."""
    mock_session.post.return_value = MagicMock(
        json=MagicMock(
            return_value={
                "id": str(BATCH_UUID),
                "import_record_id": str(RECORD_UUID),
                "storage_url": "https://example.com/blob?sig=abc",
                "status": "created",
            }
        ),
    )

    batch = dr_client.register_batch(RECORD_UUID, "https://example.com/blob?sig=abc")

    mock_session.post.assert_called_once()
    assert batch.id == BATCH_UUID


def test_get_batch_status(dr_client, mock_session) -> None:
    """get_batch_status should GET and return ImportBatchRead."""
    mock_session.get.return_value = MagicMock(
        json=MagicMock(
            return_value={
                "id": str(BATCH_UUID),
                "import_record_id": str(RECORD_UUID),
                "storage_url": "https://example.com/blob?sig=abc",
                "status": "completed",
            }
        ),
    )

    result = dr_client.get_batch_status(RECORD_UUID, BATCH_UUID)

    mock_session.get.assert_called_once()
    assert str(result.status) == "completed"


def test_finalise_import_record(dr_client, mock_session) -> None:
    """finalise_import_record should PATCH the finalise endpoint."""
    mock_session.patch.return_value = MagicMock()

    dr_client.finalise_import_record(RECORD_UUID)

    mock_session.patch.assert_called_once()
    call_url = mock_session.patch.call_args[0][0]
    assert "/finalise/" in call_url


def test_get_import_record(dr_client, mock_session) -> None:
    """get_import_record should GET and return ImportRecordRead."""
    mock_session.get.return_value = MagicMock(
        json=MagicMock(
            return_value={
                "id": str(RECORD_UUID),
                "processor_name": "Test",
                "processor_version": "0.0.1",
                "source_name": "test",
                "expected_reference_count": -1,
                "status": "created",
            }
        ),
    )

    record = dr_client.get_import_record(RECORD_UUID)
    assert record.id == RECORD_UUID


def test_token_fetch_failure(test_settings) -> None:
    """DRClient should raise DRClientError when no access_token in response."""
    mock_sess = MagicMock()
    mock_sess.headers = {}
    mock_sess.get.return_value = MagicMock(
        json=MagicMock(return_value={}),
    )
    with (
        patch(
            "openalex_snapshot_processor.dr_client._create_retry_session",
            return_value=mock_sess,
        ),
        pytest.raises(DRClientError, match="No access_token"),
    ):
        DRClient(test_settings)
