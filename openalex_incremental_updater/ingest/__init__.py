"""OpenAlex data ingestion module."""

from enum import StrEnum

from fastapi import status
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


class CreatedOrUpdated(StrEnum):
    """Define the types of dates to filter by."""

    CREATED = "created"
    UPDATED = "updated"


class RetrySession(Session):
    """Define a requests.Session with retry capabilities."""

    def __init__(self, retries: int = 5, backoff_factor: float = 0.1) -> None:
        """Class constructor."""
        super().__init__()
        self.retries = retries
        self.backoff_factor = backoff_factor

        self.setup()

    def setup(self) -> None:
        """Define retry behaviour and attach to the session."""
        retry_settings = Retry(
            total=self.retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_502_BAD_GATEWAY,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_504_GATEWAY_TIMEOUT,
            ],
        )
        self.mount("https://", HTTPAdapter(max_retries=retry_settings))
