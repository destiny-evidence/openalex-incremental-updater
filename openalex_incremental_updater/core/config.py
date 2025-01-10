"""Define API settings."""

import json

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Store typed settings for Pydantic."""

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "OpenAlex Incremental Updater"

    cors_origins: list[HttpUrl] | str = Field(..., description="CORS allowed origins")
    allow_credentials: bool = True
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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
            except json.JSONDecodeError:
                origins = [url.strip() for url in cors_origins.split(",")]
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
