"""Enumerate local compressed files from the OpenAlex snapshot."""

import json
from pathlib import Path

from loguru import logger


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


def enumerate_work_files(snapshot_works_root: str) -> list[Path]:
    """
    Read the Works manifest and return a sorted list of files.

    Files should be locally available at a path provided as an argument.

    Args:
        snapshot_works_root (str): The local directory path where OpenAlex snapshot work files are stored.

    Returns:
        list[Path]: A sorted list of Path objects representing the local work files in the snapshot.

    Raises:
        FileNotFoundError: If the snapshot works root directory does not exist.
        KeyError: If the manifest file is missing or does not contain the expected keys.

    """
    manifest_path = Path(snapshot_works_root) / "manifest"

    manifest = _read_manifest_content(manifest_path)

    entries = manifest.get("entries", [])
    logger.info(f"Found {len(entries)} entries in manifest.")

    file_paths: list[Path] = []
    missing: list[Path] = []

    for entry in entries:
        s3_url = entry.get("url")
        relative_path = s3_url.replace("s3://openalex-snapshot/works/", "")
        local_file_path = Path(snapshot_works_root) / relative_path

        if not Path(local_file_path).exists():
            missing.append(local_file_path)
        else:
            file_paths.append(local_file_path)

    if missing:
        logger.warning(
            f"{len(missing)} files listed in manifest are missing locally. Missing files: {missing}"
        )
        with Path("./missing_files.log").open("w", encoding="utf-8") as missing_log:
            for missing_file in missing:
                missing_log.write(f"{missing_file}\n")

    logger.info(
        f"{len(file_paths)} files are available locally, {len(missing)} files are missing."
    )
    return sorted(file_paths)
