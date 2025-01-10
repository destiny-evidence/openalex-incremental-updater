FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.4

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    python3-dev \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml poetry.lock /app/

RUN poetry install --no-root --only main

COPY openalex_incremental_updater /app/openalex_incremental_updater

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "openalex_incremental_updater.main:app", "--host", "0.0.0.0", "--port", "8000"]
