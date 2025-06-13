from refresh_requester.repository import (
    DestinyRepositoryContentUploader,
    upload_blob_storage_contents_to_repository,
)


def test_register_new_import_success(mocker, test_settings) -> None:
    """Test the register_new_import method."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)

    mocker.patch.object(
        uploader.session,
        "post",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: {"id": "test-import-id", "status": "created"},
        ),
    )

    response = uploader.register_new_import()
    assert response == {"id": "test-import-id", "status": "created"}


def test_register_import_batch_for_single_blob(mocker, test_settings) -> None:
    """Test the register_import_batch_for_single_blob method."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)

    expected_status = "created"
    mocker.patch.object(
        uploader.session,
        "post",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: {"id": "test-batch-id", "status": expected_status},
        ),
    )

    response = uploader.register_import_batch_for_single_blob(
        blob_name="test-blob",
        sas_url="http://test-sas-url",
        import_record={"id": "test-import-id"},
    )
    assert response == {"id": "test-batch-id", "status": expected_status}


def test_finalise_import_record(mocker, test_settings) -> None:
    """Test the finalise_import_record method."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)

    mocker.patch.object(
        uploader.session,
        "patch",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: {"id": "test-import-id", "status": "finalised"},
        ),
    )
    http_ok_status = 200
    response = uploader.finalise_import_record({"id": "test-import-id"})
    assert response.status_code == http_ok_status


def test_check_if_import_batch_completed_true(mocker, test_settings) -> None:
    """Test the check_if_import_batch_completed method when the batch is completed."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)

    mocker.patch.object(
        uploader.session,
        "get",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: {"status": "completed"},
        ),
    )

    result = uploader.check_if_import_batch_completed("test-batch-id")
    assert result is True


def test_check_if_import_batch_completed_false(mocker, test_settings) -> None:
    """Test the check_if_import_batch_completed method when the batch is not completed."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)

    mocker.patch.object(
        uploader.session,
        "get",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: {"status": "in_progress"},
        ),
    )

    result = uploader.check_if_import_batch_completed("test-batch-id")
    assert result is False


def test_get_import_batch_summary(mocker, test_settings) -> None:
    """Test the get_import_batch_summary method."""
    mocker.patch(
        "refresh_requester.repository.get_token",
        return_value="test-token",
    )
    uploader = DestinyRepositoryContentUploader(test_settings)

    mocker.patch.object(
        uploader.session,
        "get",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: {"summary": "test-summary"},
        ),
    )

    response = uploader.get_import_batch_summary("test-batch-id")
    assert response == {"summary": "test-summary"}


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

    mock_register_new_import = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_new_import",
        return_value={"id": "test-import-id", "status": "created"},
    )
    mock_register_import_batch = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_import_batch_for_single_blob",
        return_value={"id": "test-batch-id", "status": "created"},
    )
    mock_finalise_import = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.finalise_import_record",
        return_value=mocker.Mock(status_code=200),
    )
    mock_check_completed = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.check_if_import_batch_completed",
        return_value=True,
    )
    mock_get_summary = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.get_import_batch_summary",
        return_value={"summary": "test-summary"},
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
            {"id": "test-import-id", "status": "created"},
        ),
        "register_import_batch_for_single_blob should be called once with the blob name and SAS URL",
    )
    (
        mock_finalise_import.assert_called_once_with(
            {"id": "test-import-id", "status": "created"}
        ),
        "Finalise import record should be called once",
    )
    (
        mock_check_completed.assert_called_once_with("test-batch-id"),
        "check_if_import_batch_completed should be called with the batch ID",
    )
    (
        mock_get_summary.assert_called_once_with("test-batch-id"),
        "get_import_batch_summary should be called with the batch ID",
    )


def test_upload_blob_storage_contents_to_repository_success_multiple_blobs(
    mocker, test_settings
):
    """Test upload_blob_storage_contents_to_repository end-to-end logic for multiple blobs."""
    mocker.patch("refresh_requester.repository.get_token", return_value="test-token")
    mock_blob_url_pairs = [
        {"blob_name": "test-blob-1", "sas_url": "http://test-sas-url-1"},
        {"blob_name": "test-blob-2", "sas_url": "http://test-sas-url-2"},
    ]
    mock_blob_storage_client = mocker.patch(
        "refresh_requester.repository.DestinyBlobStorageClient.get_all_blob_url_pairs",
        return_value=mock_blob_url_pairs,
    )

    mock_register_new_import = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_new_import",
        return_value={"id": "test-import-id", "status": "created"},
    )
    mock_register_import_batch = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_import_batch_for_single_blob",
        side_effect=[
            {"id": "test-batch-id-1", "status": "created"},
            {"id": "test-batch-id-2", "status": "created"},
        ],
    )
    mock_finalise_import = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.finalise_import_record",
        return_value=mocker.Mock(status_code=200),
    )
    mock_check_completed = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.check_if_import_batch_completed",
        return_value=True,
    )
    mock_get_summary = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.get_import_batch_summary",
        side_effect=[
            {"summary": "test-summary-1"},
            {"summary": "test-summary-2"},
        ],
    )

    mocker.patch("refresh_requester.repository.time.sleep", return_value=None)

    upload_blob_storage_contents_to_repository(test_settings, max_retries=2)
    (
        mock_blob_storage_client.assert_called_once_with(None),
        "get_all_blob_url_pairs should be called with None to get all blobs in a container",
    )
    (
        mock_register_new_import.assert_called_once(),
        "register_new_import should be called once regardless of the number of blobs",
    )
    assert mock_register_import_batch.call_count == len(
        mock_blob_url_pairs
    ), "register_import_batch_for_single_blob should be called for each blob"
    (
        mock_register_import_batch.assert_any_call(
            "test-blob-1",
            "http://test-sas-url-1",
            {"id": "test-import-id", "status": "created"},
        ),
        "First blob should be registered for import batch",
    )
    (
        mock_register_import_batch.assert_any_call(
            "test-blob-2",
            "http://test-sas-url-2",
            {"id": "test-import-id", "status": "created"},
        ),
        "Second blob should be registered for import batch",
    )
    (
        mock_finalise_import.assert_called_once_with(
            {"id": "test-import-id", "status": "created"}
        ),
        "Finalise import record should be called once regardless of the number of blobs",
    )

    assert mock_check_completed.call_count == len(
        mock_blob_url_pairs
    ), "check_if_import_batch_completed should be called for each batch"
    (
        mock_check_completed.assert_any_call("test-batch-id-1"),
        "Check that the import ID was called for the first batch",
    )
    (
        mock_check_completed.assert_any_call("test-batch-id-2"),
        "Check that the import ID was called for the second batch",
    )
    assert mock_get_summary.call_count == len(
        mock_blob_url_pairs
    ), "get_import_batch_summary should be called for each batch"
    (
        mock_get_summary.assert_any_call("test-batch-id-1"),
        "Check that the import ID was called for the first batch",
    )
    (
        mock_get_summary.assert_any_call("test-batch-id-2"),
        "Check that the import ID was called for the second batch",
    )


def test_upload_blob_storage_contents_to_repository_handles_incomplete_batches(
    mocker, test_settings
):
    """
    Test that the function retries when import batch is not completed immediately.

    Simulates a failure, followed by a successful completion on retry.
    """
    desired_outcome_pattern_for_batch_completed_check = [False, True]
    mocker.patch("refresh_requester.repository.get_token", return_value="test-token")
    mock_blob_url_pairs = [{"blob_name": "test-blob", "sas_url": "http://test-sas-url"}]
    mocker.patch(
        "refresh_requester.repository.DestinyBlobStorageClient.get_all_blob_url_pairs",
        return_value=mock_blob_url_pairs,
    )
    mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_new_import",
        return_value={"id": "test-import-id", "status": "created"},
    )
    mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.register_import_batch_for_single_blob",
        return_value={"id": "test-batch-id", "status": "created"},
    )
    mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.finalise_import_record",
        return_value=mocker.Mock(status_code=200),
    )

    mock_check_completed = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.check_if_import_batch_completed",
        side_effect=desired_outcome_pattern_for_batch_completed_check,
    )
    mock_get_summary = mocker.patch(
        "refresh_requester.repository.DestinyRepositoryContentUploader.get_import_batch_summary",
        return_value={"summary": "test-summary"},
    )
    mock_sleep = mocker.patch(
        "refresh_requester.repository.time.sleep", return_value=None
    )

    upload_blob_storage_contents_to_repository(
        test_settings, max_retries=2, blob_to_upload="test-blob"
    )
    assert (
        mock_check_completed.call_count
        == len(desired_outcome_pattern_for_batch_completed_check)
    ), "check_if_import_batch_completed should be called twice if it fails the first time"
    (
        mock_sleep.assert_called_once(),
        "sleep should be called once to wait before retrying",
    )
    (
        mock_get_summary.assert_called_once_with("test-batch-id"),
        "get_import_batch_summary should be called after the batch is completed",
    )
