import os

import pytest
from pydantic import ValidationError

from openalex_snapshot_processor.config import Settings, get_settings


def test_settings_loads_from_env(set_test_environment_variables):
    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.SNAPSHOT_ROOT == "/fake/snapshot/root"


def test_settings_failure(set_test_environment_variables):
    os.environ.pop("SNAPSHOT_ROOT", None)
    with pytest.raises(ValidationError):
        get_settings()
    # restore the environment variable so cleanup doesn't fail
    os.environ["SNAPSHOT_ROOT"] = "/fake/snapshot/root"
