"""Style presets (one YAML per style). Validated on load."""
from functools import lru_cache
from importlib import resources

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

STEMS = ("drums", "bass", "harmony", "melody")
# GM programs (0-indexed) that are voices: choir aahs, voice oohs, synth voice, lead 6 (voice), pad 4 (choir)
FORBIDDEN_PROGRAMS = frozenset({52, 53, 54, 85, 91})

# per-stem activity 0..1 at intensity 0..4 (0 = silent). Harmony is never silent so there are no gaps.
DEFAULT_LAYERS = {
    "drums":   [0.0, 0.35, 0.7, 0.9, 1.0],
    "bass":    [0.0, 0.5, 0.8, 1.0, 1.0],
    "harmony": [0.6, 0.7, 0.85, 0.95, 1.0],
    "melody":  [0.0, 0.0, 0.6, 0.85, 1.0],
}


class Tempo(BaseModel):
    min: float = Field(ge=40, le=200)
    max: float = Field(ge=40, le=200)
    centre: float


class Preset(BaseModel):
    name: str
    tempo: Tempo
    keywords: list[str]
    modes: list[str]
    default_mode: str
    swing: float = Field(0, ge=0, le=1)
    base_intensity: int = Field(2, ge=0, le=4)
    valence: float = Field(ge=-1, le=1)
    energy: float = Field(ge=0, le=1)
    progressions: dict[str, list[list[str]]]
    programs: dict[str, int]
    drum_style: str
    bass_style: str
    harmony_style: str
    melody_style: str
    melody_register: int = 72
    gains: dict[str, float]
    layers: dict[str, list[float]] = Field(default_factory=lambda: {k: list(v) for k, v in DEFAULT_LAYERS.items()})

    @field_validator("programs")
    @classmethod
    def _no_vocals(cls, v):
        bad = {k: p for k, p in v.items() if k != "drums" and p in FORBIDDEN_PROGRAMS}
        if bad:
            raise ValueError(f"vocal GM programs are not allowed: {bad}")
        if set(v) != set(STEMS):
            raise ValueError(f"programs must define exactly {STEMS}")
        return v

    @model_validator(mode="after")
    def _check(self):
        if self.default_mode not in self.modes:
            raise ValueError("default_mode must be in modes")
        for m in self.modes:
            if m not in self.progressions:
                raise ValueError(f"no progressions for mode {m}")
        if not self.tempo.min <= self.tempo.centre <= self.tempo.max:
            raise ValueError("tempo centre outside range")
        if any(x <= 0 for x in self.layers["harmony"]):
            raise ValueError("harmony must sound at every intensity")
        return self


@lru_cache
def load_presets() -> dict[str, Preset]:
    out = {}
    for f in sorted(resources.files(__name__).iterdir(), key=lambda p: p.name):
        if f.name.endswith(".yaml"):
            p = Preset.model_validate(yaml.safe_load(f.read_text()))
            out[p.name] = p
    return out


def get_preset(name: str) -> Preset:
    return load_presets()[name]
