"""Enumerate local compressed files from the OpenAlex snapshot."""

import json
from pathlib import Path

from loguru import logger

DEFAULT_MAX_BATCH_SIZE = 100_000


def _read_manifest_content(manifest_path: Path) -> dict:
    """
    Read the manifest file content and return it as a dictionary.

    Args:
        manifest_path (Path): The Path object representing the location of the manifest file.

    Raises:
        FileNotFoundError: If the manifest file does not exist at the specified path.

    Returns:
        dict: The content of the manifest file as a dictionary.

    """
    if not manifest_path.exists():
        error_message = f"Manifest file not found at {manifest_path}"
        logger.error(error_message)
        raise FileNotFoundError(error_message)

    with manifest_path.open("r", encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def enumerate_work_files(snapshot_works_root: str) -> list[tuple[Path, int]]:
    """
    Read the Works manifest and return a sorted list of files.

    Files should be locally available at a path provided as an argument.

    Args:
        snapshot_works_root (str): The local directory path where OpenAlex snapshot work files are stored.

    Returns:
        list[tuple[Path, int]]: A sorted list of tuples containing the file path of local snapshot files
            and their corresponding record counts.

    Raises:
        FileNotFoundError: If the snapshot works root directory does not exist.
        KeyError: If the manifest file is missing or does not contain the expected keys.

    """
    manifest_path = Path(snapshot_works_root) / "manifest"

    manifest = _read_manifest_content(manifest_path)

    entries = manifest.get("entries", [])
    logger.info(f"Found {len(entries)} entries in manifest.")

    file_path_counts: list[tuple[Path, int]] = []
    missing: list[Path] = []

    for entry in entries:
        s3_url = entry.get("url")
        relative_path = s3_url.replace("s3://openalex/data/works/", "")
        local_file_path = Path(snapshot_works_root) / relative_path
        record_count = entry.get("meta", {}).get("record_count", 0)

        if not Path(local_file_path).exists():
            missing.append(local_file_path)
        else:
            file_path_counts.append((local_file_path, record_count))

    if missing:
        logger.warning(
            f"{len(missing)} files listed in manifest are missing locally. Missing files: {missing}"
        )
        missing_log_path = Path(__file__).parent.parent / "missing_files.log"
        with missing_log_path.open("w", encoding="utf-8") as missing_log:
            for missing_file in missing:
                missing_log.write(f"{missing_file}\n")

    logger.info(
        f"{len(file_path_counts)} files are available locally, {len(missing)} files are missing."
    )
    return sorted(file_path_counts, key=lambda x: x[0].name)


def batch_files_by_record_count(
    file_path_counts: list[tuple[Path, int]],
    max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
) -> list[list[Path]]:
    """
    Batch records within files into batches that stay under max_batch_size records.

    Files are processed in sorted order, with oldest files first, until max_batch_size is reached.
    If reaching max_batch_size would require splitting a file, the would-be split file is not added
    to the batch and is instead added to the next batch.

    Files whose own record count exceeds max_batch_size are emitted as a single batch.
    They are never skipped.
    This means that batches may exceed max_batch_size if a single file's record count exceeds
    max_batch_size, but files are never split.


    Args:
        file_path_counts (list[tuple[Path, int]]): A list of tuples containing file paths
        and their corresponding record counts.
        max_batch_size (int): The maximum total record count allowed in each batch.

    Returns:
        list[list[Path]]: A list of batches, where each batch is a list of file paths.

    """
    batches: list[list[Path]] = []
    current_batch: list[Path] = []
    current_count = 0

    for path, count in file_path_counts:
        if current_batch and current_count + count > max_batch_size:
            batches.append(current_batch)
            current_batch = []
            current_count = 0
        current_batch.append(path)
        current_count += count
    if current_batch:
        batches.append(current_batch)

    logger.info(
        f"Batched {len(file_path_counts)} files into {len(batches)} batches"
        f" with max batch size of {max_batch_size} records."
    )
    return batches
