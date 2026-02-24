"""Configuration settings for the Snapshot Bulk Feeder."""

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pydantic settings loaded from environment variables."""

    BATCH_DIR: str = Field(
        ...,
        description="Mount path containing batch files, manifest.json, and state.json.",
    )
    WINDOW_SIZE: int = Field(
        10,
        ge=1,
        description="Initial max concurrent batches in the DR pipeline.",
    )
    POLL_INTERVAL_SECONDS: int = Field(
        300,
        ge=10,
        description="Initial seconds between poll cycles.",
    )

    STORAGE_BLOB_ACCOUNT: str = Field(
        ..., description="Azure Blob Storage account name."
    )
    STORAGE_BLOB_CONTAINER: str = Field(
        ..., description="Azure Blob Storage container name."
    )
    STORAGE_BLOB_ACCOUNT_KEY: SecretStr = Field(
        ..., description="Azure Blob Storage account key for SAS generation."
    )
    STORAGE_BLOB_ENDPOINT: str | None = Field(
        default=None,
        description="Custom blob endpoint URL (e.g. http://127.0.0.1:10000/devstoreaccount1 for Azurite).",
    )
    BLOB_PREFIX: str = Field(
        "snapshot_bulk/",
        description="Blob name prefix in the container.",
    )
    SAS_TOKEN_EXPIRY_HOURS: int = Field(
        168,
        description="SAS token lifetime in hours (default 7 days).",
    )

    REPOSITORY_ENDPOINT: HttpUrl = Field(
        ..., description="Destiny Repository API base URL."
    )
    TOKEN_ENDPOINT: HttpUrl | None = Field(
        default=None,
        description="Auth token endpoint URL.  Omit to skip token refresh (local dev with auth bypass).",
    )

    PROCESSOR_NAME: str = Field(
        "OpenAlex Snapshot Bulk Feeder",
        description="ImportRecord processor_name metadata.",
    )
    PROCESSOR_VERSION: str = Field(
        "1.0.0",
        description="ImportRecord processor_version metadata.",
    )
    SOURCE_NAME: str = Field(
        "openalex-snapshot",
        description="ImportRecord source_name metadata.",
    )

    DECOMPRESS_ON_UPLOAD: bool = Field(
        default=False,
        description="Decompress .gz files before uploading to blob storage.",
    )
    TEST_RECORD_LIMIT: int | None = Field(
        default=None,
        ge=1,
        description="Truncate each batch to this many records before upload (testing only).",
    )
    LOG_LEVEL: str = Field("INFO", description="Log level.")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    """Return a Settings instance from the environment."""
    return Settings()
