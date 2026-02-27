"""
File processing pipeline for OpenAlex snapshot works files.

This covers streaming, converting, and uploading to blob storage.
"""

import asyncio
import gzip
import json
from collections.abc import AsyncIterator
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from openalex_incremental_updater.ingest.blob_storage import blob_upload_multipart
from openalex_incremental_updater.ingest.data import (
    JSONLConversionError,
    convert_destinyworks_to_jsonl_string,
)
from openalex_incremental_updater.ingest.openalex import safe_result_conversion
from openalex_snapshot_processor.config import Settings, get_settings

MAXIMUM_EXAMPLE_ERRORS = 5


class ProcessedFileMetadata(BaseModel):
    """
    Define a model for the processed file metadata.

    Attributes:
        blob_names (list[str]): A list of blob names that were uploaded as a result of processing the file.
        record_count (int): The total number of records that were processed and uploaded.
        error_log (str | None): The file path to the error log if any errors were

    """

    blob_names: list[str]
    record_count: int
    error_log: str | None


class ProcessedFile(ProcessedFileMetadata):
    """
    Data model representing the result of processing a single OpenAlex snapshot file.

    Attributes:
        file_path (Path): The original file path of the processed .gz file.
        base_blob_name (str): The derived base blob name used for uploaded files.

    """

    file_path: Path = Field(
        ..., description="The original file path of the processed .gz file."
    )
    base_blob_name: str = Field(
        ..., description="The derived base blob name used for uploaded files."
    )


def _log_errors(file_path: Path, errors: dict, log_dir: Path) -> Path | None:
    """
    Write the errors dict to a JSON log file if any errors were recorded.

    Files are written to log_dir, named after the source .gz file:

    Args:
        file_path: Path to the source .gz file being processed.
        errors: Error summary dict from gz_to_jsonl_stream.
        log_dir: Directory to write error logs to.

    Returns:
        Path to the written log file, or None if no errors were found.

    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{file_path.parent.name}__{file_path.stem}.errors.json"

    with log_file.open("w", encoding="utf-8") as output_error_file:
        json.dump(
            {"source": str(file_path), "errors": errors}, output_error_file, indent=2
        )

    total_errors = sum(
        value.get("total", len(value)) if isinstance(value, dict) else 0
        for value in errors.values()
    )
    logger.warning(f"Recorded {total_errors} errors for {file_path.name} in {log_file}")
    return log_file


def _derive_base_blob_name(file_path: Path) -> str:
    """
    Derive a deterministic base blob name from the source file.

    Maps e.g:

    /data/updated_date=2020-01-01/0000_part_00.gz
    to
    openalex_snapshot_works_2020-01-01_0000_part_00


    Args:
        file_path (Path): The local file path of the source .gz file being processed.

    Returns:
        str: The derived base blob name, without extension or part suffix.

    """
    date_segment = next(
        (part for part in file_path.parts if part.startswith("updated_date=")),
        "unknown_date",
    )

    date_string = date_segment.removeprefix("updated_date=")
    stem = file_path.stem
    return f"openalex_snapshot_works_{date_string}_{stem}"


async def _as_async_batches(batch: list) -> AsyncIterator[list]:
    """
    Convert a list into an async iterator yielding batches.

    Args:
        batch (list): The list to be converted into an async iterator.

    Yields:
        AsyncIterator[list]: An asynchronous iterator yielding batches of the input list.

    """
    yield batch


async def gz_to_jsonl_stream(file_path: Path, errors: dict) -> AsyncIterator[bytes]:
    """
    Stream a .gz file and yield transformed JSONL lines.

    Args:
        file_path (Path): The path to the .gz file to be streamed.

    Yields:
        AsyncIterator[bytes]: An asynchronous iterator yielding JSONL lines as bytes.

    """
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                raw_dict = json.loads(stripped)
            except json.JSONDecodeError as parse_error:
                entry = errors.setdefault(
                    "json_decode_errors", {"total": 0, "examples": []}
                )
                entry["total"] += 1
                if len(entry["examples"]) < MAXIMUM_EXAMPLE_ERRORS:
                    entry["examples"].append(str(parse_error))
                continue
            converted = safe_result_conversion([raw_dict], errors_dict=errors)
            try:
                async for item in convert_destinyworks_to_jsonl_string(
                    _as_async_batches(converted)
                ):
                    yield item
            except JSONLConversionError as json_conversion_error:
                entry = errors.setdefault(
                    "jsonl_conversion_errors", {"total": 0, "examples": []}
                )
                entry["total"] += 1
                if len(entry["examples"]) < MAXIMUM_EXAMPLE_ERRORS:
                    entry["examples"].append(str(json_conversion_error))


async def transform_file(file_path: Path) -> tuple[list[bytes], dict]:
    """
    Transform a file and return the resulting JSONL lines and any errors.

    Args:
        file_path (Path): The absolute local file path of the source .gz file being processed.

    Returns:
        tuple[list[bytes], dict]: A tuple containing a list of JSONL lines as bytes
            and a dictionary of any errors encountered during processing.

    """
    errors: dict = {}
    lines = [line async for line in gz_to_jsonl_stream(file_path, errors)]
    return lines, errors


async def _iter(items: list[bytes]) -> AsyncIterator[bytes]:
    """
    Convert a list of bytes into an async iterator.

    Args:
        items (list[bytes]): The list of bytes to be converted.

    Yields:
        AsyncIterator[bytes]: An asynchronous iterator yielding items from the input list.

    """
    for item in items:
        yield item


async def _upload(
    settings: Settings,
    lines: list[bytes],
    base_blob_name: str,
) -> list[str]:
    """
    Upload a list of JSONL lines to blob storage, split into parts.

    Args:
        settings (Settings): The application settings containing configuration values.
        lines (list[bytes]): A list of JSONL lines as bytes to be uploaded.
        base_blob_name (str): The base name to use for the uploaded blobs.

    Returns:
        list[str]: A list of blob names that were uploaded.

    """
    return await blob_upload_multipart(
        data=_iter(lines),
        base_filename=base_blob_name,
        batch_size=settings.BLOB_BATCH_SIZE,
    )


async def _process_file_async(
    settings: Settings, file_path: Path, base_blob_name: str, log_directory: Path
) -> ProcessedFileMetadata:
    """
    Process a single file asynchronously: stream, convert, and upload to blob storage.

    Args:
        settings (Settings): The application settings containing configuration values.
        file_path (Path): The local file path of the source .gz file being processed.
        base_blob_name (str): The base blob name to use for uploaded files.

    Returns:
        ProcessedFileMetadata: The full processed file report.

    """
    lines, errors = await transform_file(file_path)
    error_log_path = _log_errors(file_path, errors, log_directory) if errors else None
    if error_log_path:
        logger.warning(
            f"Errors encountered while transforming file {file_path}: {errors}"
        )
        logger.warning(f"Logged errors to {error_log_path}")
    blob_names = await _upload(settings, lines, base_blob_name)
    return ProcessedFileMetadata(
        blob_names=blob_names,
        record_count=len(lines),
        error_log=str(error_log_path) if error_log_path else None,
    )


async def process_files_async(file_paths: list[Path]) -> list[ProcessedFile]:
    """
    Process a batch of files asynchronously.

    Overlapping upload I/O across files to speed up the full batch processing time.

    Args:
        file_paths (list[Path]): The local file paths of the source .gz files being processed.

    Returns:
        list[ProcessedFile]: A list of ProcessedFile objects.

    """
    settings = get_settings()
    log_directory = Path(__file__).parent / "logs"
    base_blob_names = [_derive_base_blob_name(file_path) for file_path in file_paths]

    tasks = [
        _process_file_async(settings, path, base_blob_name, log_directory)
        for path, base_blob_name in zip(file_paths, base_blob_names, strict=False)
    ]
    results = await asyncio.gather(*tasks)

    return [
        ProcessedFile(
            blob_names=result.blob_names,
            record_count=result.record_count,
            error_log=result.error_log,
            file_path=file_path,
            base_blob_name=base_blob_name,
        )
        for file_path, base_blob_name, result in zip(
            file_paths, base_blob_names, results, strict=False
        )
    ]


def process_file_batch(file_paths: list[Path]) -> list[dict]:
    """
    Process a batch of files, return one result dict per file.

    Upload I/O overlaps across files within a batch
    to speed up the full batch processing time.

    Args:
        file_paths (list[Path]): A list of local file paths to process.

    Returns:
        list[dict]: A list of ProcessedFile metadata dicts, one per file.

    """
    return [
        processed_file.model_dump()
        for processed_file in asyncio.run(process_files_async(file_paths))
    ]
