"""Request/response schemas (the OpenAPI contract is generated from these)."""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import get_settings

_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_KEY_RE = re.compile(r"^\s*([A-Ga-g])\s*(#|♯|b|♭|-sharp| sharp|-flat| flat)?\s*"
                     r"(major|minor|maj|min|m|M)?\s*$")


def parse_key(text: str) -> tuple[int, str, str]:
    """'F# minor' / 'Am' / 'Bb' -> (pitch class, mode, canonical name)."""
    m = _KEY_RE.match(text or "")
    if not m:
        raise ValueError(f"unrecognised key {text!r}; use e.g. 'C major', 'A minor', 'F# minor', 'Am'")
    letter = m.group(1).upper()
    acc = (m.group(2) or "").strip(" -").lower()
    shift = {"#": 1, "♯": 1, "sharp": 1, "b": -1, "♭": -1, "flat": -1}.get(acc, 0)
    q = m.group(3) or ""
    mode = "minor" if q in ("minor", "min", "m") else "major"
    pc = (_PC[letter] + shift) % 12
    name = f"{letter}{'#' if shift == 1 else 'b' if shift == -1 else ''} {mode}"
    return pc, mode, name


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_s: float = Field(ge=0, description="Requested start time in seconds")
    mood: str = Field(min_length=1, max_length=200)


class OutputOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_rate: Literal[44100, 48000] = 48000
    target_lufs: float = Field(-16.0, ge=-30, le=-8)
    formats: list[Literal["wav", "mp3"]] = Field(default_factory=lambda: ["wav"])


class MusicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{
        "prompt": "calm cinematic piano that builds to an uplifting peak",
        "duration_s": 45,
        "sections": [{"start_s": 0, "mood": "calm intro"}, {"start_s": 20, "mood": "build"},
                     {"start_s": 32, "mood": "uplifting peak"}],
        "output": {"sample_rate": 48000, "target_lufs": -16, "formats": ["wav", "mp3"]},
    }]})

    prompt: str = Field(min_length=1, max_length=2000)
    duration_s: float = Field(description="Exact length of every output file, 5-300 s")
    sections: list[Section] | None = Field(None, max_length=32)
    tempo_bpm: float | None = Field(None, ge=40, le=200)
    key: str | None = None
    loopable: bool = False
    narration_url: str | None = Field(None, max_length=2048,
                                      description="https://, http:// or upload://<id> from POST /api/v1/uploads")
    seed: int | None = Field(None, ge=0, le=2**31 - 1)
    output: OutputOptions = Field(default_factory=OutputOptions)
    callback_url: str | None = Field(None, max_length=2048)

    @field_validator("duration_s")
    @classmethod
    def _dur(cls, v):
        s = get_settings()
        if not s.min_duration_s <= v <= s.max_duration_s:
            raise ValueError(f"duration_s must be between {s.min_duration_s:g} and {s.max_duration_s:g}")
        return v

    @field_validator("key")
    @classmethod
    def _key(cls, v):
        if v is not None:
            parse_key(v)
        return v

    @field_validator("narration_url", "callback_url")
    @classmethod
    def _url(cls, v):
        if v is not None and not re.match(r"^(https?://|upload://)", v):
            raise ValueError("must start with https://, http:// or upload://")
        return v


class RegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stem: str
    seed: int | None = Field(None, ge=0, le=2**31 - 1)
    callback_url: str | None = None


class JobAccepted(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    status_url: str


class JobResult(BaseModel):
    mix_wav: str
    mix_mp3: str | None = None
    stems: dict[str, str]
    mix_ducked: str | None = None
    manifest: str


class ErrorInfo(BaseModel):
    code: str
    message: str
    retryable: bool
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorInfo


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: int = Field(ge=0, le=100)
    kind: Literal["generate", "regenerate"] = "generate"
    parent_job_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    warnings: list[dict] = Field(default_factory=list)
    result: JobResult | None = None
    error: ErrorInfo | None = None


class UploadResponse(BaseModel):
    url: str
    size_bytes: int
