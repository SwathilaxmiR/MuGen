import os
import shutil

import pytest

from musicengine.config import get_settings
from tests_conftest_helpers import services_up


def fluidsynth_available() -> bool:
    s = get_settings()
    return bool(shutil.which(s.fluidsynth_bin)) and os.path.isfile(s.soundfont_path)


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "integration" in item.keywords and not services_up():
            item.add_marker(pytest.mark.skip(reason="postgres/S3 not reachable (run `make test`)"))
        if "e2e" in item.keywords and not os.environ.get("E2E_API_URL"):
            item.add_marker(pytest.mark.skip(reason="E2E_API_URL not set (run `make test`)"))
        if "fluidsynth" in item.keywords and not fluidsynth_available():
            item.add_marker(pytest.mark.skip(reason="fluidsynth or SoundFont not installed"))
