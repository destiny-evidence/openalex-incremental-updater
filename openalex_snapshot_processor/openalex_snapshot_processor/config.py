"""Define configuration settings."""

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Define configuration settings for the app."""

    SNAPSHOT_ROOT: str = Field(
        ...,
        description=(
            "Absolute path to the local directory where OpenAlex snapshot files are stored."
        ),
    )

    BLOB_BATCH_SIZE: int = Field(
        10_000,
        description=(
            "The number of records to include in each batch when sending data to the Destiny Repository API."
        ),
    )
    STORAGE_BLOB_ACCOUNT: str = Field(
        ...,
        description=(
            "The name of the Azure Blob Storage account where OpenAlex snapshot files are stored."
        ),
    )
    STORAGE_BLOB_CONTAINER: str = Field(
        ...,
        description=(
            "The name of the Azure Blob Storage container where OpenAlex snapshot files are stored."
        ),
    )
    STORAGE_BLOB_ACCOUNT_KEY: SecretStr = Field(
        ...,
        description=(
            "The access key for the Azure Blob Storage account where OpenAlex snapshot files are stored."
        ),
    )

    REPOSITORY_ENDPOINT: HttpUrl = Field(
        ...,
        description=(
            "The base URL of the Destiny Repository API endpoint to send data for ingest."
        ),
    )
    TOKEN_ENDPOINT: HttpUrl = Field(
        ...,
        description=(
            "The URL of the token endpoint for Azure AD authentication to get"
            " an access token for the Destiny Repository API."
        ),
    )
    APP_REGISTRATION_APP_ID: str = Field(
        ...,
        description=(
            "The application (client) ID of the Azure AD app registration used"
            " for authentication when sending data to the Destiny Repository API."
        ),
    )

    APP_REGISTRATION_SECRET: SecretStr = Field(
        ...,
        description=(
            "The client secret of the Azure AD app registration used"
            " for authentication when sending data to the Destiny Repository API."
        ),
    )

    TENANT_ID: str = Field(..., description=("Azure tenant ID for authentication."))

    API_ENDPOINT: HttpUrl = Field(
        default=HttpUrl("http://example.com/api"),
        description=("Unused, placeholder for another settings object."),
    )
    OPENALEX_API_KEY: SecretStr = Field(
        default=SecretStr("unused"),
        description=("Unused, placeholder for another settings object."),
    )
    USER_EMAIL: str = Field(
        default="unused",
        description=("Unused, placeholder for another settings object."),
    )
    CORS_ORIGINS: str = Field(
        default='["http://localhost:3000"]',
        description=("Unused, placeholder for another settings object."),
    )
    AZURE_AUTH_ENVIRONMENT_ID: str = Field(
        default="unused",
        description=("Unused, placeholder for another settings object."),
    )
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    """Get the (cached) settings for the app."""
    return Settings()
