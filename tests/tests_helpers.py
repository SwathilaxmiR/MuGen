"""Shared test helpers: pick the best renderer available (fluidsynth in compose, numpy otherwise)."""
import os
import shutil

from musicengine.config import get_settings


def _renderer() -> str:
    s = get_settings()
    if shutil.which(s.fluidsynth_bin) and os.path.isfile(s.soundfont_path):
        return "fluidsynth"
    return "numpy"


RENDERER = os.environ.get("TEST_RENDERER") or _renderer()
