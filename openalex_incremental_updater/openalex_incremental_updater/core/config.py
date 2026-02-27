"""Define API settings."""

import json

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Store typed settings for Pydantic."""

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "OpenAlex Incremental Updater"
    OPENALEX_API_URL: str = "https://api.openalex.org"
    OPENALEX_API_KEY: SecretStr = Field(
        ...,
        description="API key for OpenAlex API",
    )
    AZURE_AUTH_ENVIRONMENT_ID: str = Field(
        ...,
        description="Azure application ID for authentication",
    )
    APP_REGISTRATION_APP_ID: str = Field(
        ...,
        description="Azure application registration app ID",
    )
    APP_REGISTRATION_SECRET: SecretStr = Field(
        ...,
        description="Azure application registration secret",
    )
    TENANT_ID: str = Field(
        ...,
        description="Azure tenant ID for authentication",
    )
    USER_EMAIL: str = Field(
        ...,
        description="User email address sent to OpenAlex API to join the polite pool",
    )
    STORAGE_BLOB_ACCOUNT: str = Field(
        ...,
        description="Azure Storage Blob account name",
    )
    STORAGE_BLOB_CONTAINER: str = Field(
        ...,
        description="Azure Storage Blob container name",
    )
    cors_origins: list[HttpUrl] | str = Field(..., description="CORS allowed origins")
    allow_credentials: bool = True
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]
    log_level: str = "INFO"
    BLOB_BATCH_SIZE: int = 10_000

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("cors_origins", mode="before")
    def parse_cors_origins(cls, cors_origins: str | list[str]) -> list[HttpUrl]:
        """
        Parse the CORS origins from a string or list of strings.

        This handles cases where an environment variable is a JSON list or
        a comma-separated string. This can happen when reading from a .env file
        or from the environment, as users may prefer to use a JSON list in the .env
        file or a comma-separated string.

        Args:
            cors_origins (str | list[str]): The CORS origins as a string/list of strings

        Raises:
            TypeError: If the CORS origins are not a list or a string.

        Returns:
            list[HttpUrl]: The CORS origins as a list of URLs

        """
        if isinstance(cors_origins, str):
            try:
                origins = json.loads(cors_origins)
                is_listlike = isinstance(origins, list)
                if not is_listlike:
                    json_format_error = "Must be list-like or comma-separated string"
                    raise TypeError(json_format_error)
                return [url.strip() for url in origins]
            except json.JSONDecodeError:
                return [HttpUrl(url.strip()) for url in cors_origins.split(",")]
        if isinstance(cors_origins, list):
            origins = [HttpUrl(url.strip()) for url in cors_origins]
        elif not isinstance(cors_origins, list):
            invalid_type_error = "CORS_ORIGINS must be a list or a string."
            raise TypeError(invalid_type_error)
        return origins


def get_settings() -> Settings:
    """
    Return a Settings object.

    Returns
        Settings: Pydantic settings object

    """
    return Settings()
