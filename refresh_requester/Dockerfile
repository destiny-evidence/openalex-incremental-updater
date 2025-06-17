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
    python3-dev \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

ARG GH_PAT
ARG USE_SSH=false
ENV USE_SSH=${USE_SSH}
WORKDIR /app

COPY pyproject.toml poetry.lock README.md /app/

COPY refresh_requester /app/refresh_requester

ENV POETRY_SYSTEM_GIT_CLIENT=true

# SSH-enabled install path for local use
RUN --mount=type=ssh \
  if [ "$USE_SSH" = "true" ]; then \
    mkdir -p -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi; \
  fi

# HTTPS fallback install path for CI use
RUN if [ "$USE_SSH" != "true" ] && [ -n "$GH_PAT" ]; then \
    git config --global url."https//${GH_PAT}:x-oauth-basic@github.com/".insteadOf "git@github.com:" && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi; \
  fi

# Cleanup of Git config if GH_PAT was set & used
RUN if [ -n "$GH_PAT" ]; then \
      git config --global --unset-all url."https://${GH_PAT}:x-oauth-basic@github.com/".insteadOf || true ; \
    fi

CMD ["python", "refresh_requester/main.py"]
