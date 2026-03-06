import gzip
import json
from pathlib import Path

from destiny_sdk.enhancements import (
    AuthorPosition,
    Authorship,
    BibliographicMetadataEnhancement,
)
from destiny_sdk.references import ReferenceFileInput
from pydantic import ValidationError

from openalex_incremental_updater.ingest.blob_storage import blob_upload_multipart
from openalex_incremental_updater.ingest.data import JSONLConversionError
from openalex_incremental_updater.ingest.openalex import safe_result_conversion
from openalex_snapshot_processor.file_processor import (
    ProcessedFile,
    ProcessedFileMetadata,
    _as_async_batches,
    _check_converted_result_for_authorships,
    _derive_base_blob_name,
    _log_errors,
    construct_destiny_authorships_order_not_found,
    gz_to_jsonl_stream,
    process_files_async,
)


def test_log_errors(tmp_path):
    file_path = tmp_path / "test_file.gz"
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    expected_errors = {
        "json_decode_errors": {"total": 3, "examples": ["foo", "bar", "baz"]},
        "jsonl_conversion_errors": {"total": 2, "examples": ["qux", "quux"]},
    }
    error_log_path = _log_errors(file_path, expected_errors, log_dir)
    assert (
        error_log_path is not None
    ), "Error log path should not be None when errors are present."
    assert error_log_path.exists(), "Error log file should be created."
    assert (
        f"{file_path.stem}.errors.json" in error_log_path.name
    ), "Error log file name should include the source file name."
    with error_log_path.open("r", encoding="utf-8") as f:
        logged_errors = json.load(f)
    assert (
        logged_errors["errors"] == expected_errors
    ), "Logged errors should match the input errors."
    assert logged_errors["source"] == str(file_path)


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

    async for line in gz_to_jsonl_stream(gz_file_path, {}):
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
    async for line in gz_to_jsonl_stream(str(gz_file_path), errors):
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
    async for line in gz_to_jsonl_stream(str(gz_file_path), errors):
        if line.startswith(b'{"errors":'):
            errors = json.loads(line.decode("utf-8"))["errors"]

    assert (
        "jsonl_conversion_errors" in errors
    ), "Errors dictionary should contain 'jsonl_conversion_errors' key for invalid JSONL conversion errors."


async def test_process_file_async(mocker, test_settings, test_jsonl_gz_file):
    gz_file_path, _file_contents = test_jsonl_gz_file
    stream = gz_to_jsonl_stream(gz_file_path, {})
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


async def test_process_files_async(
    mocker, tmp_path, test_jsonl_gz_file, set_test_environment_variables
):
    gz_file_path, _file_contents = test_jsonl_gz_file
    expected_processed_file_report = ProcessedFileMetadata(
        blob_names=["test_blob_name"],
        record_count=10,
        error_log=None,
    )
    test_log_directory = tmp_path / "logs"
    mocker.patch(
        "openalex_snapshot_processor.file_processor._process_file_async",
        return_value=expected_processed_file_report,
    )
    result = await process_files_async([gz_file_path], test_log_directory)
    assert result == [
        ProcessedFile(
            blob_names=expected_processed_file_report.blob_names,
            record_count=expected_processed_file_report.record_count,
            error_log=expected_processed_file_report.error_log,
            file_path=str(gz_file_path),
            base_blob_name=_derive_base_blob_name(gz_file_path),
        )
    ], "Should return the expected list of ProcessedFile objects."


def test_construct_destiny_authorships_order_not_found_success(openalex_work_dict):
    errors_dict = {}
    openalex_work_dict_no_positions = openalex_work_dict.copy()
    for authorship in openalex_work_dict_no_positions.get("authorships", []):
        authorship.pop("author_position", None)
    authorships = construct_destiny_authorships_order_not_found(
        openalex_work_dict_no_positions, errors_dict
    )
    assert all(
        isinstance(authorship, Authorship) for authorship in authorships
    ), "Authorships should be returned as a list of Authorship objects."
    assert len(authorships) == len(
        openalex_work_dict.get("authorships", [])
    ), "The number of authorships should match the input data."
    assert all(
        authorship.display_name is not None for authorship in authorships
    ), "Each authorship should have a display name."
    assert all(
        authorship.position is not None for authorship in authorships
    ), "Each authorship should have a position assigned."
    assert (
        sum(
            1
            for authorship in authorships
            if authorship.position == AuthorPosition.FIRST
        )
        == 1
    ), "There should be exactly one first author."
    assert (
        sum(
            1
            for authorship in authorships
            if authorship.position == AuthorPosition.LAST
        )
        == 1
    ), "There should be exactly one last author."
    if len(authorships) > len(set({"first", "last"})):
        assert sum(
            1
            for authorship in authorships
            if authorship.position == AuthorPosition.MIDDLE
        ) == len(authorships) - len(
            set({"first", "last"})
        ), "The number of middle authors should be total authors minus two."
    assert (
        len(errors_dict) == 0
    ), "There should be no errors logged for valid authorship data."


def test_construct_destiny_authorships_order_not_found_failure_author_dict_not_found(
    caplog, openalex_work_dict
):
    errors_dict = {}
    work_dict_no_author_dicts_in_authorships = openalex_work_dict.copy()
    for authorship in work_dict_no_author_dicts_in_authorships.get("authorships", []):
        authorship.pop("author", None)

    expected_error_message = "Author name not found in Authorship"
    expected_total_authorship_construction_errors = len(
        work_dict_no_author_dicts_in_authorships.get("authorships", [])
    )

    with caplog.at_level("WARNING"):
        authorships = construct_destiny_authorships_order_not_found(
            work_dict_no_author_dicts_in_authorships, errors_dict
        )
    total_authorship_errors_found = errors_dict.get(
        "authorship_construction_errors", {}
    ).get("total", 0)
    assert (
        total_authorship_errors_found == expected_total_authorship_construction_errors
    )
    assert (
        expected_error_message in caplog.text
    ), "Should log a warning when no authorships are found."
    assert (
        authorships == []
    ), "Should return an empty list when no authorships are present."
    assert (
        len(errors_dict) == 1
    ), "Should log one error type when no authorships are found."


def test_construct_destiny_authorships_order_not_found_failure_no_display_name(
    openalex_work_dict,
):
    work_dict_no_display_names = openalex_work_dict.copy()
    for authorship in work_dict_no_display_names.get("authorships", []):
        if "author" in authorship:
            authorship["author"].pop("display_name", None)
            authorship.pop("author_position", None)

    test_errors_dict = {}

    authorships = construct_destiny_authorships_order_not_found(
        work_dict_no_display_names, test_errors_dict
    )

    total_authorship_construction_errors_found = test_errors_dict.get(
        "authorship_construction_errors", {}
    ).get("total", 0)
    expected_total_authorship_construction_errors = len(
        work_dict_no_display_names.get("authorships", [])
    )
    assert all(
        authorship.display_name is None for authorship in authorships
    ), "Authorship display names should be None when not present in input data."
    assert all(
        authorship.position is not None for authorship in authorships
    ), "Authorships should be empty if display names are missing."
    assert (
        not authorships
    ), "Authorships list should be empty when display names are missing."
    assert (
        total_authorship_construction_errors_found
        == expected_total_authorship_construction_errors
    ), "Should log an error for each authorship with missing display name."


def test_check_converted_result_for_authorships_success(openalex_work_dict):
    errors_dict = {}
    openalex_work_dict_no_author_positions = openalex_work_dict.copy()

    expected_authorship_objects = openalex_work_dict.get("authorships", [])
    expected_display_names = [
        authorship["author"]["display_name"]
        for authorship in expected_authorship_objects
    ]
    expected_positions = [
        authorship["author_position"] for authorship in expected_authorship_objects
    ]
    for authorship in openalex_work_dict_no_author_positions.get("authorships", []):
        authorship.pop("author_position", None)

    converted_destiny_work = safe_result_conversion(
        [openalex_work_dict], errors_dict=errors_dict
    )

    converted_destiny_work_authorships = [
        authorship
        for work in converted_destiny_work
        for authorship in getattr(work, "authorships", [])
    ]
    assert not converted_destiny_work_authorships
    results = _check_converted_result_for_authorships(
        converted_destiny_work, openalex_work_dict, errors_dict
    )
    assert all(
        result.identifiers in [work.identifiers for work in converted_destiny_work]
        for result in results
    ), "All identifiers found in the originally converted work should be present in the results."

    result_authorships = [
        authorship
        for result in results
        for enhancement in result.enhancements
        if isinstance(enhancement.content, BibliographicMetadataEnhancement)
        for authorship in (enhancement.content.authorship or [])
    ]

    assert all(
        isinstance(authorship, Authorship) for authorship in result_authorships
    ), "Authorships should be returned as a list of Authorship objects."
    assert len(result_authorships) == len(
        expected_authorship_objects
    ), "The number of authorships should match the input data."
    assert all(
        authorship.display_name
        in [
            expected_authorship["author"]["display_name"]
            for expected_authorship in expected_authorship_objects
        ]
        for authorship in result_authorships
    ), "Each authorship display name should match the expected display names from the input data."

    assert (
        sorted(author.display_name for author in result_authorships)
        == sorted(expected_display_names)
    ), "The display names of the resulting authorships should match the expected display names from the input data."
    assert (
        sorted(author.position.value for author in result_authorships)
        == sorted(expected_positions)
    ), "The positions of the resulting authorships should match the expected positions from the input data."
    assert (
        "authorship_construction_errors" not in errors_dict
    ), "There should be no authorship construction errors logged for valid authorship data."


def test_check_converted_result_for_authorships_failure_validation_error(
    mocker, openalex_work_dict
):
    errors_dict = {}

    work_dict_no_positions = openalex_work_dict.copy()
    expected_total_authorships = len(openalex_work_dict.get("authorships", []))
    for authorship in work_dict_no_positions.get("authorships", []):
        authorship.pop("author_position", None)
    converted_destiny_work = safe_result_conversion(
        [work_dict_no_positions], errors_dict=errors_dict
    )

    try:
        Authorship(display_name=None, position=None)
    except ValidationError as e:
        validation_error = e

    mocker.patch(
        "openalex_snapshot_processor.file_processor.Authorship",
        side_effect=validation_error,
    )

    _check_converted_result_for_authorships(
        converted_destiny_work, openalex_work_dict, errors_dict
    )

    assert (
        errors_dict.get("authorship_construction_errors", {}).get("total", 0)
        == expected_total_authorships
    ), "Should log one error per authorship when Authorship construction raises ValidationError."
