import gzip
import json
from pathlib import Path

from destiny_sdk.references import ReferenceFileInput

from openalex_incremental_updater.ingest.blob_storage import blob_upload_multipart
from openalex_incremental_updater.ingest.data import JSONLConversionError
from openalex_snapshot_processor.file_processor import (
    _as_async_batches,
    _derive_base_blob_name,
    _gz_to_jsonl_stream,
    process_file,
)


def test_derive_base_blob_name():
    file_path = Path("snapshot_works_root/updated_date=2020-01-01/part-00000.gz")
    expected_base_blob_name = "openalex_snapshot_works_2020-01-01_part-00000"
    assert _derive_base_blob_name(file_path) == expected_base_blob_name


def test_derive_base_blob_name_no_date():
    file_path = Path("snapshot_works_root/part-00000.gz")
    expected_base_blob_name = "openalex_snapshot_works_unknown_date_part-00000"
    assert _derive_base_blob_name(file_path) == expected_base_blob_name


async def test_as_async_batches():
    batch = [1, 2, 3, 4]
    async_iter = _as_async_batches(batch)
    async_batch = [batch_contents async for batch_contents in async_iter]
    assert async_batch == [batch]


async def test_gz_to_jsonl_stream_success(test_jsonl_gz_file):
    gz_file_path, sample_data = test_jsonl_gz_file

    expected_ids_dicts = [item["ids"] for item in sample_data]
    possible_identifiers = [
        id_value
        for expected_ids in expected_ids_dicts
        for id_value in expected_ids.values()
    ]
    bare_identifiers = [
        candidate_identifier.rsplit(".org/", 1)[-1]
        for candidate_identifier in possible_identifiers
    ]

    async for line in _gz_to_jsonl_stream(str(gz_file_path)):
        destiny_reference = ReferenceFileInput.from_jsonl(line)
        assert isinstance(
            destiny_reference, ReferenceFileInput
        ), "Each line should be converted to a ReferenceFileInput instance."
        assert len(destiny_reference.identifiers) == len(
            expected_ids_dicts[0]
        ), "The number of identifiers should match the expected count."

        for identifier in destiny_reference.identifiers:
            assert (
                identifier.identifier in bare_identifiers
            ), f"Identifier {identifier.identifier} should be in the expected identifiers list."


async def test_gz_to_jsonl_stream_invalid_json(mocker, tmp_path):
    gz_file_path = tmp_path / "invalid.jsonl.gz"
    with gzip.open(gz_file_path, "at", encoding="utf-8") as gz_file:
        gz_file.write("A test jsonl file\n\n")

    errors = {}
    async for line in _gz_to_jsonl_stream(str(gz_file_path)):
        if line.startswith(b'{"errors":'):
            errors = json.loads(line.decode("utf-8"))["errors"]

    assert (
        "json_decode_errors" in errors
    ), "Errors dictionary should contain 'json_decode_errors' key for invalid JSON lines."


async def test_gz_to_jsonl_stream_jsonl_conversion_error(mocker, tmp_path):
    gz_file_path = tmp_path / "invalid.jsonl.gz"
    with gzip.open(gz_file_path, "at", encoding="utf-8") as gz_file:
        gz_file.write('{"data": "A test jsonl file"}\n')
    mocker.patch("openalex_snapshot_processor.file_processor.safe_result_conversion")
    mocker.patch(
        "openalex_snapshot_processor.file_processor.convert_destinyworks_to_jsonl_string",
        side_effect=JSONLConversionError("Test conversion error"),
    )
    errors = {}
    async for line in _gz_to_jsonl_stream(str(gz_file_path)):
        if line.startswith(b'{"errors":'):
            errors = json.loads(line.decode("utf-8"))["errors"]

    assert (
        "jsonl_conversion_errors" in errors
    ), "Errors dictionary should contain 'jsonl_conversion_errors' key for invalid JSONL conversion errors."


async def test_process_file_async(mocker, test_settings, test_jsonl_gz_file):
    gz_file_path, _file_contents = test_jsonl_gz_file
    stream = _gz_to_jsonl_stream(gz_file_path)
    base_blob_name = _derive_base_blob_name(gz_file_path)
    mocker.patch("openalex_incremental_updater.ingest.blob_storage.blob_upload")

    blob_batch_size = test_settings.BLOB_BATCH_SIZE
    uploaded_blobs = await blob_upload_multipart(
        data=stream,
        base_filename=base_blob_name,
        batch_size=blob_batch_size,
    )
    assert len(uploaded_blobs) == 1, "Should upload one blob for the test data."
    assert uploaded_blobs[0].startswith(
        base_blob_name
    ), "Uploaded blob name should start with the base blob name."


def test_process_file(mocker, test_jsonl_gz_file, set_test_environment_variables):
    gz_file_path, _file_contents = test_jsonl_gz_file
    mocker.patch(
        "openalex_snapshot_processor.file_processor._process_file_async",
        return_value=["test_blob_name"],
    )
    result = process_file(str(gz_file_path))
    assert (
        result
        == {
            "file_path": str(gz_file_path),
            "base_blob_name": _derive_base_blob_name(gz_file_path),
            "blob_names": ["test_blob_name"],
        }
    ), "The process_file function should return the expected dictionary with file path, base blob name, and blob names."
