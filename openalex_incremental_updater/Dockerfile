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

ARG USE_SSH=false
ENV USE_SSH=${USE_SSH}

WORKDIR /app

COPY pyproject.toml poetry.lock README.md /app/

COPY openalex_incremental_updater /app/openalex_incremental_updater

ENV POETRY_SYSTEM_GIT_CLIENT=true


# SSH-enabled install path for local use
RUN --mount=type=ssh \
  if [ "$USE_SSH" = "true" ]; then \
    mkdir -p -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi; \
  fi

# HTTPS fallback install path for CI use using BuildKit secrets
RUN --mount=type=secret,id=gh_pat \
  if [ "$USE_SSH" != "true" ] && [ -f /run/secrets/gh_pat ]; then \
    GH_PAT=$(cat /run/secrets/gh_pat) && \
    cp pyproject.toml pyproject.toml.bak && \
    sed "s|git@github.com:|https://${GH_PAT}@github.com/|g" pyproject.toml.bak > pyproject.toml && \
    poetry lock && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi && \
    mv pyproject.toml.bak pyproject.toml; \
  fi


CMD ["poetry", "run", "uvicorn", "openalex_incremental_updater.main:app", "--host", "0.0.0.0", "--port", "8000"]
