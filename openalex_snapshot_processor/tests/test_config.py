"""Tests for config.py."""

import pytest
from pydantic import ValidationError

from openalex_snapshot_processor.config import Settings

from .conftest import ENV_DEFAULTS


def test_settings_loads_from_env(set_test_env) -> None:
    """Settings should load successfully from environment variables."""
    settings = Settings()
    assert ENV_DEFAULTS["BATCH_DIR"] == settings.BATCH_DIR
    assert int(ENV_DEFAULTS["WINDOW_SIZE"]) == settings.WINDOW_SIZE
    assert int(ENV_DEFAULTS["POLL_INTERVAL_SECONDS"]) == settings.POLL_INTERVAL_SECONDS
    assert ENV_DEFAULTS["STORAGE_BLOB_ACCOUNT"] == settings.STORAGE_BLOB_ACCOUNT
    assert settings.DECOMPRESS_ON_UPLOAD is False
    assert (
        int(ENV_DEFAULTS["SAS_TOKEN_EXPIRY_HOURS"]) == settings.SAS_TOKEN_EXPIRY_HOURS
    )


def test_settings_defaults() -> None:
    """Settings with only required fields should use defaults."""
    settings = Settings(
        BATCH_DIR="/data",
        STORAGE_BLOB_ACCOUNT="acct",
        STORAGE_BLOB_CONTAINER="ctr",
        STORAGE_BLOB_ACCOUNT_KEY="key",  # pragma: allowlist secret
        REPOSITORY_ENDPOINT="https://repo.example.com",
        TOKEN_ENDPOINT="https://token.example.com",  # noqa: S106
    )
    assert Settings.model_fields["WINDOW_SIZE"].default == settings.WINDOW_SIZE
    assert (
        Settings.model_fields["POLL_INTERVAL_SECONDS"].default
        == settings.POLL_INTERVAL_SECONDS
    )
    assert settings.BLOB_PREFIX == "snapshot_bulk/"
    assert settings.PROCESSOR_NAME == "OpenAlex Snapshot Bulk Feeder"


def test_settings_missing_required_raises() -> None:
    """Settings without required fields should raise ValidationError."""
    with pytest.raises(ValidationError):
        Settings()
