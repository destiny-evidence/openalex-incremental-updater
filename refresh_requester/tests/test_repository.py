from datetime import UTC, datetime
from uuid import uuid4

import freezegun
import pytest
from destiny_sdk.imports import (
    CollisionStrategy,
    ImportBatchRead,
    ImportBatchStatus,
    ImportBatchSummary,
    ImportRecordRead,
    ImportRecordStatus,
    ImportResultStatus,
)

from refresh_requester.repository import (
    DestinyRepositoryContentUploader,
    upload_blob_storage_contents_to_repository,
)


@freezegun.freeze_time("2025-06-12T02:00:00+00")
def test_register_new_import_success(mocker, test_settings) -> None:
    """Test the register_new_import method."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    test_datetime = datetime.now(tz=UTC)
    uploader = DestinyRepositoryContentUploader(test_settings)
    test_response_dict = {
        "id": uuid4(),
        "status": ImportRecordStatus.CREATED.value,
        "processor_name": "Test Processor",
        "processor_version": "999.9.9",
        "expected_reference_count": -1,
        "source_name": "Test Source",
    }
    mocker.patch.object(
        uploader.session,
        "post",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: test_response_dict,
        ),
    )
    expected_response_dict = {
        "search_string": test_response_dict.get("search_string"),
        "searched_at": test_datetime,
        "processor_name": test_response_dict.get("processor_name"),
        "processor_version": test_response_dict.get("processor_version"),
        "notes": test_response_dict.get("notes"),
        "expected_reference_count": test_response_dict.get("expected_reference_count"),
        "source_name": test_response_dict.get("source_name"),
        "id": test_response_dict.get("id"),
        "status": test_response_dict.get("status"),
        "batches": test_response_dict.get("batches"),
    }

    response = uploader.register_new_import()
    response_dict = response.model_dump()
    assert (
        response_dict == expected_response_dict
    ), "Response should match the expected structure and values"


def test_register_import_batch_for_single_blob(mocker, test_settings) -> None:
    """Test the register_import_batch_for_single_blob method."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)
    test_record_id = uuid4()

    test_status = ImportRecordStatus.CREATED
    test_import_record = ImportRecordRead(
        id=test_record_id,
        status=test_status,
        processor_name="Test Processor",
        processor_version="999.9.9",
        expected_reference_count=-1,
        source_name="Test Source",
    )
    mock_import_batch_read_response = ImportBatchRead(
        id=uuid4(),
        storage_url="http://test-storage-url",
        import_record_id=test_record_id,
        status=test_import_record.status,
        collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
    )
    mocker.patch.object(
        uploader.session,
        "post",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: mock_import_batch_read_response,
        ),
    )

    response = uploader.register_import_batch_for_single_blob(
        blob_name="test-blob",
        sas_url="http://test-sas-url",
        import_record=test_import_record,
    )
    assert isinstance(
        response, ImportBatchRead
    ), "Response should be an instance of ImportBatchRead"
    assert (
        response.status == test_status
    ), "Response status should match the import record status"


@freezegun.freeze_time("2025-06-12T02:00:00+00")
def test_finalise_import_record(mocker, test_settings) -> None:
    """Test the finalise_import_record method."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)
    test_id = uuid4()
    http_no_content_status = 204

    mocker.patch.object(
        uploader.session,
        "patch",
        return_value=mocker.Mock(
            status_code=204,
        ),
    )
    response = uploader.finalise_import_record(test_id)
    assert (
        response.status_code == http_no_content_status
    ), "Response status code should be 204 No Content"


@pytest.mark.parametrize(
    ("test_status", "expected_result"),
    [
        (ImportBatchStatus.COMPLETED, True),
        (ImportBatchStatus.STARTED, False),
        (ImportBatchStatus.FAILED, False),
        (ImportBatchStatus.CANCELLED, False),
    ],
)
def test_check_if_import_batch_completed_status_correct(
    mocker, test_settings, test_status, expected_result
) -> None:
    """
    Test the check_if_import_batch_completed method.

    When the batch is completed return the correct status as a boolean.
    """
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)
    test_id = uuid4()
    mocked_response = ImportBatchRead(
        id=test_id,
        storage_url="http://test-storage-url",
        import_record_id=test_id,
        status=test_status,
        collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
    )
    mocker.patch.object(
        uploader.session,
        "get",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: mocked_response.model_dump(),
        ),
    )

    result = uploader.check_if_import_batch_completed(test_id)
    assert (
        result is expected_result
    ), "Result should match the expected boolean value based on the import batch status"


@freezegun.freeze_time("2025-06-12T02:00:00+00")
def test_get_import_batch_summary(mocker, test_settings) -> None:
    """Test the get_import_batch_summary method."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)
    test_import_batch_id = uuid4()
    test_summary_id = uuid4()

    mock_summary_response = ImportBatchSummary(
        storage_url="http://test-storage-url",
        id=test_summary_id,
        import_batch_id=test_import_batch_id,
        import_batch_status=ImportBatchStatus.COMPLETED,
        collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
        results={
            ImportResultStatus.COMPLETED.value: 10,
            ImportResultStatus.FAILED.value: 0,
        },
        failure_details=None,
    )
    http_ok_status = 200

    mocker.patch.object(
        uploader.session,
        "get",
        return_value=mocker.Mock(
            status_code=http_ok_status, json=lambda: mock_summary_response.model_dump()
        ),
    )
    response = uploader.get_import_batch_summary(test_import_batch_id)
    assert (
        response.import_batch_status == ImportBatchStatus.COMPLETED
    ), "Import batch status should be COMPLETED"


@freezegun.freeze_time("2025-06-12T02:00:00+00")
def test_upload_blob_storage_contents_to_repository_success_single_blob(
    mocker, test_settings
):
    """
    Test upload_blob_storage_contents_to_repository end-to-end logic.

    Tests the case where a single blob is uploaded to the repository.
    """
    mocker.patch("refresh_requester.repository.get_token", return_value="test-token")
    mock_blob_url_pairs = [{"blob_name": "test-blob", "sas_url": "http://test-sas-url"}]
    mock_blob_storage_client = mocker.patch(
        "refresh_requester.repository.DestinyBlobStorageClient.get_all_blob_url_pairs",
        return_value=mock_blob_url_pairs,
    )
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    test_summary_id = uuid4()
    http_no_content_status = 204

    mock_import_record = ImportRecordRead(
        id=test_import_record_id,
        status=ImportRecordStatus.CREATED,
        processor_name="Test Processor",
        processor_version="999.9.9",
        expected_reference_count=-1,
        source_name="Test Source",
    )

    mock_batch_registration = ImportBatchRead(
        id=test_batch_id,
        storage_url="http://test-storage-url",
        import_record_id=test_import_record_id,
        status=ImportBatchStatus.CREATED,
        collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
    )

    mock_batch_summary = ImportBatchSummary(
        storage_url="http://test-storage-url",
        id=test_summary_id,
        import_batch_id=test_batch_id,
        import_batch_status=ImportBatchStatus.COMPLETED,
        collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
        results={
            ImportResultStatus.COMPLETED.value: 10,
            ImportResultStatus.FAILED.value: 0,
        },
        failure_details=None,
    )

    mock_register_new_import = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_new_import",
        return_value=mock_import_record,
    )
    mock_register_import_batch = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_import_batch_for_single_blob",
        return_value=mock_batch_registration,
    )
    mock_finalise_import = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.finalise_import_record",
        return_value=mocker.Mock(status_code=http_no_content_status),
    )
    mock_check_completed = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.check_if_import_batch_completed",
        return_value=True,
    )
    mock_get_summary = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.get_import_batch_summary",
        return_value=mock_batch_summary,
    )

    mocker.patch("refresh_requester.repository.time.sleep", return_value=None)

    upload_blob_storage_contents_to_repository(
        test_settings, max_retries=2, blob_to_upload="test-blob"
    )
    (
        mock_blob_storage_client.assert_called_once_with("test-blob"),
        "get_all_blob_url_pairs should be called with 'test-blob' to get the specific blob",
    )
    (
        mock_register_new_import.assert_called_once(),
        "register_new_import should be called once",
    )
    (
        mock_register_import_batch.assert_called_once_with(
            "test-blob",
            "http://test-sas-url",
            mock_import_record,
        ),
        "register_import_batch_for_single_blob should be called once with the blob name, SAS URL and import record",
    )
    (
        mock_finalise_import.assert_called_once_with(test_import_record_id),
        "Finalise import record should be called once",
    )
    (
        mock_check_completed.assert_called_once_with(test_batch_id),
        "check_if_import_batch_completed should be called with the batch ID",
    )
    (
        mock_get_summary.assert_called_once_with(test_batch_id),
        "get_import_batch_summary should be called with the batch ID",
    )


def test_upload_blob_storage_contents_to_repository_success_multiple_blobs(
    mocker, test_settings
):
    """
    Test upload_blob_storage_contents_to_repository end-to-end logic.

    Tests the case where multiple blobs are uploaded to the repository.
    """
    mocker.patch("refresh_requester.repository.get_token", return_value="test-token")
    mock_blob_url_pairs = [
        {"blob_name": "test-blob-1", "sas_url": "http://test-sas-url-1"},
        {"blob_name": "test-blob-2", "sas_url": "http://test-sas-url-2"},
    ]
    mock_blob_storage_client = mocker.patch(
        "refresh_requester.repository.DestinyBlobStorageClient.get_all_blob_url_pairs",
        return_value=mock_blob_url_pairs,
    )
    test_import_record_id = uuid4()
    test_batch_ids = [uuid4(), uuid4()]
    test_summary_ids = [uuid4(), uuid4()]
    http_no_content_status = 204

    mock_import_record = ImportRecordRead(
        id=test_import_record_id,
        status=ImportRecordStatus.CREATED,
        processor_name="Test Processor",
        processor_version="999.9.9",
        expected_reference_count=-1,
        source_name="Test Source",
    )

    mock_batch_registrations = [
        ImportBatchRead(
            id=test_batch_ids[0],
            storage_url="http://test-storage-url-1",
            import_record_id=test_import_record_id,
            status=ImportBatchStatus.CREATED,
            collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
        ),
        ImportBatchRead(
            id=test_batch_ids[1],
            storage_url="http://test-storage-url-2",
            import_record_id=test_import_record_id,
            status=ImportBatchStatus.CREATED,
            collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
        ),
    ]

    mock_batch_summaries = [
        ImportBatchSummary(
            storage_url="http://test-storage-url-1",
            id=test_summary_ids[0],
            import_batch_id=test_batch_ids[0],
            import_batch_status=ImportBatchStatus.COMPLETED,
            collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
            results={
                ImportResultStatus.COMPLETED.value: 5,
                ImportResultStatus.FAILED.value: 0,
            },
            failure_details=None,
        ),
        ImportBatchSummary(
            storage_url="http://test-storage-url-2",
            id=test_summary_ids[1],
            import_batch_id=test_batch_ids[1],
            import_batch_status=ImportBatchStatus.COMPLETED,
            collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
            results={
                ImportResultStatus.COMPLETED.value: 7,
                ImportResultStatus.FAILED.value: 0,
            },
            failure_details=None,
        ),
    ]

    mock_register_new_import = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_new_import",
        return_value=mock_import_record,
    )
    mock_register_import_batch = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_import_batch_for_single_blob",
        side_effect=mock_batch_registrations,
    )
    mock_finalise_import = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.finalise_import_record",
        return_value=mocker.Mock(status_code=http_no_content_status),
    )
    mock_check_completed = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.check_if_import_batch_completed",
        side_effect=[True, True],
    )
    mock_get_summary = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.get_import_batch_summary",
        side_effect=mock_batch_summaries,
    )

    mocker.patch("refresh_requester.repository.time.sleep", return_value=None)

    upload_blob_storage_contents_to_repository(test_settings, max_retries=2)
    (
        mock_blob_storage_client.assert_called_once_with(None),
        "get_all_blob_url_pairs should be called with None to get all blobs in a container",
    )
    (
        mock_register_new_import.assert_called_once(),
        "register_new_import should be called once",
    )
    assert mock_register_import_batch.call_count == len(
        mock_blob_url_pairs
    ), "register_import_batch_for_single_blob should be called for each blob"
    (
        mock_register_import_batch.assert_any_call(
            "test-blob-1",
            "http://test-sas-url-1",
            mock_import_record,
        ),
        "First blob should be registered for import batch",
    )
    (
        mock_register_import_batch.assert_any_call(
            "test-blob-2",
            "http://test-sas-url-2",
            mock_import_record,
        ),
        "Second blob should be registered for import batch",
    )
    (
        mock_finalise_import.assert_called_once_with(test_import_record_id),
        "Finalise import record should be called once",
    )
    assert mock_check_completed.call_count == len(
        mock_blob_url_pairs
    ), "check_if_import_batch_completed should be called for each batch"
    (
        mock_check_completed.assert_any_call(test_batch_ids[0]),
        "Check that the import ID was called for the first batch",
    )
    (
        mock_check_completed.assert_any_call(test_batch_ids[1]),
        "Check that the import ID was called for the second batch",
    )
    assert mock_get_summary.call_count == len(
        mock_blob_url_pairs
    ), "get_import_batch_summary should be called for each batch"
    (
        mock_get_summary.assert_any_call(test_batch_ids[0]),
        "Check that the import ID was called for the first batch",
    )
    (
        mock_get_summary.assert_any_call(test_batch_ids[1]),
        "Check that the import ID was called for the second batch",
    )


def test_upload_blob_storage_contents_to_repository_handles_incomplete_batches(
    mocker, test_settings
):
    """
    Test that the function retries when import batch is not completed immediately.

    Simulates a failure, followed by a successful completion on retry.
    """
    mocker.patch("refresh_requester.repository.get_token", return_value="test-token")
    mock_blob_url_pairs = [{"blob_name": "test-blob", "sas_url": "http://test-sas-url"}]
    mock_blob_storage_client = mocker.patch(
        "refresh_requester.repository.DestinyBlobStorageClient.get_all_blob_url_pairs",
        return_value=mock_blob_url_pairs,
    )
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    test_summary_id = uuid4()
    http_no_content_status = 204

    expected_completion_statuses = [False, True]
    mock_import_record = ImportRecordRead(
        id=test_import_record_id,
        status=ImportRecordStatus.CREATED,
        processor_name="Test Processor",
        processor_version="999.9.9",
        expected_reference_count=-1,
        source_name="Test Source",
    )

    mock_batch_registration = ImportBatchRead(
        id=test_batch_id,
        storage_url="http://test-storage-url",
        import_record_id=test_import_record_id,
        status=ImportBatchStatus.CREATED,
        collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
    )

    mock_batch_summary = ImportBatchSummary(
        storage_url="http://test-storage-url",
        id=test_summary_id,
        import_batch_id=test_batch_id,
        import_batch_status=ImportBatchStatus.COMPLETED,
        collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
        results={
            ImportResultStatus.COMPLETED.value: 10,
            ImportResultStatus.FAILED.value: 0,
        },
        failure_details=None,
    )

    mock_register_new_import = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_new_import",
        return_value=mock_import_record,
    )
    mock_register_import_batch = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_import_batch_for_single_blob",
        return_value=mock_batch_registration,
    )
    mock_finalise_import = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.finalise_import_record",
        return_value=mocker.Mock(status_code=http_no_content_status),
    )
    # Simulate incomplete batch on first check, then completed on retry
    mock_check_completed = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.check_if_import_batch_completed",
        side_effect=[False, True],
    )
    mock_get_summary = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.get_import_batch_summary",
        return_value=mock_batch_summary,
    )
    mock_sleep = mocker.patch(
        "refresh_requester.repository.time.sleep", return_value=None
    )

    upload_blob_storage_contents_to_repository(
        test_settings, max_retries=2, blob_to_upload="test-blob"
    )
    (
        mock_blob_storage_client.assert_called_once_with("test-blob"),
        "get_all_blob_url_pairs should be called with 'test-blob' to get the specific blob",
    )
    (
        mock_register_new_import.assert_called_once(),
        "register_new_import should be called once",
    )
    (
        mock_register_import_batch.assert_called_once_with(
            "test-blob",
            "http://test-sas-url",
            mock_import_record,
        ),
        "register_import_batch_for_single_blob should be called once with the blob name, SAS URL and import record",
    )
    (
        mock_finalise_import.assert_called_once_with(test_import_record_id),
        "Finalise import record should be called once",
    )
    assert (
        mock_check_completed.call_count == len(expected_completion_statuses)
    ), "check_if_import_batch_completed should be called twice if it fails the first time"
    (
        mock_sleep.assert_called_once(),
        "sleep should be called once to wait before retrying",
    )
    (
        mock_get_summary.assert_called_once_with(test_batch_id),
        "get_import_batch_summary should be called after the batch is completed",
    )
