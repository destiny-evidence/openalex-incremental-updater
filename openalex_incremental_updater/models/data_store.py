"""Define the schema for a postgres DB to store our OpenAlex Work data."""

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Text,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Generic base class from sqlalchemy with which to define custom types."""


class Work(Base):
    """Define our unit of data based on OpenAlex Work."""

    __tablename__ = "works"
    id = Column(Text, primary_key=True, index=True)
    title = Column(Text, index=True)
    authors = Column(JSON)
    abstract = Column(Text)
    publication_date = Column(DateTime)
    created_date = Column(Text)
    updated_date = Column(Text)
    language = Column(Text)
