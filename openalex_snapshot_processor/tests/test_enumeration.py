import pytest

from openalex_snapshot_processor.enumeration import enumerate_work_files


def test_enumerate_work_files_success(mocker):
    snapshot_works_root = "tests/fixtures/snapshot_works_root"
    expected_files = [
        "updated_date=2020-01-01/part-00000.gz",
        "updated_date=2020-01-02/part-00000.gz",
        "updated_date=2020-01-03/part-00000.gz",
    ]
    dummy_manifest = {
        "entries": [
            {"url": f"s3://openalex-snapshot/works/{file_name}"}
            for file_name in expected_files
        ]
    }

    mocker.patch(
        "openalex_snapshot_processor.enumeration.Path.exists", return_value=True
    )
    mocker.patch(
        "openalex_snapshot_processor.enumeration._read_manifest_content",
        return_value=dummy_manifest,
    )
    result = enumerate_work_files(snapshot_works_root)

    assert all(
        any(expected_file in str(file_path) for file_path in result)
        for expected_file in expected_files
    )


def test_enumerate_work_files_failure_file_not_found(mocker):
    snapshot_works_root = "tests/fixtures/snapshot_works_root"

    mocker.patch(
        "openalex_snapshot_processor.enumeration.Path.exists", return_value=False
    )
    with pytest.raises(FileNotFoundError):
        enumerate_work_files(snapshot_works_root)


def test_enumerate_work_files_failure_missing_keys(mocker):
    snapshot_works_root = "tests/fixtures/snapshot_works_root"
    dummy_manifest = {"invalid_entries": []}

    mocker.patch(
        "openalex_snapshot_processor.enumeration.Path.exists", return_value=True
    )
    mocker.patch(
        "openalex_snapshot_processor.enumeration._read_manifest_content",
        return_value=dummy_manifest,
    )

    result = enumerate_work_files(snapshot_works_root)

    assert result == []


def test_enumerate_work_files_partial_success_missing_files(
    mocker,
):
    snapshot_works_root = "tests/fixtures/snapshot_works_root"
    test_files = [
        "updated_date=2020-01-01/part-00000.gz",
        "updated_date=2020-01-02/part-00000.gz",
        "updated_date=2020-01-03/part-00000.gz",
    ]
    included_files = test_files[:2]
    excluded_files = test_files[2:]
    dummy_manifest = {
        "entries": [
            {"url": f"s3://openalex-snapshot/works/{file_name}"}
            for file_name in test_files
        ]
    }

    def mock_exists_side_effect(self):
        excluded_file_stem = [
            excluded_file.split("/")[0] for excluded_file in excluded_files
        ]
        return not any(stem in str(self) for stem in excluded_file_stem)

    mocker.patch(
        "openalex_snapshot_processor.enumeration.Path.exists", mock_exists_side_effect
    )
    mocker.patch(
        "openalex_snapshot_processor.enumeration._read_manifest_content",
        return_value=dummy_manifest,
    )

    result = enumerate_work_files(snapshot_works_root)

    assert all(
        any(included_file in str(file_path) for file_path in result)
        for included_file in included_files
    )
    assert not any(
        excluded_file in str(file_path)
        for file_path in result
        for excluded_file in excluded_files
    )
