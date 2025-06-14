# syntax=docker/dockerfile:1.4
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.4

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
# Conditionally reconfigure Git to use HTTPS only if GH_PAT is passed
RUN if [ -n "$GH_PAT" ]; then \
      git config --global url."https://${GH_PAT}:x-oauth-basic@github.com/".insteadOf "git@github.com:" ; \
    else \
      echo "No GH_PAT provided. Assuming local SSH access." ; \
    fi

WORKDIR /app

COPY pyproject.toml poetry.lock README.md /app/

COPY refresh_requester /app/refresh_requester


# SSH-enabled install path for local use
RUN --mount=type=ssh \
  if [ "$USE_SSH" = "true" ]; then \
    # Add GitHub's SSH key to known_hosts to avoid host verification issues
    # See https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints
    RUN mkdir -p ~/.ssh && echo \
    "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl" \
    >> ~/.ssh/known_hosts && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi; \
  fi

# HTTPS fallback install path for CI use
RUN if [ "$USE_SSH" != "true" ] && [ -n "$GH_PAT" ]; then \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi; \
  fi

# Cleanup of Git config if GH_PAT was set & used
RUN if [ -n "$GH_PAT" ]; then \
      git config --global --unset-all url."https://${GH_PAT}:x-oauth-basic@github.com/".insteadOf || true ; \
    fi

CMD ["python", "refresh_requester/main.py"]
