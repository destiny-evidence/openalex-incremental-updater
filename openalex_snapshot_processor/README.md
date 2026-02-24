# OpenAlex Snapshot Processor

Containerised feeder that pushes pre-processed OpenAlex snapshot batches into destiny-repository (DR). Designed to run unattended for days/weeks, with operator controls for pause, resume, and cancellation.

## How it works

1. On startup, reads a `manifest.json` from `BATCH_DIR` listing all `.jsonl.gz` batch files
2. Creates (or resumes) an ImportRecord in DR
3. Runs a sliding-window loop with **completion-gated backpressure**:
   - On cold start, submits only 1 batch (proves DR can handle it)
   - As batches complete, the window opens: `effective_window = min(window_size, completed + 1)`
   - Max 1 submission per poll cycle (spaces submissions across intervals)
   - Uploads batch files to Azure Blob Storage
   - Registers each batch with DR via SAS URL
   - Polls DR for batch completion
   - Persists progress to `state.json` after every cycle
4. Once all batches reach a terminal state (completed/failed), finalises the ImportRecord

The feeder resumes from `state.json` on restart, reconciling in-progress batches with DR.

## API endpoints

| Method   | Path                        | Description                                                  |
| -------- | --------------------------- | ------------------------------------------------------------ |
| `GET`    | `/health`                   | Liveness probe                                               |
| `GET`    | `/status`                   | Progress, throughput, ETA, failed batches                    |
| `PATCH`  | `/settings`                 | Adjust `window_size` and `poll_interval_seconds` at runtime  |
| `POST`   | `/batches/{filename}/retry` | Reset a failed batch to pending                              |
| `POST`   | `/pause`                    | Pause the feeder loop (keeps app alive for `/status`)        |
| `POST`   | `/resume`                   | Resume a paused feeder loop                                  |
| `DELETE` | `/import`                   | Cancel import: archive state and reset for resumable restart |

### Pause / Resume

Pausing stops the feeder from submitting new batches or polling DR. The app stays alive so `/status` remains accessible. Useful during DR maintenance windows.

- `POST /pause` returns `409` if already paused
- `POST /resume` returns `409` if not paused
- Both return `503` if the feeder isn't running

### Cancel import (resumable)

`DELETE /import` stops the feeder loop and prepares the state for a clean restart:

1. Archives the current `state.json` to `state.cancelled.<timestamp>.json` (audit trail)
2. Writes a new `state.json` that preserves completed batches and resets everything else to `PENDING`
3. Clears `import_record_id` so the next startup creates a fresh ImportRecord in DR

Returns a summary:

```json
{ "cancelled_batches": 4794, "completed": 2, "pending": 4794 }
```

On the next restart, the feeder loads the reset state, skips already-completed batches, and picks up the remaining work automatically — no manual cleanup required.

Archive files accumulate in `BATCH_DIR` and can be safely deleted once reviewed:

```text
BATCH_DIR/
├── state.json                              ← current (reset) state
├── state.cancelled.20260224T143000Z.json   ← archived from cancellation
├── manifest.json
└── batch_*.jsonl.gz
```

## Configuration

All configuration is via environment variables (or `.env` file):

| Variable                   | Required | Default                         | Description                                                                    |
| -------------------------- | -------- | ------------------------------- | ------------------------------------------------------------------------------ |
| `BATCH_DIR`                | yes      | —                               | Path to directory containing batch files and `manifest.json`                   |
| `WINDOW_SIZE`              | no       | `10`                            | Max concurrent batches in the DR pipeline                                      |
| `POLL_INTERVAL_SECONDS`    | no       | `300`                           | Seconds between poll cycles                                                    |
| `STORAGE_BLOB_ACCOUNT`     | yes      | —                               | Azure Blob Storage account name                                                |
| `STORAGE_BLOB_CONTAINER`   | yes      | —                               | Azure Blob Storage container name                                              |
| `STORAGE_BLOB_ACCOUNT_KEY` | yes      | —                               | Azure Blob Storage account key                                                 |
| `STORAGE_BLOB_ENDPOINT`    | no       | —                               | Custom blob endpoint (e.g. Azurite: `http://127.0.0.1:10000/devstoreaccount1`) |
| `BLOB_PREFIX`              | no       | `snapshot_bulk/`                | Blob name prefix in the container                                              |
| `SAS_TOKEN_EXPIRY_HOURS`   | no       | `168`                           | SAS token lifetime (default 7 days)                                            |
| `REPOSITORY_ENDPOINT`      | yes      | —                               | DR API base URL (include `/v1` if versioned)                                   |
| `TOKEN_ENDPOINT`           | no       | —                               | Auth token endpoint. Omit for local dev (auth bypass)                          |
| `PROCESSOR_NAME`           | no       | `OpenAlex Snapshot Bulk Feeder` | ImportRecord metadata                                                          |
| `PROCESSOR_VERSION`        | no       | `1.0.0`                         | ImportRecord metadata                                                          |
| `SOURCE_NAME`              | no       | `openalex-snapshot`             | ImportRecord metadata                                                          |
| `DECOMPRESS_ON_UPLOAD`     | no       | `false`                         | Decompress `.gz` before uploading to blob                                      |
| `TEST_RECORD_LIMIT`        | no       | —                               | Truncate each batch to N records before upload (testing only)                  |
| `LOG_LEVEL`                | no       | `INFO`                          | Log level                                                                      |

## CLI: snapshot-to-JSONL transformer

The package includes a CLI that converts raw OpenAlex JSON `.gz` snapshot files into the gzip-compressed JSONL batches the feeder uploads. This makes the snapshot processor self-contained — one package to transform **and** upload.

```bash
# Full production run (~2-3 hours with 4 workers)
uv run python -m openalex_snapshot_processor.cli.snapshot_to_jsonl \
    --input /path/to/openalex/works-full-2026-02/ \
    --output /path/to/jsonl-batches \
    --workers 4

# Quick test (2 files, 1000 records max)
uv run python -m openalex_snapshot_processor.cli.snapshot_to_jsonl \
    --input .data/sources/openalex/works-full-2026-02 \
    --output /tmp/jsonl-test \
    --limit-files 2 --limit 1000 --workers 2
```

Options:

| Flag              | Default       | Description                                        |
| ----------------- | ------------- | -------------------------------------------------- |
| `--input`, `-i`   | _(required)_  | Directory containing OpenAlex JSON `.gz` files     |
| `--output`, `-o`  | _(required)_  | Output directory for batch files and manifest      |
| `--workers`, `-w` | CPU count - 1 | Number of worker processes                         |
| `--batch-size`    | `100,000`     | Records per batch file                             |
| `--limit-files`   | _(none)_      | Only process first N `.gz` files (for testing)     |
| `--limit`         | _(none)_      | Cap total records written per worker (for testing) |

Output structure:

```text
output_dir/
├── batch_00001.jsonl.gz   (100K records each, ~25 MB gzipped)
├── batch_00002.jsonl.gz
├── ...
└── manifest.json          (totals + per-batch record counts)
```

## Production deployment

### Container setup

The feeder is designed to run as a single long-lived container. `BATCH_DIR` must be a persistent volume — it holds the batch files, `manifest.json`, and `state.json`. If the volume is ephemeral, state is lost on restart and all batches are re-submitted.

```bash
docker run -d \
  --name snapshot-feeder \
  -v /mnt/data/jsonl-batches:/data/batches \
  -e BATCH_DIR=/data/batches \
  -e WINDOW_SIZE=10 \
  -e POLL_INTERVAL_SECONDS=300 \
  -e STORAGE_BLOB_ACCOUNT=prodaccount \
  -e STORAGE_BLOB_CONTAINER=snapshot-bulk \
  -e STORAGE_BLOB_ACCOUNT_KEY="$BLOB_KEY" \
  -e REPOSITORY_ENDPOINT=https://dr.example.com/v1 \
  -e TOKEN_ENDPOINT=https://auth.example.com/token \
  -p 8888:8000 \
  snapshot-feeder:latest
```

### Cancel and restart workflow

For a typical cancel-and-restart (e.g. DR schema migration, bad batch data, config change):

```bash
# 1. Cancel — archives state, resets non-completed batches to PENDING
curl -X DELETE http://localhost:8888/import

# 2. Restart the container (or redeploy with new config)
docker restart snapshot-feeder

# 3. Feeder loads reset state, creates a fresh ImportRecord, resumes from where it left off
curl http://localhost:8888/status
```

Completed batches are preserved across cancel+restart cycles, so a 50%-done import doesn't start from scratch.

### Tuning

- **`WINDOW_SIZE`**: Controls DR pipeline concurrency. The feeder ramps up gradually from 1 to `WINDOW_SIZE` as batches complete (completion-gated backpressure). Start at 5-10 and adjust based on DR worker count. Adjustable at runtime via `PATCH /settings`.
- **`POLL_INTERVAL_SECONDS`**: How often the feeder checks DR for batch completion. Also controls submission rate (max 1 batch per interval). 300s (5 min) is reasonable for large batches; lower for smaller batches or during testing.
- **`SAS_TOKEN_EXPIRY_HOURS`**: Default 168h (7 days). Increase if batches take longer to process in DR, otherwise DR will get a 403 when reading the blob.
- **`TEST_RECORD_LIMIT`**: Set to e.g. `10000` to truncate each 100K batch to 10K records on upload. Useful for testing the full pipeline end-to-end without waiting hours per batch.

### Monitoring

- **`GET /status`** returns throughput (`batches/hour`), ETA, failed batch list, pause state, and `effective_window` (current ramp-up limit vs configured `window_size`). Poll this from your monitoring stack.
- **`GET /health`** is a liveness probe — returns `200` as long as the FastAPI process is alive.
- The feeder logs every state transition (batch submitted, completed, failed) at INFO level. Ship logs to your aggregator for alerting on failures.

### Failure handling

- Individual batch failures do not stop the feeder. Failed batches are skipped and reported in `/status`.
- DR's `partially_failed` status is treated as failed (e.g. when a few records in a batch have bad JSON).
- Use `POST /batches/{filename}/retry` to retry specific failed batches without restarting.
- If many batches fail, `DELETE /import` + restart is cleaner than retrying individually.
- In-progress batches are reconciled with DR on restart — if DR already completed a batch, the feeder marks it completed locally.

## Local development

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency management
- DR running locally (e.g. `http://localhost:8000/v1`)
- Azurite for blob storage (e.g. via Docker on port 10000)
- Pre-processed batch files with `manifest.json` (generated by the CLI above, or from `openalex-bulk-ingest`)

### Running

```bash
cd openalex_snapshot_processor
uv sync

# Start the app (using Azurite well-known credentials)
BATCH_DIR=/path/to/jsonl-batches \
WINDOW_SIZE=2 \
POLL_INTERVAL_SECONDS=10 \
STORAGE_BLOB_ACCOUNT=devstoreaccount1 \
STORAGE_BLOB_CONTAINER=snapshot-bulk \
STORAGE_BLOB_ACCOUNT_KEY="$AZURITE_ACCOUNT_KEY" \
STORAGE_BLOB_ENDPOINT='http://127.0.0.1:10000/devstoreaccount1' \
REPOSITORY_ENDPOINT='http://localhost:8000/v1' \
uv run uvicorn openalex_snapshot_processor.main:app --port 8888
```

### Tests

```bash
uv run pytest
```

### Linting

```bash
pre-commit run --all-files
```

## Project structure

```text
openalex_snapshot_processor/
  __init__.py
  main.py              — FastAPI app, lifespan, endpoints
  feeder.py            — Core async feeder loop (sliding window, pause/resume)
  models.py            — Pydantic models for state, API requests/responses
  state.py             — state.json and manifest.json persistence
  config.py            — Settings from environment variables
  blob_client.py       — Azure Blob Storage upload and SAS URL generation
  dr_client.py         — Destiny Repository API client (import records, batches)
  cli/
    __init__.py
    openalex_transforms.py — OpenAlex → DESTINY transform pipeline
    snapshot_to_jsonl.py   — CLI: convert snapshots to JSONL batches
tests/
  test_main.py         — Endpoint tests
  test_feeder.py       — Feeder loop tests
  test_models.py       — Model validation tests
  test_state.py        — State persistence tests
  test_blob_client.py
  test_dr_client.py
  test_config.py
```
