from uuid import uuid4

import pytest
from destiny_sdk.imports import ImportRecordRead, ImportRecordStatus

from openalex_snapshot_processor.registration import ImportReport, register_file_blobs
from refresh_requester.repository import DestinyRepositoryImportError


def test_register_file_blobs_success(mocker, set_test_environment_variables):
    test_import_record_id = uuid4()
    test_batch_id = uuid4()
    expected_upload_result = {
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
    mocker.patch(
        "openalex_snapshot_processor.registration.upload_blob_storage_contents_to_repository",
        return_value=expected_upload_result,
    )

    result = register_file_blobs("test_base_blob_name")
    assert isinstance(
        result, ImportReport
    ), "Result should be an instance of ImportReport."
    assert (
        result.import_record.id == test_import_record_id
    ), "Import record ID should match the mocked value."
    assert result.import_batch_ids == [
        test_batch_id
    ], "Import batch IDs should match the mocked value."


def test_register_file_blobs_import_failure(
    caplog, mocker, set_test_environment_variables
):
    mocker.patch(
        "openalex_snapshot_processor.registration.upload_blob_storage_contents_to_repository",
        side_effect=DestinyRepositoryImportError("Mocked import error"),
    )

    with caplog.at_level("ERROR"), pytest.raises(DestinyRepositoryImportError):
        register_file_blobs("test_base_blob_name")

    assert (
        "Error during import: Mocked import error" in caplog.text
    ), "Error message should be logged when import fails."
