import json
import logging
from uuid import uuid4

import pytest
from destiny_sdk.imports import (
    ImportBatchRead,
    ImportBatchStatus,
    ImportBatchSummary,
    ImportRecordRead,
    ImportRecordStatus,
    ImportResultStatus,
)
from requests import HTTPError, Response

from openalex_snapshot_processor.registration import (
    InProgressRecord,
    ProgressLoadError,
    RegistrationProgress,
    RegistrationReport,
    RegistrationSummary,
    RepositoryRegistrationError,
    _has_exit_status,
    _load_progress,
    _reconcile_in_progress,
    _register_single_file,
    _save_progress,
    poll_registration_status,
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
    tmp_path,
    mocker,
    test_settings,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    poll_interval = 1
    test_blob_storage_client = test_destiny_blob_storage_client
    test_progress_file = tmp_path / "progress.json"
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
    test_progress = RegistrationProgress()

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
    mocker.patch(
        "openalex_snapshot_processor.registration.poll_registration_status",
        return_value=None,
    )
    result = _register_single_file(
        test_destiny_repository_content_uploader,
        test_blob_storage_client,
        "test_base_blob_name",
        poll_interval,
        progress=test_progress,
        progress_file=test_progress_file,
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
    tmp_path,
    mocker,
    test_settings,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    poll_interval = 1
    test_progress = RegistrationProgress()
    test_progress_file = tmp_path / "progress.json"
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
            test_progress,
            test_progress_file,
        )
    assert expected_error_message in str(error_info.value)


def test_register_single_file_failure_register_new_import(
    tmp_path,
    mocker,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    poll_interval = 1
    test_progress = RegistrationProgress()
    test_progress_file = tmp_path / "progress.json"
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
            progress=test_progress,
            progress_file=test_progress_file,
        )
    assert expected_error_message in str(error_info.value)


def test_register_single_file_failure_batch_import(
    tmp_path,
    mocker,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    poll_interval = 1
    test_blob_storage_client = test_destiny_blob_storage_client
    test_progress = RegistrationProgress()
    test_progress_file = tmp_path / "progress.json"

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
            test_progress,
            test_progress_file,
        )
    assert expected_error_message in str(error_info.value)


def test_register_single_file_failure_finalise_import_record(
    tmp_path,
    mocker,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    poll_interval = 1
    test_blob_storage_client = test_destiny_blob_storage_client
    test_progress = RegistrationProgress()
    test_progress_file = tmp_path / "progress.json"
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
            progress=test_progress,
            progress_file=test_progress_file,
        )
    assert expected_error_message in str(error_info.value)


def test_register_single_file_failure_finalise_poll_batches_for_completion(
    tmp_path,
    mocker,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    poll_interval = 1
    test_blob_storage_client = test_destiny_blob_storage_client
    test_progress = RegistrationProgress()
    test_progress_file = tmp_path / "progress.json"

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
    expected_error_message = "Test polling error"
    mocker.patch(
        "openalex_snapshot_processor.registration.poll_registration_status",
        side_effect=RepositoryRegistrationError(expected_error_message),
    )
    with pytest.raises(RepositoryRegistrationError) as error_info:
        _register_single_file(
            test_destiny_repository_content_uploader,
            test_blob_storage_client,
            "test_base_blob_name",
            poll_interval,
            progress=test_progress,
            progress_file=test_progress_file,
        )
    assert expected_error_message in str(error_info.value)


def test_register_single_file_failure_finalise_poll_batches_transient_http_error(
    tmp_path,
    mocker,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    poll_interval = 1
    test_blob_storage_client = test_destiny_blob_storage_client
    test_progress = RegistrationProgress()
    test_progress_file = tmp_path / "progress.json"

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
    expected_error_message = "Test transient polling error"
    mocker.patch(
        "openalex_snapshot_processor.registration.poll_registration_status",
        side_effect=HTTPError(expected_error_message),
    )
    with pytest.raises(HTTPError) as error_info:
        _register_single_file(
            test_destiny_repository_content_uploader,
            test_blob_storage_client,
            "test_base_blob_name",
            poll_interval,
            progress=test_progress,
            progress_file=test_progress_file,
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
    assert (
        result.retried_count == 0
    ), "Retried count should be 0 when there are no retries."
    assert result.total_batches_registered == sum(
        len(b) for b in test_batch_ids_to_register
    ), "Total batches registered should match the sum of batches for non-skipped files."
    assert len(result.results) == len(
        test_files_to_register
    ), "Number of results should match non-skipped files."
    assert all(
        isinstance(r, RegistrationReport) for r in result.results
    ), "All results should be RegistrationReport instances."


def test_register_all_blobs_in_serial_previously_failed_succeeds_on_retry(
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

    # simulate one previously failed file that will now succeed upon retry

    test_previously_failed_files = [
        f["base_blob_name"] for f in test_processed_files[:1]
    ]
    test_files_to_register = [f["base_blob_name"] for f in test_processed_files]
    test_batch_ids_to_register = test_batch_ids

    test_progress_data = {"failed": test_previously_failed_files}
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
    ), "Single file registration should be called for each file that needs to be registered, including previously failed files."
    assert isinstance(
        result, RegistrationSummary
    ), "Result should be an instance of RegistrationSummary."
    assert result.total_files == len(
        test_processed_files
    ), "Total files should match the total number of files _ever_ processed."
    assert (
        result.completed_count == len(test_files_to_register)
    ), "Completed count should match the number of files registered in this run since all files were either previously failed or not marked at all."
    assert (
        result.skipped_count == 0
    ), "Skipped count should be 0 when there are no previously completed files."
    assert (
        result.retried_count == len(test_previously_failed_files)
    ), "Retried count should match the number of previously failed files that are now completed."
    assert (
        result.total_batches_registered
        == sum(len(b) for b in test_batch_ids_to_register)
    ), "Total batches registered should match the sum of batches for all files since there are no skipped files."
    assert len(result.results) == len(
        test_files_to_register
    ), "Number of results should match the number of files registered in this run."
    assert all(
        isinstance(r, RegistrationReport) for r in result.results
    ), "All results should be RegistrationReport instances."


def test_register_all_blobs_in_serial_fresh_file_not_counted_as_retry(
    tmp_path,
    mocker,
    test_settings,
    test_destiny_repository_content_uploader,
    test_destiny_blob_storage_client,
):
    test_failed_blob = "test_failed_blob"
    test_fresh_blob = "test_fresh_blob"

    progress = RegistrationProgress(failed=[test_failed_blob])
    progress_file_path = tmp_path / "progress.json"
    _save_progress(progress_file_path, progress)

    test_processed_files = [
        {"base_blob_name": test_failed_blob},
        {"base_blob_name": test_fresh_blob},
    ]

    mocker.patch(
        "openalex_snapshot_processor.registration.get_settings",
        return_value=test_settings,
    )
    mocker.patch(
        "openalex_snapshot_processor.registration.DestinyBlobStorageClient",
        return_value=test_destiny_blob_storage_client,
    )
    mocker.patch(
        "openalex_snapshot_processor.registration._register_single_file",
        side_effect=[
            RegistrationReport(
                import_record_id=uuid4(), import_batch_ids=[uuid4()], batch_count=1
            ),
            RegistrationReport(
                import_record_id=uuid4(), import_batch_ids=[uuid4()], batch_count=1
            ),
        ],
    )

    result = register_all_blobs_in_serial(
        processed_files=test_processed_files,
        progress_file=progress_file_path,
    )

    assert (
        result.retried_count == len([test_failed_blob])
    ), "Retried count should only include previously failed files that were completed, not fresh files that were never marked as failed."
    assert (
        result.completed_count == len(test_processed_files)
    ), "Completed count should include all files that were completed, including both previously failed and fresh files."

    saved_progress = _load_progress(progress_file_path)
    assert (
        test_failed_blob in saved_progress.retried_completed
    ), "Previously failed blob should be marked as retried and completed in progress."
    assert (
        test_fresh_blob not in saved_progress.retried_completed
    ), "Fresh blob should not be marked as retried since it was never failed."
    assert (
        test_fresh_blob in saved_progress.completed
    ), "Fresh blob should be marked as completed in progress."
    assert (
        test_failed_blob not in saved_progress.failed
    ), "Previously failed blob should no longer be marked as failed in progress."
    assert (
        len(saved_progress.failed) == 0
    ), "Failed list in progress should be empty after retrying and completing previously failed files."


def test_reconcile_in_progress_all_completed(
    tmp_path,
    mocker,
    test_destiny_repository_content_uploader,
):
    progress_file = tmp_path / "progress.json"
    base_blob_name = "test_blob"

    test_in_progress_completed_blob_names = [
        f"{base_blob_name}_part0001",
        f"{base_blob_name}_part0002",
        f"{base_blob_name}_part0003",
    ]
    test_in_progress_records = {
        name: InProgressRecord(
            import_record_id=uuid4(),
            import_batch_ids=[uuid4()],
        )
        for name in test_in_progress_completed_blob_names
    }

    progress_data = {
        "in_progress": test_in_progress_records,
        "failed": [],
        "completed": [],
        "retried_completed": [],
    }
    progress = RegistrationProgress(**progress_data)

    _save_progress(progress_file, progress)

    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "get_import_batch_summary",
        return_value=ImportBatchSummary(
            storage_url="https://fake-storage-url",
            id=uuid4(),
            import_batch_id=uuid4(),
            import_batch_status=ImportBatchStatus.COMPLETED,
            results={
                ImportResultStatus.COMPLETED: len(
                    test_in_progress_completed_blob_names
                ),
            },
            failure_details=None,
        ),
    )

    assert len(progress.in_progress) == len(
        test_in_progress_completed_blob_names
    ), "Setup should have all test blobs in in-progress state before reconciliation."
    assert (
        len(progress.completed) == 0
    ), "Setup should have no blobs in completed state before reconciliation."
    assert (
        len(progress.failed) == 0
    ), "Setup should have no blobs in failed state before reconciliation."
    assert (
        len(progress.retried_completed) == 0
    ), "Setup should have no blobs in retried_completed state before reconciliation."

    _reconcile_in_progress(
        progress, test_destiny_repository_content_uploader, progress_file
    )

    assert (
        len(progress.in_progress) == 0
    ), "All in-progress blobs should be reconciled and marked as completed."
    assert set(progress.completed) == set(
        test_in_progress_completed_blob_names
    ), "All previously in-progress blobs should now be marked as completed."
    assert (
        len(progress.failed) == 0
    ), "No blobs should be marked as failed during reconciliation when all are completed."
    assert (
        len(progress.retried_completed) == 0
    ), "No blobs should be marked as retried_completed during reconciliation when all are completed."


def test_reconcile_in_progress_one_completed_others_in_progress(
    tmp_path,
    mocker,
    test_destiny_repository_content_uploader,
):
    progress_file = tmp_path / "progress.json"
    base_blob_name = "test_blob"

    test_import_record_id = uuid4()
    test_in_progress_completed_blob_names = [
        f"{base_blob_name}_part0001",
        f"{base_blob_name}_part0002",
        f"{base_blob_name}_part0003",
    ]

    test_batch_ids = [uuid4() for _ in test_in_progress_completed_blob_names]

    test_in_progress_records = {
        name: InProgressRecord(
            import_record_id=test_import_record_id,
            import_batch_ids=[
                test_batch_ids[test_in_progress_completed_blob_names.index(name)]
            ],
        )
        for name in test_in_progress_completed_blob_names
    }
    expected_complete_records = {
        name: InProgressRecord(
            import_record_id=test_import_record_id,
            import_batch_ids=[
                test_batch_ids[test_in_progress_completed_blob_names.index(name)]
            ],
        )
        for name in test_in_progress_completed_blob_names[:1]
    }
    expected_in_progress_records = {
        name: InProgressRecord(
            import_record_id=test_import_record_id,
            import_batch_ids=[
                test_batch_ids[test_in_progress_completed_blob_names.index(name)]
            ],
        )
        for name in test_in_progress_completed_blob_names[1:]
    }
    progress_data = {
        "in_progress": test_in_progress_records,
        "failed": [],
        "completed": [],
        "retried_completed": [],
    }
    progress = RegistrationProgress(**progress_data)

    _save_progress(progress_file, progress)

    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "get_import_batch_summary",
        side_effect=[
            ImportBatchSummary(
                storage_url="https://fake-storage-url",
                id=uuid4(),
                import_batch_id=test_batch_ids[0],
                import_batch_status=ImportBatchStatus.COMPLETED,
                results={
                    ImportResultStatus.COMPLETED: 1,
                },
                failure_details=None,
            ),
            ImportBatchSummary(
                storage_url="https://fake-storage-url",
                id=uuid4(),
                import_batch_id=test_batch_ids[1],
                import_batch_status=ImportBatchStatus.STARTED,
                results={
                    ImportResultStatus.STARTED: 1,
                },
                failure_details=None,
            ),
            ImportBatchSummary(
                storage_url="https://fake-storage-url",
                id=uuid4(),
                import_batch_id=test_batch_ids[2],
                import_batch_status=ImportBatchStatus.STARTED,
                results={
                    ImportResultStatus.STARTED: 1,
                },
                failure_details=None,
            ),
        ],
    )

    assert len(progress.in_progress) == len(
        test_in_progress_completed_blob_names
    ), "Setup should have all test blobs in in-progress state before reconciliation."
    assert (
        len(progress.completed) == 0
    ), "Setup should have no blobs in completed state before reconciliation."
    assert (
        len(progress.failed) == 0
    ), "Setup should have no blobs in failed state before reconciliation."
    assert (
        len(progress.retried_completed) == 0
    ), "Setup should have no blobs in retried_completed state before reconciliation."

    _reconcile_in_progress(
        progress, test_destiny_repository_content_uploader, progress_file
    )

    assert len(progress.in_progress) == len(
        expected_in_progress_records
    ), "All in-progress blobs should be reconciled and marked as completed."
    assert set(progress.completed) == set(
        expected_complete_records.keys()
    ), "All previously in-progress blobs should now be marked as completed."
    assert (
        len(progress.failed) == 0
    ), "No blobs should be marked as failed during reconciliation when all are completed."
    assert (
        len(progress.retried_completed) == 0
    ), "No blobs should be marked as retried_completed during reconciliation when all are completed."


def test_reconcile_in_progress_one_failure_others_in_progress(
    tmp_path,
    mocker,
    test_destiny_repository_content_uploader,
):
    progress_file = tmp_path / "progress.json"
    base_blob_name = "test_blob"

    test_import_record_id = uuid4()
    test_in_progress_blob_names = [
        f"{base_blob_name}_part0001",
        f"{base_blob_name}_part0002",
        f"{base_blob_name}_part0003",
    ]

    test_batch_ids = [uuid4() for _ in test_in_progress_blob_names]

    test_in_progress_records = {
        name: InProgressRecord(
            import_record_id=test_import_record_id,
            import_batch_ids=[test_batch_ids[test_in_progress_blob_names.index(name)]],
        )
        for name in test_in_progress_blob_names
    }
    expected_failed_records = {
        name: InProgressRecord(
            import_record_id=test_import_record_id,
            import_batch_ids=[test_batch_ids[test_in_progress_blob_names.index(name)]],
        )
        for name in test_in_progress_blob_names[:1]
    }
    expected_in_progress_records = {
        name: InProgressRecord(
            import_record_id=test_import_record_id,
            import_batch_ids=[test_batch_ids[test_in_progress_blob_names.index(name)]],
        )
        for name in test_in_progress_blob_names[1:]
    }
    progress_data = {
        "in_progress": test_in_progress_records,
        "failed": [],
        "completed": [],
        "retried_completed": [],
    }
    progress = RegistrationProgress(**progress_data)

    _save_progress(progress_file, progress)

    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "get_import_batch_summary",
        side_effect=[
            ImportBatchSummary(
                storage_url="https://fake-storage-url",
                id=uuid4(),
                import_batch_id=test_batch_ids[0],
                import_batch_status=ImportBatchStatus.FAILED,
                results={
                    ImportResultStatus.FAILED: 1,
                },
                failure_details=None,
            ),
            ImportBatchSummary(
                storage_url="https://fake-storage-url",
                id=uuid4(),
                import_batch_id=test_batch_ids[1],
                import_batch_status=ImportBatchStatus.STARTED,
                results={
                    ImportResultStatus.STARTED: 1,
                },
                failure_details=None,
            ),
            ImportBatchSummary(
                storage_url="https://fake-storage-url",
                id=uuid4(),
                import_batch_id=test_batch_ids[2],
                import_batch_status=ImportBatchStatus.STARTED,
                results={
                    ImportResultStatus.STARTED: 1,
                },
                failure_details=None,
            ),
        ],
    )

    assert len(progress.in_progress) == len(
        test_in_progress_blob_names
    ), "Setup should have all test blobs in in-progress state before reconciliation."
    assert (
        len(progress.completed) == 0
    ), "Setup should have no blobs in completed state before reconciliation."
    assert (
        len(progress.failed) == 0
    ), "Setup should have no blobs in failed state before reconciliation."
    assert (
        len(progress.retried_completed) == 0
    ), "Setup should have no blobs in retried_completed state before reconciliation."

    _reconcile_in_progress(
        progress, test_destiny_repository_content_uploader, progress_file
    )

    assert len(progress.in_progress) == len(
        expected_in_progress_records
    ), "All in-progress blobs should be reconciled and marked as in-progress."
    assert set(progress.failed) == set(
        expected_failed_records.keys()
    ), "All previously in-progress blobs should now be marked as failed."
    assert (
        len(progress.failed) == 1
    ), "One blob should be marked as failed during reconciliation."
    assert (
        len(progress.retried_completed) == 0
    ), "No blobs should be marked as retried_completed during reconciliation when all are failed."


def test_reconcile_in_progress_all_failure_mix(
    tmp_path,
    mocker,
    test_destiny_repository_content_uploader,
):
    progress_file = tmp_path / "progress.json"
    base_blob_name = "test_blob"

    test_import_record_id = uuid4()
    test_in_progress_blob_names = [
        f"{base_blob_name}_part0001",
        f"{base_blob_name}_part0002",
        f"{base_blob_name}_part0003",
    ]

    test_batch_ids = [uuid4() for _ in test_in_progress_blob_names]

    test_in_progress_records = {
        name: InProgressRecord(
            import_record_id=test_import_record_id,
            import_batch_ids=[test_batch_ids[test_in_progress_blob_names.index(name)]],
        )
        for name in test_in_progress_blob_names
    }

    progress_data = {
        "in_progress": test_in_progress_records,
        "failed": [],
        "completed": [],
        "retried_completed": [],
    }
    progress = RegistrationProgress(**progress_data)

    _save_progress(progress_file, progress)

    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "get_import_batch_summary",
        side_effect=[
            ImportBatchSummary(
                storage_url="https://fake-storage-url",
                id=uuid4(),
                import_batch_id=test_batch_ids[0],
                import_batch_status=ImportBatchStatus.FAILED,
                results={
                    ImportResultStatus.FAILED: 1,
                },
                failure_details=None,
            ),
            ImportBatchSummary(
                storage_url="https://fake-storage-url",
                id=uuid4(),
                import_batch_id=test_batch_ids[1],
                import_batch_status=ImportBatchStatus.PARTIALLY_FAILED,
                results={
                    ImportResultStatus.PARTIALLY_FAILED: 1,
                },
                failure_details=None,
            ),
            ImportBatchSummary(
                storage_url="https://fake-storage-url",
                id=uuid4(),
                import_batch_id=test_batch_ids[2],
                import_batch_status=ImportBatchStatus.FAILED,
                results={
                    ImportResultStatus.FAILED: 1,
                },
                failure_details=None,
            ),
        ],
    )

    assert len(progress.in_progress) == len(
        test_in_progress_blob_names
    ), "Setup should have all test blobs in in-progress state before reconciliation."
    assert (
        len(progress.completed) == 0
    ), "Setup should have no blobs in completed state before reconciliation."
    assert (
        len(progress.failed) == 0
    ), "Setup should have no blobs in failed state before reconciliation."
    assert (
        len(progress.retried_completed) == 0
    ), "Setup should have no blobs in retried_completed state before reconciliation."

    _reconcile_in_progress(
        progress, test_destiny_repository_content_uploader, progress_file
    )

    assert (
        len(progress.in_progress) == 0
    ), "All in-progress blobs should be reconciled and marked as in-progress."
    assert set(progress.failed) == set(
        test_in_progress_blob_names
    ), "All previously in-progress blobs should now be marked as failed."
    assert len(progress.failed) == len(
        test_in_progress_blob_names
    ), "Three blobs should be marked as failed during reconciliation."
    assert (
        len(progress.retried_completed) == 0
    ), "No blobs should be marked as retried_completed during reconciliation when all are failed."


@pytest.mark.parametrize(
    ("batch_status", "batch_results", "expected_has_exit_status"),
    [
        (ImportBatchStatus.CREATED, {ImportResultStatus.CREATED: 10}, False),
        (ImportBatchStatus.STARTED, {ImportResultStatus.STARTED: 10}, False),
        (ImportBatchStatus.COMPLETED, {ImportResultStatus.COMPLETED: 10}, True),
    ],
)
def test_has_exit_status_success_path(
    batch_status, batch_results, expected_has_exit_status
):
    test_import_batch_id = uuid4()
    test_summary = ImportBatchSummary(
        storage_url="https://fake-storage-url",
        id=uuid4(),
        import_batch_id=test_import_batch_id,
        import_batch_status=batch_status,
        results=batch_results,
        failure_details=None,
    )

    result = _has_exit_status(
        test_summary,
        test_summary.import_batch_status,
        test_summary.import_batch_id,
    )

    assert result == expected_has_exit_status


@pytest.mark.parametrize(
    ("batch_status", "batch_results"),
    [
        (ImportBatchStatus.PARTIALLY_FAILED, {ImportResultStatus.CREATED: 10}),
        (ImportBatchStatus.FAILED, {ImportResultStatus.FAILED: 10}),
    ],
)
def test_has_exit_status_failure_path(batch_status, batch_results):
    test_import_batch_id = uuid4()
    test_summary = ImportBatchSummary(
        storage_url="https://fake-storage-url",
        id=uuid4(),
        import_batch_id=test_import_batch_id,
        import_batch_status=batch_status,
        results=batch_results,
        failure_details=None,
    )

    with pytest.raises(RepositoryRegistrationError):
        _has_exit_status(
            test_summary,
            test_summary.import_batch_status,
            test_summary.import_batch_id,
        )


def test_poll_registration_status_incomplete_to_complete_no_failures(
    mocker,
    test_destiny_repository_content_uploader,
):
    test_import_record_id = uuid4()
    test_import_batch_id = uuid4()
    test_summary_in_progress = ImportBatchSummary(
        storage_url="https://fake-storage-url",
        id=uuid4(),
        import_batch_id=test_import_batch_id,
        import_batch_status=ImportBatchStatus.STARTED,
        results={ImportResultStatus.STARTED: 10},
        failure_details=None,
    )
    test_summary_completed = ImportBatchSummary(
        storage_url="https://fake-storage-url",
        id=uuid4(),
        import_batch_id=test_import_batch_id,
        import_batch_status=ImportBatchStatus.COMPLETED,
        results={ImportResultStatus.COMPLETED: 10},
        failure_details=None,
    )

    test_batch_summary_result_set = [
        test_summary_in_progress,
        test_summary_in_progress,
        test_summary_completed,
    ]
    mocked_batch_summary_fetch = mocker.patch.object(
        DestinyRepositoryContentUploader,
        "get_import_batch_summary",
        side_effect=test_batch_summary_result_set,
    )

    mocker.patch("time.sleep")

    poll_registration_status(
        test_destiny_repository_content_uploader,
        test_import_record_id,
        test_import_batch_id,
        poll_interval=0,
    )

    assert mocked_batch_summary_fetch.call_count == len(
        test_batch_summary_result_set
    ), "Batch summary should be fetched repeatedly until completion is reached."


def test_poll_registration_status_incomplete_hangs_reaches_max_polling_limit(
    caplog,
    mocker,
    test_destiny_repository_content_uploader,
):
    test_import_record_id = uuid4()
    test_import_batch_id = uuid4()
    test_summary_in_progress = ImportBatchSummary(
        storage_url="https://fake-storage-url",
        id=uuid4(),
        import_batch_id=test_import_batch_id,
        import_batch_status=ImportBatchStatus.STARTED,
        results={ImportResultStatus.STARTED: 10},
        failure_details=None,
    )

    mocked_batch_summary_fetch = mocker.patch.object(
        DestinyRepositoryContentUploader,
        "get_import_batch_summary",
        return_value=test_summary_in_progress,
    )

    mocker.patch("time.sleep")

    expected_warning_message_excerpt = (
        f"Batch {test_import_batch_id} has not reached a terminal state after polling"
    )
    with (
        pytest.raises(RepositoryRegistrationError) as error_info,
        caplog.at_level(logging.WARNING),
    ):
        poll_registration_status(
            test_destiny_repository_content_uploader,
            test_import_record_id,
            test_import_batch_id,
            poll_interval=0,
            max_poll_limit_seconds=1,
        )

    assert (
        mocked_batch_summary_fetch.call_count > 1
    ), "Batch summary should be fetched multiple times until maximum polling limit is reached."
    assert (
        expected_warning_message_excerpt in caplog.text
    ), f"Expected warning message not found in logs: {caplog.text}"
    assert "Stopping polling to avoid infinite loop" in str(
        error_info.value
    ), f"Expected error message not found in exception: {error_info.value!s}"


@pytest.mark.parametrize(
    ("batch_status", "batch_results"),
    [
        (ImportBatchStatus.PARTIALLY_FAILED, {ImportResultStatus.PARTIALLY_FAILED: 10}),
        (ImportBatchStatus.FAILED, {ImportResultStatus.FAILED: 10}),
    ],
)
def test_poll_registration_status_partial_or_total_failure(
    mocker, test_destiny_repository_content_uploader, batch_status, batch_results
):
    test_import_record_id = uuid4()
    test_import_batch_id = uuid4()
    test_summary_failed = ImportBatchSummary(
        storage_url="https://fake-storage-url",
        id=uuid4(),
        import_batch_id=test_import_batch_id,
        import_batch_status=batch_status,
        results=batch_results,
        failure_details=["Test failure details"],
    )

    mocker.patch.object(
        DestinyRepositoryContentUploader,
        "get_import_batch_summary",
        return_value=test_summary_failed,
    )

    with pytest.raises(RepositoryRegistrationError) as error_info:
        poll_registration_status(
            test_destiny_repository_content_uploader,
            test_import_record_id,
            test_import_batch_id,
            poll_interval=0,
        )

    assert (
        f"Batch {test_import_batch_id} reached terminal state {batch_status}. Failure details: {test_summary_failed.failure_details}"
        in str(error_info.value)
    ), f"Expected error message not found in exception: {error_info.value!s}"
