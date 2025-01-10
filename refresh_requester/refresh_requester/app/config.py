"""Define configuration settings for the app."""

from fastapi import status
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Store typed settings for Pydantic."""

    API_ENDPOINT: str = Field(
        ...,
        description="The endpoint for the OpenAlex Incremental Ingestion API",
    )
    retry_total: int = 3
    retry_backoff_factor: float = 0.3
    retry_status_list = [
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT,
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
