#syntax=docker/dockerfile:1.4
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.4

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

ARG GH_PAT

WORKDIR /app

ARG GH_PAT


COPY pyproject.toml poetry.lock /app/

COPY openalex_incremental_updater /app/openalex_incremental_updater

# SSH-enabled install path for local use
RUN --mount=type=ssh \
  if [ "$USE_SSH" = "true" ]; then \
    mkdir -p -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts && \
    mkdir -p ~/.ssh && \
    --mount=type=ssh poetry bundle venv -vvv --only=main /app/.venv; \
  fi

# HTTPS fallback install path for CI use
RUN if [ "$USE_SSH" != "true" ] && [ -n "$GH_PAT" ]; then \
    git config --global url."https://${GH_PAT}:x-oauth-basic@github.com/".insteadOf "git@github.com:" ;\
  fi

RUN poetry install --no-root --only main;


EXPOSE 8000

# Cleanup of Git config if GH_PAT was set & used
RUN if [ -n "$GH_PAT" ]; then \
      git config --global --unset-all url."https://${GH_PAT}:x-oauth-basic@github.com/".insteadOf || true ; \
    fi

CMD ["poetry", "run", "uvicorn", "openalex_incremental_updater.main:app", "--host", "0.0.0.0", "--port", "8000"]
