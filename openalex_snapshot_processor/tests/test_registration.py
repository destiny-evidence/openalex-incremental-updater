import json
from uuid import uuid4

import pytest
from destiny_sdk.imports import ImportBatchRead, ImportRecordRead, ImportRecordStatus
from requests import HTTPError, Response

from openalex_snapshot_processor.registration import (
    ProgressLoadError,
    RegistrationProgress,
    RegistrationReport,
    RegistrationSummary,
    RepositoryRegistrationError,
    _load_progress,
    _register_single_file,
    _save_progress,
    register_all_blobs_in_serial,
)
from refresh_requester.blob_storage import DestinyBlobStorageClient
from refresh_requester.repository import (
    DestinyRepositoryContentUploader,
    DestinyRepositoryImportError,
)


def test_load_progress_success(tmp_path):
    progress_data = {"completed": ["blob1", "blob2"]}
    progress_file = tmp_path / "progress.json"
    progress_file.write_text(json.dumps(progress_data))

    loaded_progress = _load_progress(progress_file)
    assert isinstance(
        loaded_progress, RegistrationProgress
    ), "Loaded progress should be an instance of RegistrationProgress."
    assert loaded_progress.completed == progress_data.get(
        "completed"
    ), "Completed blobs should match the data in the file."


def test_load_progress_failure_file_not_found(tmp_path):
    # Test loading progress from a non-existent file
    non_existent_file = tmp_path / "non_existent.json"
    loaded_progress = _load_progress(non_existent_file)
    assert isinstance(
        loaded_progress, RegistrationProgress
    ), "Loaded progress should be an instance of RegistrationProgress even if file does not exist."
    assert (
        loaded_progress.completed == []
    ), "Completed blobs should be empty when file does not exist."


def test_load_progress_failure_invalid_json(tmp_path):
    # Test loading progress from a file with invalid JSON
    invalid_json_file = tmp_path / "invalid.json"
    invalid_json_file.write_text("This is not valid JSON")

    with pytest.raises(ProgressLoadError):
        _load_progress(invalid_json_file)


def test_save_progress_success(tmp_path):
    progress_data = {"completed": ["blob1", "blob2"]}
    progress_file = tmp_path / "progress.json"
    progress = RegistrationProgress(**progress_data)
    _save_progress(progress_file, progress)
    loaded_progress = _load_progress(progress_file)
    assert isinstance(
        loaded_progress, RegistrationProgress
    ), "Loaded progress should be an instance of RegistrationProgress."
    assert loaded_progress.completed == progress_data.get(
        "completed"
    ), "Completed blobs should match the data in the file."


def test_register_single_file_success(
    mocker,
    test_settings,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    poll_interval = 1
    max_poll_attempts = 3
    test_blob_storage_client = test_destiny_blob_storage_client
    test_upload_result = {
        "import_record": ImportRecordRead(
            id=test_import_record_id,
            processor_name="test_processor",
            processor_version="9.9.9",
            expected_reference_count=-1,
            source_name="test_source",
            status=ImportRecordStatus.COMPLETED,
        ),
        "import_batch_ids": [test_batch_id],
    }

    mocker.patch.object(
        DestinyBlobStorageClient,
        "get_all_blob_url_pairs",
        return_value=[{"blob_name": "test_blob", "sas_url": "https://fake-sas-url"}],
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "refresh_token",
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "register_new_import",
        return_value=test_upload_result["import_record"],
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "register_import_batch_for_single_blob",
        return_value=ImportBatchRead(
            id=test_batch_id,
            import_record=test_upload_result["import_record"],
            import_record_id=test_import_record_id,
            import_results=None,
            status=ImportRecordStatus.COMPLETED,
            storage_url="https://fake-storage-url",
        ),
    )
    mocker.patch("requests.Session.patch", return_value=mocker.MagicMock(spec=Response))
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "poll_import_batches_for_completion",
        return_value=None,
    )
    result = _register_single_file(
        test_destiny_repository_content_uploader,
        test_blob_storage_client,
        "test_base_blob_name",
        poll_interval,
        max_poll_attempts,
    )
    assert isinstance(
        result, RegistrationReport
    ), "Result should be an instance of RegistrationReport."
    assert (
        result.import_record_id == test_import_record_id
    ), "Import record ID should match the mocked value."
    assert result.import_batch_ids == [
        test_batch_id
    ], "Import batch IDs should match the mocked value."


def test_register_single_file_failure_token_refresh(
    mocker,
    test_settings,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    poll_interval = 1
    max_poll_attempts = 3
    test_blob_storage_client = test_destiny_blob_storage_client

    expected_error_message = "Mocked token refresh error"

    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "refresh_token",
        side_effect=DestinyRepositoryImportError(expected_error_message),
    )

    with pytest.raises(DestinyRepositoryImportError) as error_info:
        _register_single_file(
            test_destiny_repository_content_uploader,
            test_blob_storage_client,
            "test_base_blob_name",
            poll_interval,
            max_poll_attempts,
        )
    assert expected_error_message in str(error_info.value)


def test_register_single_file_failure_register_new_import(
    mocker,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    poll_interval = 1
    max_poll_attempts = 3
    test_blob_storage_client = test_destiny_blob_storage_client

    expected_error_message = "Mocked token refresh error"

    mocker.patch.object(
        DestinyBlobStorageClient,
        "get_all_blob_url_pairs",
        return_value=[{"blob_name": "test_blob", "sas_url": "https://fake-sas-url"}],
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "refresh_token",
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "register_new_import",
        side_effect=DestinyRepositoryImportError(expected_error_message),
    )

    with pytest.raises(RepositoryRegistrationError) as error_info:
        _register_single_file(
            test_destiny_repository_content_uploader,
            test_blob_storage_client,
            "test_base_blob_name",
            poll_interval,
            max_poll_attempts,
        )
    assert expected_error_message in str(error_info.value)


def test_register_single_file_failure_batch_import(
    mocker,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    poll_interval = 1
    max_poll_attempts = 3
    test_blob_storage_client = test_destiny_blob_storage_client
    test_upload_result = {
        "import_record": ImportRecordRead(
            id=test_import_record_id,
            processor_name="test_processor",
            processor_version="9.9.9",
            expected_reference_count=-1,
            source_name="test_source",
            status=ImportRecordStatus.COMPLETED,
        ),
        "import_batch_ids": [test_batch_id],
    }
    expected_error_message = "Mocked batch registration error"

    mocker.patch.object(
        DestinyBlobStorageClient,
        "get_all_blob_url_pairs",
        return_value=[{"blob_name": "test_blob", "sas_url": "https://fake-sas-url"}],
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "refresh_token",
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "register_new_import",
        return_value=test_upload_result["import_record"],
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "register_import_batch_for_single_blob",
        side_effect=HTTPError(expected_error_message),
    )

    with pytest.raises(RepositoryRegistrationError) as error_info:
        _register_single_file(
            test_destiny_repository_content_uploader,
            test_blob_storage_client,
            "test_base_blob_name",
            poll_interval,
            max_poll_attempts,
        )
    assert expected_error_message in str(error_info.value)


def test_register_single_file_failure_finalise_import_record(
    mocker,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    poll_interval = 1
    max_poll_attempts = 3
    test_blob_storage_client = test_destiny_blob_storage_client
    test_upload_result = {
        "import_record": ImportRecordRead(
            id=test_import_record_id,
            processor_name="test_processor",
            processor_version="9.9.9",
            expected_reference_count=-1,
            source_name="test_source",
            status=ImportRecordStatus.COMPLETED,
        ),
        "import_batch_ids": [test_batch_id],
    }

    expected_error_message = "Mocked finalise import record error"
    mocker.patch.object(
        DestinyBlobStorageClient,
        "get_all_blob_url_pairs",
        return_value=[{"blob_name": "test_blob", "sas_url": "https://fake-sas-url"}],
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "refresh_token",
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "register_new_import",
        return_value=test_upload_result["import_record"],
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "register_import_batch_for_single_blob",
        return_value=ImportBatchRead(
            id=test_batch_id,
            import_record=test_upload_result["import_record"],
            import_record_id=test_import_record_id,
            import_results=None,
            status=ImportRecordStatus.COMPLETED,
            storage_url="https://fake-storage-url",
        ),
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "finalise_import_record",
        side_effect=HTTPError(expected_error_message),
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "poll_import_batches_for_completion",
        return_value=None,
    )
    with pytest.raises(RepositoryRegistrationError) as error_info:
        _register_single_file(
            test_destiny_repository_content_uploader,
            test_blob_storage_client,
            "test_base_blob_name",
            poll_interval,
            max_poll_attempts,
        )
    assert expected_error_message in str(error_info.value)


def test_register_single_file_failure_finalise_poll_batches_for_completion(
    mocker,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    poll_interval = 1
    max_poll_attempts = 3
    test_blob_storage_client = test_destiny_blob_storage_client
    test_upload_result = {
        "import_record": ImportRecordRead(
            id=test_import_record_id,
            processor_name="test_processor",
            processor_version="9.9.9",
            expected_reference_count=-1,
            source_name="test_source",
            status=ImportRecordStatus.COMPLETED,
        ),
        "import_batch_ids": [test_batch_id],
    }

    expected_error_message = "Mocked polling error"
    mocker.patch.object(
        DestinyBlobStorageClient,
        "get_all_blob_url_pairs",
        return_value=[{"blob_name": "test_blob", "sas_url": "https://fake-sas-url"}],
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "refresh_token",
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "register_new_import",
        return_value=test_upload_result["import_record"],
    )
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "register_import_batch_for_single_blob",
        return_value=ImportBatchRead(
            id=test_batch_id,
            import_record=test_upload_result["import_record"],
            import_record_id=test_import_record_id,
            import_results=None,
            status=ImportRecordStatus.COMPLETED,
            storage_url="https://fake-storage-url",
        ),
    )
    mocker.patch("requests.Session.patch", return_value=mocker.MagicMock(spec=Response))
    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "poll_import_batches_for_completion",
        side_effect=HTTPError(expected_error_message),
    )
    with pytest.raises(RepositoryRegistrationError) as error_info:
        _register_single_file(
            test_destiny_repository_content_uploader,
            test_blob_storage_client,
            "test_base_blob_name",
            poll_interval,
            max_poll_attempts,
        )
    assert expected_error_message in str(error_info.value)


def test_register_all_blobs_in_serial_success(
    tmp_path,
    mocker,
    test_settings,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_processed_files = [
        {"base_blob_name": "test_base_blob_name_part0001"},
        {"base_blob_name": "test_base_blob_name_part0002"},
        {"base_blob_name": "test_base_blob_name_part0003"},
    ]
    test_import_record_ids = [uuid4() for _ in test_processed_files]
    # assumes two batches per file for testing purposes
    test_batch_ids = [[uuid4(), uuid4()] for _ in test_processed_files]

    # simulate one completed file, don't expect to see this get registered again

    test_already_completed_files = [
        f["base_blob_name"] for f in test_processed_files[:1]
    ]
    test_files_to_register = [f["base_blob_name"] for f in test_processed_files[1:]]
    test_batch_ids_to_register = test_batch_ids[1:]

    test_progress_data = {"completed": test_already_completed_files}
    progress_file_path = tmp_path / "progress.json"
    progress = RegistrationProgress(**test_progress_data)
    _save_progress(progress_file_path, progress)

    expected_single_file_registration_result = [
        RegistrationReport(
            import_record_id=test_import_record_ids[i],
            import_batch_ids=test_batch_ids_to_register[i],
            batch_count=len(test_batch_ids_to_register[i]),
        )
        for i in range(len(test_files_to_register))
    ]

    mocker.patch(
        "openalex_snapshot_processor.registration.get_settings",
        return_value=test_settings,
    )
    mocked_single_file_registration_call = mocker.patch(
        "openalex_snapshot_processor.registration._register_single_file",
        side_effect=expected_single_file_registration_result,
    )
    mocker.patch(
        "openalex_snapshot_processor.registration.DestinyBlobStorageClient",
        return_value=test_destiny_blob_storage_client,
    )

    result = register_all_blobs_in_serial(
        processed_files=test_processed_files,
        progress_file=progress_file_path,
    )
    assert (
        mocked_single_file_registration_call.call_count == len(test_files_to_register)
    ), "Single file registration should be called for each file that needs to be registered."
    assert isinstance(
        result, RegistrationSummary
    ), "Result should be an instance of RegistrationSummary."
    assert (
        result.total_files == len(test_processed_files)
    ), "Total files should match the total number of files _ever_ processed. This includes already processed files and files processed in this run."
    assert (
        result.completed_count
        == len(test_already_completed_files) + len(test_files_to_register)
    ), "Completed count should match the number of already completed files plus the number of files registered."
    assert result.skipped_count == len(
        test_already_completed_files
    ), "Skipped count should be equal to the number of already completed files."
    assert result.total_batches_registered == sum(
        len(b) for b in test_batch_ids_to_register
    ), "Total batches registered should match the sum of batches for non-skipped files."
    assert len(result.results) == len(
        test_files_to_register
    ), "Number of results should match non-skipped files."
    assert all(
        isinstance(r, RegistrationReport) for r in result.results
    ), "All results should be RegistrationReport instances."
