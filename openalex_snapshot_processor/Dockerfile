FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

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
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/microsoft.gpg] \
      https://packages.microsoft.com/repos/azure-cli/ $(. /etc/os-release && echo $VERSION_CODENAME) main" \
      > /etc/apt/sources.list.d/azure-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends azure-cli \
    && apt-get purge -y gpg && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
# Run uv installer and remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin:$PATH"



COPY openalex_incremental_updater /opt/packages/openalex_incremental_updater
COPY refresh_requester /opt/packages/refresh_requester
COPY openalex_snapshot_processor /opt/packages/openalex_snapshot_processor

WORKDIR /opt/packages/openalex_snapshot_processor

RUN uv sync --locked

RUN chmod +x /opt/packages/openalex_snapshot_processor/register_deployments.sh
ENTRYPOINT ["/opt/packages/openalex_snapshot_processor/register_deployments.sh"]
