FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.4

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    python3-dev \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

ARG GH_PAT
# Conditionally reconfigure Git to use HTTPS only if GH_PAT is passed
RUN if [ -n "$GH_PAT" ]; then \
      git config --global url."https://${GH_PAT}:x-oauth-basic@github.com/".insteadOf "git@github.com:" ; \
    else \
      echo "No GH_PAT provided. Assuming local SSH access." ; \
    fi

WORKDIR /app

ARG GH_PAT


COPY pyproject.toml poetry.lock /app/

RUN poetry install --no-root --only main

COPY openalex_incremental_updater /app/openalex_incremental_updater

EXPOSE 8000

# Cleanup of Git config if GH_PAT was set & used
RUN if [ -n "$GH_PAT" ]; then \
      git config --global --unset-all url."https://${GH_PAT}:x-oauth-basic@github.com/".insteadOf || true ; \
    fi

CMD ["poetry", "run", "uvicorn", "openalex_incremental_updater.main:app", "--host", "0.0.0.0", "--port", "8000"]
