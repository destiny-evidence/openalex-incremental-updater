"""Define the schema for a postgres DB to store our OpenAlex Work data."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
)
from sqlmodel import Field, SQLModel


class Work(SQLModel, table=True):
    """Define our unit of data based on OpenAlex Work."""

    id: str = Field(primary_key=True, index=True)
    title: str
    authors: dict = Field(default_factory=dict, sa_column=Column(JSON))
    abstract: str | None
    publication_date: datetime
    created_date: str
    updated_date: str
    language: str
