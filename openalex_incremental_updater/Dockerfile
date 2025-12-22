#syntax=docker/dockerfile:1.4
FROM python:3.13-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/root/.local/bin:$PATH"

# Build stage - install build dependencies
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh

WORKDIR /app

# Copy only dependency files first for better caching
COPY pyproject.toml uv.lock README.md /app/

# Install dependencies (this layer gets cached unless dependencies change)
RUN uv sync --locked --no-dev

# Runtime stage - minimal runtime dependencies
FROM base AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libpq5 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy uv from builder
COPY --from=builder /root/.local /root/.local

# Copy installed dependencies from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code (this layer changes frequently)
COPY openalex_incremental_updater /app/openalex_incremental_updater
COPY pyproject.toml README.md /app/

CMD ["uv", "run", "uvicorn", "openalex_incremental_updater.main:app", "--host", "0.0.0.0", "--port", "8000"]
