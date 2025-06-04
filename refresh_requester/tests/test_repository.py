from refresh_requester.repository import DestinyRepositoryContentUploader


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

    response = uploader.finalise_import_record({"id": "test-import-id"})
    assert response == {"id": "test-import-id", "status": "finalised"}


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
