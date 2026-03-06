"""
File processing pipeline for OpenAlex snapshot works files.

This covers streaming, converting, and uploading to blob storage.
"""

import asyncio
import gzip
import json
from collections.abc import AsyncIterator
from pathlib import Path

from destiny_sdk.enhancements import (
    AuthorPosition,
    Authorship,
    BibliographicMetadataEnhancement,
)
from destiny_sdk.references import ReferenceFileInput
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from openalex_incremental_updater.ingest.blob_storage import blob_upload_multipart
from openalex_incremental_updater.ingest.data import (
    JSONLConversionError,
    convert_destinyworks_to_jsonl_string,
)
from openalex_incremental_updater.ingest.openalex import safe_result_conversion
from openalex_snapshot_processor.config import Settings, get_settings

MAXIMUM_EXAMPLE_ERRORS = 5


class UploadCounter(BaseModel):
    """
    A counter for tracking the number of items within an upload to blob storage.

    Attributes:
        value (int): The current count of items in the upload.

    """

    value: int = 0


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


def construct_destiny_authorships_order_not_found(
    openalex_work_dict: dict,
    errors_dict: dict,
) -> list[Authorship]:
    """
    Prepare a list of authorships for the Destiny OpenAlex work.

    Makes conversion less DRY than hoped for, but retains authorship information
    in snapshot file ingest, where it looks like authorship position information is missing.

    Args:
        openalex_work_dict (dict): The OpenAlex work metadata as a dictionary.
        errors_dict (dict): The errors dictionary to be updated with any errors encountered.

    Returns:
        list[Authorship]: A list of Authorship objects.

    """
    authorships: list[Authorship] = []
    openalex_authorships_dict = openalex_work_dict.get("authorships", [])

    for author_index, author in enumerate(openalex_authorships_dict):
        author_data = author.get("author") or {}
        display_name = author_data.get("display_name", "")
        orcid = author_data.get("orcid", None)
        position_str = author.get("author_position", "") or str(author_index)

        if not display_name:
            logger.warning(
                f"Author name not found in Authorship for Work {openalex_work_dict.get('id', 'unknown_id')}"
            )
            entry = errors_dict.setdefault(
                "authorship_construction_errors", {"total": 0, "examples": []}
            )
            entry["total"] += 1
            if len(entry["examples"]) < MAXIMUM_EXAMPLE_ERRORS:
                entry["examples"].append(
                    {
                        "display_name": display_name,
                        "position": position_str,
                        "error": "Author name not found",
                    }
                )
            continue

        author_position_valid_values = {position.value for position in AuthorPosition}
        if position_str.lower() not in author_position_valid_values:
            logger.warning(
                f"Fixing authorship for {display_name} with invalid position {position_str}"
                f" in {openalex_work_dict.get('id', 'unknown_id')}."
            )
            is_first_author = int(author_index) == 0
            is_last_author = int(author_index) == len(openalex_authorships_dict) - 1
            is_middle_author = not is_first_author and not is_last_author

            if is_first_author:
                position_str = AuthorPosition.FIRST
            elif is_last_author:
                position_str = AuthorPosition.LAST
            elif is_middle_author:
                position_str = AuthorPosition.MIDDLE

        try:
            authorships.append(
                Authorship(
                    display_name=display_name,
                    orcid=orcid,
                    position=position_str,
                )
            )
        except ValidationError as authorship_construction_validation_error:
            logger.warning(
                f"Failed to construct Authorship for {display_name}"
                f" in work {openalex_work_dict.get('id', 'unknown_id')}:"
                f" {authorship_construction_validation_error}"
            )
            entry = errors_dict.setdefault(
                "authorship_construction_errors", {"total": 0, "examples": []}
            )
            entry["total"] += 1
            if len(entry["examples"]) < MAXIMUM_EXAMPLE_ERRORS:
                entry["examples"].append(
                    {
                        "display_name": display_name,
                        "position": position_str,
                        "validation_error": str(
                            authorship_construction_validation_error
                        ),
                    }
                )

    return authorships


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


async def _counted_stream(
    source: AsyncIterator[bytes], counter: UploadCounter
) -> AsyncIterator[bytes]:
    """
    Wrap an async iterator to count the number of items yielded.

    Updates the total count in the provided UploadCounter instance.

    Args:
        source (AsyncIterator[bytes]): The original async iterator yielding items to be uploaded.
        counter (UploadCounter): The upload counter to be updated.

    Returns:
        AsyncIterator[bytes]: The async iterator yielding items with counting.

    """
    async for item in source:
        counter.value += 1
        yield item


async def _as_async_batches(batch: list) -> AsyncIterator[list]:
    """
    Convert a list into an async iterator yielding batches.

    Args:
        batch (list): The list to be converted into an async iterator.

    Yields:
        AsyncIterator[list]: An asynchronous iterator yielding batches of the input list.

    """
    yield batch


def _check_converted_result_for_authorships(
    converted: list[ReferenceFileInput],
    openalex_work_dict: dict,
    errors_dict: dict,
) -> list[ReferenceFileInput]:
    """
    Determine authorship order if these are missing from the converted result.

    Args:
        converted (list[ReferenceFileInput]): The converted result from safe_result_conversion.
        openalex_work_dict (dict): The OpenAlex work metadata as a dictionary.
        errors_dict (dict): The errors dictionary to be updated with any errors encountered.

    Returns:
        list[ReferenceFileInput]: The converted result with authorship information filled in where missing.

    """
    for result_index, converted_result in enumerate(converted):
        enhancements = converted_result.enhancements
        for enhancement_index, enhancement in enumerate(enhancements):
            if isinstance(enhancement.content, BibliographicMetadataEnhancement):
                if not enhancement.content.authorship:
                    enhancement.content.authorship = (
                        construct_destiny_authorships_order_not_found(
                            openalex_work_dict, errors_dict
                        )
                    )

                converted[result_index].enhancements[enhancement_index] = enhancement

    return converted


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
            finalised = _check_converted_result_for_authorships(
                converted, raw_dict, errors
            )
            try:
                async for item in convert_destinyworks_to_jsonl_string(
                    _as_async_batches(finalised)
                ):
                    yield item
            except JSONLConversionError as json_conversion_error:
                entry = errors.setdefault(
                    "jsonl_conversion_errors", {"total": 0, "examples": []}
                )
                entry["total"] += 1
                if len(entry["examples"]) < MAXIMUM_EXAMPLE_ERRORS:
                    entry["examples"].append(str(json_conversion_error))


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
    errors: dict = {}
    counter = UploadCounter()

    blob_names = await blob_upload_multipart(
        data=_counted_stream(gz_to_jsonl_stream(file_path, errors), counter),
        base_filename=base_blob_name,
        batch_size=settings.BLOB_BATCH_SIZE,
    )
    error_log_path = _log_errors(file_path, errors, log_directory) if errors else None
    if error_log_path:
        logger.warning(
            f"Errors encountered while transforming file {file_path}: {errors}"
        )
        logger.warning(f"Logged errors to {error_log_path}")

    return ProcessedFileMetadata(
        blob_names=blob_names,
        record_count=counter.value,
        error_log=str(error_log_path) if error_log_path else None,
    )


async def process_files_async(
    file_paths: list[Path], log_directory: Path
) -> list[ProcessedFile]:
    """
    Process a batch of files asynchronously.

    Overlapping upload I/O across files to speed up the full batch processing time.

    Args:
        file_paths (list[Path]): The local file paths of the source .gz files being processed.

    Returns:
        list[ProcessedFile]: A list of ProcessedFile objects.

    """
    settings = get_settings()
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


def process_file_batch(file_paths: list[Path], log_directory: Path) -> list[dict]:
    """
    Process a batch of files, return one result dict per file.

    Upload I/O overlaps across files within a batch
    to speed up the full batch processing time.

    Args:
        file_paths (list[Path]): A list of local file paths to process.
        log_directory (Path): The directory to use for logging errors.

    Returns:
        list[dict]: A list of ProcessedFile metadata dicts, one per file.

    """
    return [
        processed_file.model_dump()
        for processed_file in asyncio.run(
            process_files_async(file_paths, log_directory)
        )
    ]
