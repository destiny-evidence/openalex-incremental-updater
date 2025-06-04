"""Define configuration settings for the app."""

from datetime import date
from http import HTTPStatus

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests import Session
from requests.adapters import HTTPAdapter, Retry


def get_retry_session() -> Session:
    """
    Return a requests session with retry settings enabled.

    Returns:
        requests.Session: A requests session with retry settings enabled.

    """
    settings = get_settings()
    session = Session()
    retries = Retry(
        total=settings.retry_total,
        backoff_factor=settings.retry_backoff_factor,
        status_forcelist=settings.retry_status_list,
    )

    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


class Settings(BaseSettings):
    """Store typed settings for Pydantic."""

    API_ENDPOINT: HttpUrl = Field(
        ...,
        description="The endpoint for the OpenAlex Incremental Ingestion API",
    )
    STORAGE_BLOB_ACCOUNT: str = Field(
        ...,
        description="The account for the Azure Storage Blob",
    )
    STORAGE_BLOB_CONTAINER: str = Field(
        ...,
        description="The container for the Azure Storage Blob",
    )
    STORAGE_BLOB_ACCOUNT_KEY: SecretStr = Field(
        ...,
        description="The account key for the Azure Storage Blob",
    )
    TOKEN_ENDPOINT: HttpUrl = Field(
        ...,
        description="The endpoint for Destiny Repository API token requests",
    )
    limit: int | None = None
    fetch_date: date | None = None
    retry_total: int = 3
    retry_backoff_factor: float = 0.3
    # See https://docs.python.org/3/library/http.html#http-status-codes
    retry_status_list: list[int] = [
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    ]
    request_timeout: int = 5 * 60
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    """
    Return a Settings object.

    Returns
        Settings: Pydantic settings object

    """
    return Settings()
