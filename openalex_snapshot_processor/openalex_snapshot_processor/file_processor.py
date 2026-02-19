"""
File processing pipeline for OpenAlex snapshot works files.

This covers streaming, converting, and uploading to blob storage.
"""

import asyncio
import gzip
import json
from collections.abc import AsyncIterator
from pathlib import Path

from openalex_incremental_updater.ingest.blob_storage import blob_upload_multipart
from openalex_incremental_updater.ingest.data import (
    JSONLConversionError,
    convert_destinyworks_to_jsonl_string,
)
from openalex_incremental_updater.ingest.openalex import safe_result_conversion
from openalex_snapshot_processor.config import Settings, get_settings


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


async def _gz_to_jsonl_stream(file_path: Path) -> AsyncIterator[bytes]:
    """
    Stream a .gz file and yield transformed JSONL lines.

    Args:
        file_path (Path): The path to the .gz file to be streamed.

    Yields:
        AsyncIterator[bytes]: An asynchronous iterator yielding JSONL lines as bytes.

    """
    errors: dict = {}
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                raw_dict = json.loads(stripped)
            except json.JSONDecodeError:
                errors.setdefault("json_decode_errors", []).append(
                    {"line": raw_line, "error": "JSONDecodeError"}
                )
                continue
            converted = safe_result_conversion([raw_dict], errors_dict=errors)
            try:
                async for item in convert_destinyworks_to_jsonl_string(
                    _as_async_batches(converted)
                ):
                    yield item
            except JSONLConversionError as json_conversion_error:
                errors.setdefault("jsonl_conversion_errors", []).append(
                    {"error": str(json_conversion_error), "raw_dict": raw_dict}
                )
        errors_populated = errors.get("json_decode_errors") or errors.get(
            "jsonl_conversion_errors"
        )
        doi_errors_found = errors.get("doi_errors", {}).get("total", 0) > 0
        if errors_populated or doi_errors_found:
            yield json.dumps({"errors": errors}).encode("utf-8")


async def _process_file_async(
    settings: Settings, file_path: str, base_blob_name: str
) -> list[str]:
    """
    Process a single file asynchronously: stream, convert, and upload to blob storage.

    Args:
        settings (Settings): The application settings containing configuration values.
        file_path (Path): The local file path of the source .gz file being processed.
        base_blob_name (str): The base blob name to use for uploaded files.

    Returns:
        list[str]: A list of blob names that were uploaded.

    """
    stream = _gz_to_jsonl_stream(Path(file_path))
    return await blob_upload_multipart(
        data=stream,
        base_filename=base_blob_name,
        batch_size=settings.BLOB_BATCH_SIZE,
    )


def process_file(file_path: str) -> dict:
    """
    Define the Airflow task entry point — runs the async pipeline synchronously.

    Args:
        file_path (str): The local file path of the source .gz file being processed.

    Returns:
        dict: A dictionary containing the original file path,
            the derived base blob name, and a list of uploaded blob names.

    """
    settings = get_settings()
    base_blob_name = _derive_base_blob_name(Path(file_path))
    blob_names = asyncio.run(_process_file_async(settings, file_path, base_blob_name))
    return {
        "file_path": file_path,
        "base_blob_name": base_blob_name,
        "blob_names": blob_names,
    }
