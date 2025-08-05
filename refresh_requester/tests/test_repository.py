from datetime import UTC, datetime
from http import HTTPStatus
from uuid import uuid4

import freezegun
import pytest
from destiny_sdk.imports import (
    CollisionStrategy,
    ImportBatchRead,
    ImportBatchStatus,
    ImportBatchSummary,
    ImportRecordIn,
    ImportRecordRead,
    ImportRecordStatus,
    ImportResultStatus,
)

from refresh_requester.repository import (
    DestinyRepositoryContentUploader,
    ImportSourceType,
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
            status_code=HTTPStatus.OK,
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
            status_code=HTTPStatus.OK,
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

    mocker.patch.object(
        uploader.session,
        "patch",
        return_value=mocker.Mock(
            status_code=HTTPStatus.NO_CONTENT,
        ),
    )
    response = uploader.finalise_import_record(test_id)
    assert (
        response.status_code == HTTPStatus.NO_CONTENT
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
    test_batch_id = uuid4()
    test_record_id = uuid4()
    mocked_response = ImportBatchRead(
        id=test_batch_id,
        storage_url="http://test-storage-url",
        import_record_id=test_record_id,
        status=test_status,
        collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
    )
    mocker.patch.object(
        uploader.session,
        "get",
        return_value=mocker.Mock(
            status_code=HTTPStatus.OK,
            json=lambda: mocked_response.model_dump(),
        ),
    )

    result = uploader.check_if_import_batch_completed(test_record_id, test_batch_id)
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
    test_import_record_id = uuid4()
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

    mocker.patch.object(
        uploader.session,
        "get",
        return_value=mocker.Mock(
            status_code=HTTPStatus.OK, json=lambda: mock_summary_response.model_dump()
        ),
    )
    response = uploader.get_import_batch_summary(
        test_import_record_id, test_import_batch_id
    )
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
        return_value=mocker.Mock(status_code=HTTPStatus.NO_CONTENT),
    )

    upload_blob_storage_contents_to_repository(
        test_settings, blob_to_upload="test-blob"
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
        return_value=mocker.Mock(status_code=HTTPStatus.NO_CONTENT),
    )

    upload_blob_storage_contents_to_repository(test_settings)
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


def test_poll_import_batches_for_completion_retries_if_batch_incomplete(
    mocker, test_settings
):
    """
    Test that the function retries when import batch is not completed immediately.

    Simulates a failure, followed by a successful completion on retry.
    """
    mocker.patch("refresh_requester.repository.get_token", return_value="test-token")
    uploader = DestinyRepositoryContentUploader(test_settings)
    test_import_batch_id = uuid4()
    test_number_of_retries = 2

    import_record_id = uuid4()
    import_batch_id_one = uuid4()
    import_batch_id_two = uuid4()
    summary_id_one = uuid4()
    summary_id_two = uuid4()
    started_status = ImportBatchRead(
        id=test_import_batch_id,
        storage_url="http://test-storage-url",
        import_record_id=import_record_id,
        status=ImportBatchStatus.STARTED,
        collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
    )
    completed_status = ImportBatchRead(
        id=test_import_batch_id,
        storage_url="http://test-storage-url",
        import_record_id=import_record_id,
        status=ImportBatchStatus.COMPLETED,
        collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
    )
    mocker.patch.object(
        uploader.session,
        "get",
        side_effect=[
            mocker.Mock(
                status_code=HTTPStatus.OK,
                json=lambda: started_status.model_dump(),
            ),
            mocker.Mock(
                status_code=HTTPStatus.OK,
                json=lambda: completed_status.model_dump(),
            ),
        ],
    )

    mock_batch_summaries = [
        ImportBatchSummary(
            storage_url="http://test-storage-url-1",
            id=summary_id_one,
            import_batch_id=import_batch_id_one,
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
            id=summary_id_two,
            import_batch_id=import_batch_id_two,
            import_batch_status=ImportBatchStatus.COMPLETED,
            collision_strategy=CollisionStrategy.MERGE_AGGRESSIVE,
            results={
                ImportResultStatus.COMPLETED.value: 7,
                ImportResultStatus.FAILED.value: 0,
            },
            failure_details=None,
        ),
    ]
    mock_get_summary = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.get_import_batch_summary",
        side_effect=mock_batch_summaries,
    )

    mocker.patch("refresh_requester.repository.time.sleep", return_value=None)

    uploader.poll_import_batches_for_completion(
        import_record_id, [test_import_batch_id], max_retries=test_number_of_retries
    )

    assert (
        uploader.session.get.call_count == test_number_of_retries
    ), "Should have made two GET requests to check batch status"
    mock_get_summary.assert_called_once_with(import_record_id, test_import_batch_id)


def test_construct_payload(mocker, test_settings) -> None:
    """Test the register_new_import method with source type."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)
    test_processor_name = "Test Processor"
    test_processor_version = "999.9.9"
    test_expected_reference_count = -1
    test_source_name = "Test Source"
    result = uploader.construct_payload(
        test_processor_name,
        test_processor_version,
        test_expected_reference_count,
        test_source_name,
    )

    assert isinstance(
        result, ImportRecordIn
    ), "Result should be an instance of ImportSourceType"


@pytest.mark.parametrize(
    (
        "source_type",
        "processor_name",
        "processor_version",
        "expected_reference_count",
        "source_name",
    ),
    [
        (
            ImportSourceType.OPEN_ALEX,
            "Bulk OpenAlex Importer",
            "initial_openalex_import",
            -1,
            "openalex",
        ),
        (
            ImportSourceType.SOLR,
            "Bulk Solr Importer",
            "initial_solr_import",
            -1,
            "pik-solr",
        ),
    ],
)
def test_retrieve_payload_from_source_type(
    mocker,
    test_settings,
    source_type,
    processor_name,
    processor_version,
    expected_reference_count,
    source_name,
) -> None:
    """Test the retrieve_payload_from_source_type method."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)
    result = uploader.retrieve_payload_from_source_type(source_type)

    assert isinstance(
        result, ImportRecordIn
    ), "Result should be an instance of ImportRecordIn"
    assert (
        result.processor_name == processor_name
    ), f"Processor name should be {processor_name}"
    assert (
        result.processor_version == processor_version
    ), f"Processor version should be {processor_version}"
    assert (
        result.expected_reference_count == expected_reference_count
    ), f"Expected reference count should be {expected_reference_count}"
    assert result.source_name == source_name, f"Source name should be {source_name}"
