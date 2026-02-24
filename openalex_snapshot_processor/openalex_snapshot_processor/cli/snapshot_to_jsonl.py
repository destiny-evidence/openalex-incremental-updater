r"""
Convert OpenAlex JSON snapshots to gzip-compressed JSONL batches.

Produces ReferenceFileInput JSONL files for bulk upload by the
snapshot-processor feeder. Each batch is self-contained,
gzip-compressed, and sequentially numbered for easy enumeration.

Output structure::

    output_dir/
    ├── batch_00001.jsonl.gz   (100 K records each, ~25 MB gzipped)
    ├── batch_00002.jsonl.gz
    ├── ...
    └── manifest.json          (totals + per-batch record counts)

Usage::

    # Full production run (~2-3 hours with 4 workers)
    uv run python -m openalex_snapshot_processor.cli.snapshot_to_jsonl \
        --input /Volumes/4TBSSD/.../works-full-2026-02/ \
        --output /Volumes/4TBSSD/destiny-data/jsonl-batches \
        --workers 4

    # Quick test (2 files, 1000 records max)
    uv run python -m openalex_snapshot_processor.cli.snapshot_to_jsonl \
        --input .data/sources/openalex/works-full-2026-02 \
        --output /tmp/jsonl-test \
        --limit-files 2 --limit 1000 --workers 2
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path

import orjson

from .openalex_transforms import openalex_to_reference_file_input

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 100_000  # Records per batch file

_MAX_LOGGED_FAILURES = 10  # Cap per-worker failure log messages to avoid flooding

_PROGRESS_LOG_INTERVAL = 50_000  # Log progress every N records within a worker


# ---------------------------------------------------------------------------
# File utilities (inlined — too small for a separate module)
# ---------------------------------------------------------------------------


def _find_gz_files(input_dir: Path) -> list[Path]:
    """Find all .gz files in *input_dir* recursively, sorted."""
    gz_files = [
        Path(root) / file
        for root, _, files in os.walk(input_dir)
        for file in files
        if file.endswith(".gz")
    ]
    return sorted(gz_files)


def _distribute_files(files: list[Path], num_workers: int) -> list[list[Path]]:
    """Distribute *files* among *num_workers* using round-robin."""
    if num_workers <= 0:
        msg = "num_workers must be positive"
        raise ValueError(msg)

    chunks: list[list[Path]] = [[] for _ in range(num_workers)]
    for i, f in enumerate(files):
        chunks[i % num_workers].append(f)
    return chunks


# ---------------------------------------------------------------------------
# Worker dataclasses
# ---------------------------------------------------------------------------


@dataclass
class WorkerArgs:
    """Arguments passed to each worker process."""

    worker_id: int
    gz_files: list[Path]
    output_dir: Path
    batch_size: int
    limit: int | None


@dataclass
class WorkerResult:
    """Aggregated result from a single worker."""

    worker_id: int
    records_processed: int
    records_written: int
    records_skipped: int
    records_failed: int
    batches_written: int
    files_processed: int
    gz_errors: int
    error: str | None = None
    batch_record_counts: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def write_batch(
    batch: list[str],
    batch_num: int,
    worker_dir: Path,
) -> Path:
    """Write a list of JSONL strings to a gzip-compressed batch file."""
    path = worker_dir / f"batch_{batch_num:05d}.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as f:
        for line in batch:
            f.write(line)
            f.write("\n")
    return path


def process_gz_file(  # noqa: PLR0913
    gz_path: Path,
    batch: list[str],
    batch_num: int,
    worker_dir: Path,
    batch_size: int,
    limit: int | None,
    total_written: int,
    *,
    worker_id: int,
) -> tuple[list[str], int, int, int, int, int, list[int]]:
    """
    Stream one .gz file, accumulate records, and flush full batches.

    Returns:
        (batch, batch_num, processed, written, skipped, failed, batch_counts)

    """
    processed = 0
    written = 0
    skipped = 0
    failed = 0
    logged_failures = 0
    batch_counts: list[int] = []

    try:
        with gzip.open(gz_path, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                if limit is not None and (total_written + written) >= limit:
                    break

                processed += 1

                try:
                    work = orjson.loads(line)
                    ref = openalex_to_reference_file_input(work)

                    if ref is None:
                        skipped += 1
                        continue

                    batch.append(ref.model_dump_json())
                    written += 1

                    if len(batch) >= batch_size:
                        batch_num += 1
                        write_batch(batch, batch_num, worker_dir)
                        batch_counts.append(len(batch))
                        batch = []

                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    if logged_failures < _MAX_LOGGED_FAILURES:
                        logger.warning(
                            "Worker %d: failed to transform record: %s",
                            worker_id,
                            exc,
                        )
                        logged_failures += 1

                if processed % _PROGRESS_LOG_INTERVAL == 0:
                    logger.info(
                        "Worker %d: %s processed, %s written so far in %s",
                        worker_id,
                        f"{processed:,}",
                        f"{total_written + written:,}",
                        gz_path.name,
                    )

    except (gzip.BadGzipFile, OSError, EOFError) as exc:
        logger.warning(
            "Worker %d: skipping corrupted file %s: %s",
            worker_id,
            gz_path,
            exc,
        )
        return batch, batch_num, processed, written, skipped, failed + 1, batch_counts

    return batch, batch_num, processed, written, skipped, failed, batch_counts


def worker_process(args: WorkerArgs) -> WorkerResult:
    """Process a chunk of .gz files in a single worker."""
    worker_dir = args.output_dir / "tmp" / f"w{args.worker_id}"
    worker_dir.mkdir(parents=True, exist_ok=True)

    batch: list[str] = []
    batch_num = 0
    total_processed = 0
    total_written = 0
    total_skipped = 0
    total_failed = 0
    files_processed = 0
    gz_errors = 0
    all_batch_counts: list[int] = []

    try:
        for gz_path in args.gz_files:
            if args.limit is not None and total_written >= args.limit:
                break

            (
                batch,
                batch_num,
                processed,
                written,
                skipped,
                failed,
                batch_counts,
            ) = process_gz_file(
                gz_path=gz_path,
                batch=batch,
                batch_num=batch_num,
                worker_dir=worker_dir,
                batch_size=args.batch_size,
                limit=args.limit,
                total_written=total_written,
                worker_id=args.worker_id,
            )
            total_processed += processed
            total_written += written
            total_skipped += skipped
            total_failed += failed
            all_batch_counts.extend(batch_counts)

            if processed == 0 and failed > 0:
                gz_errors += 1
            else:
                files_processed += 1

        # Flush remaining records as final batch
        if batch:
            batch_num += 1
            write_batch(batch, batch_num, worker_dir)
            all_batch_counts.append(len(batch))

    except Exception as exc:
        logger.exception("Worker %d: fatal error", args.worker_id)
        return WorkerResult(
            worker_id=args.worker_id,
            records_processed=total_processed,
            records_written=total_written,
            records_skipped=total_skipped,
            records_failed=total_failed,
            batches_written=batch_num,
            files_processed=files_processed,
            gz_errors=gz_errors,
            error=str(exc),
            batch_record_counts=all_batch_counts,
        )

    return WorkerResult(
        worker_id=args.worker_id,
        records_processed=total_processed,
        records_written=total_written,
        records_skipped=total_skipped,
        records_failed=total_failed,
        batches_written=batch_num,
        files_processed=files_processed,
        gz_errors=gz_errors,
        batch_record_counts=all_batch_counts,
    )


# ---------------------------------------------------------------------------
# Output finalisation
# ---------------------------------------------------------------------------


def rename_worker_batches(output_dir: Path) -> list[tuple[str, int]]:
    """
    Rename per-worker batch files to sequential global numbering.

    Scans ``tmp/w*/batch_*.jsonl.gz`` sorted by (worker_id, batch_num),
    renames each to ``output_dir/batch_00001.jsonl.gz``, and removes ``tmp/``.
    """
    tmp_dir = output_dir / "tmp"
    if not tmp_dir.exists():
        return []

    worker_batches: list[Path] = []
    worker_dirs = sorted(tmp_dir.iterdir())
    for wd in worker_dirs:
        if wd.is_dir() and wd.name.startswith("w"):
            batches = sorted(wd.glob("batch_*.jsonl.gz"))
            worker_batches.extend(batches)

    renamed: list[str] = []
    for i, src in enumerate(worker_batches, start=1):
        dst_name = f"batch_{i:05d}.jsonl.gz"
        dst = output_dir / dst_name
        src.rename(dst)
        renamed.append(dst_name)

    shutil.rmtree(tmp_dir)
    return [(name, 0) for name in renamed]


def write_manifest(
    output_dir: Path,
    results: list[WorkerResult],
    batch_filenames: list[str],
    batch_record_counts: list[int],
    duration_seconds: float,
) -> Path:
    """Write ``manifest.json`` with totals and per-batch record counts."""
    total_processed = sum(r.records_processed for r in results)
    total_written = sum(r.records_written for r in results)
    total_skipped = sum(r.records_skipped for r in results)
    total_failed = sum(r.records_failed for r in results)
    total_gz_errors = sum(r.gz_errors for r in results)
    total_files = sum(r.files_processed for r in results)

    batches = [
        {"file": filename, "records": count}
        for filename, count in zip(batch_filenames, batch_record_counts, strict=False)
    ]

    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "duration_seconds": round(duration_seconds, 1),
        "totals": {
            "records_processed": total_processed,
            "records_written": total_written,
            "records_skipped": total_skipped,
            "records_failed": total_failed,
            "gz_files_processed": total_files,
            "gz_files_corrupted": total_gz_errors,
            "batch_files": len(batches),
        },
        "batches": batches,
    }

    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w") as f:
        json.dump(manifest, f, indent=2)
    return manifest_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert OpenAlex JSON snapshots to gzip-compressed JSONL batches",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        help="Input directory containing OpenAlex JSON .gz files",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output directory for batch files and manifest",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=max(1, (cpu_count() or 2) - 1),
        help="Number of worker processes (default: CPU count - 1)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Records per batch file (default: {DEFAULT_BATCH_SIZE:,})",
    )
    parser.add_argument(
        "--limit-files",
        type=int,
        default=None,
        help="Only process first N .gz files (for testing)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap total records written across all workers (for testing)",
    )
    return parser.parse_args()


def _run_workers(
    worker_args: list[WorkerArgs],
    num_workers: int,
) -> list[WorkerResult]:
    """Run worker pool and return results."""
    if num_workers == 1:
        return [worker_process(worker_args[0])]

    with Pool(processes=num_workers) as pool:
        return pool.map(worker_process, worker_args)


def _finalize_output(
    output_dir: Path,
    results: list[WorkerResult],
    duration: float,
) -> list[str]:
    """Rename batches, write manifest, and return filenames."""
    for r in results:
        status = f" (ERROR: {r.error})" if r.error else ""
        logger.info(
            "Worker %d: %s written from %d files, %d batches%s",
            r.worker_id,
            f"{r.records_written:,}",
            r.files_processed,
            r.batches_written,
            status,
        )

    logger.info("Renaming worker batches to sequential numbering...")
    renamed = rename_worker_batches(output_dir)
    batch_filenames = [name for name, _ in renamed]

    all_batch_counts: list[int] = []
    for r in results:
        all_batch_counts.extend(r.batch_record_counts)

    write_manifest(output_dir, results, batch_filenames, all_batch_counts, duration)
    return batch_filenames


def _print_summary(
    results: list[WorkerResult],
    batch_filenames: list[str],
    output_dir: Path,
    duration: float,
) -> None:
    """Log final summary statistics."""
    total_written = sum(r.records_written for r in results)
    total_processed = sum(r.records_processed for r in results)
    total_skipped = sum(r.records_skipped for r in results)
    total_failed = sum(r.records_failed for r in results)

    logger.info("=" * 60)
    logger.info("COMPLETE")
    logger.info("=" * 60)
    logger.info("Duration: %.1f seconds (%.1f minutes)", duration, duration / 60)
    logger.info("Files processed: %d", sum(r.files_processed for r in results))
    logger.info("Records processed: %s", f"{total_processed:,}")
    logger.info("Records written: %s", f"{total_written:,}")
    logger.info("Records skipped: %s", f"{total_skipped:,}")
    logger.info("Records failed: %s", f"{total_failed:,}")
    logger.info("Batch files: %d", len(batch_filenames))
    if duration > 0:
        logger.info("Throughput: %.0f records/sec", total_written / duration)
    logger.info("Output: %s", output_dir)
    logger.info("Manifest: %s", output_dir / "manifest.json")


def main() -> None:
    """Convert OpenAlex snapshots to gzip-compressed JSONL batches."""
    args = _parse_args()

    input_dir = args.input.expanduser().resolve()
    output_dir = args.output.expanduser().resolve()

    if not input_dir.exists():
        logger.error("Input directory does not exist: %s", input_dir)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Discover .gz files
    gz_files = _find_gz_files(input_dir)
    if not gz_files:
        logger.error("No .gz files found in %s", input_dir)
        return

    if args.limit_files:
        gz_files = gz_files[: args.limit_files]

    logger.info("Found %d .gz files to process", len(gz_files))

    per_worker_limit = args.limit

    num_workers = min(args.workers, len(gz_files))
    logger.info(
        "Using %d workers, batch size %s",
        num_workers,
        f"{args.batch_size:,}",
    )
    if per_worker_limit:
        logger.info("Record limit: %s per worker", f"{per_worker_limit:,}")

    file_chunks = _distribute_files(gz_files, num_workers)
    worker_args = [
        WorkerArgs(
            worker_id=i,
            gz_files=chunk,
            output_dir=output_dir,
            batch_size=args.batch_size,
            limit=per_worker_limit,
        )
        for i, chunk in enumerate(file_chunks)
        if chunk
    ]

    start_time = time.time()
    results = _run_workers(worker_args, num_workers)
    duration = time.time() - start_time

    batch_filenames = _finalize_output(output_dir, results, duration)
    _print_summary(results, batch_filenames, output_dir, duration)


if __name__ == "__main__":
    main()
