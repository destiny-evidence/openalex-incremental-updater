#syntax=docker/dockerfile:1.4
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=2.1.2

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gcc \
    gpg \
    git \
    openssh-client \
    python3-dev \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
      | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/microsoft.gpg] \
      https://packages.microsoft.com/repos/azure-cli/ $(. /etc/os-release && echo $VERSION_CODENAME) main" \
      > /etc/apt/sources.list.d/azure-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends azure-cli \
    && apt-get purge -y gpg && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml poetry.lock README.md /app/

COPY refresh_requester /app/refresh_requester

RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

EXPOSE 8080

CMD ["poetry", "run", "uvicorn", "refresh_requester.main:app", "--host", "0.0.0.0", "--port", "8080"]
