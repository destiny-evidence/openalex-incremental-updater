#syntax=docker/dockerfile:1.4
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=2.1.2

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    git \
    openssh-client \
    libpq-dev \
    python3-dev \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml poetry.lock README.md /app/

COPY openalex_incremental_updater /app/openalex_incremental_updater

RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

CMD ["poetry", "run", "uvicorn", "openalex_incremental_updater.main:app", "--host", "0.0.0.0", "--port", "8000"]
