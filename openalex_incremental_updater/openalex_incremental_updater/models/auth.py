"""Define models for authentication tokens."""

from pydantic import BaseModel


class DestinyRepoToken(BaseModel, extra="forbid"):
    """
    Model for storing the token used to access the DESTINY repository.

    This token is required to authenticate requests to the Destiny API.
    """

    token_type: str
    expires_in: int
    ext_expires_in: int
    access_token: str
    token_source: str
