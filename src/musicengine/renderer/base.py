"""Renderer interface: StemPart -> stereo float32 audio of exactly the render length."""
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ..composer.base import StemPart
from ..planner.plan import Plan


@dataclass
class RenderSpec:
    sr: int
    beat_s: float
    length: int          # output samples (round(D*sr))
    loop: bool
    loop_beats: float    # loop length in beats (loop mode)

    @property
    def passes(self) -> int:
        return 2 if self.loop else 1


def render_spec(plan: Plan) -> RenderSpec:
    g = plan.g
    return RenderSpec(sr=plan.sample_rate, beat_s=g.beat_s, length=g.length_samples, loop=g.loop,
                      loop_beats=float(g.n_beats))


def events_seconds(part: StemPart, rs: RenderSpec) -> list[tuple[float, float, int, int]]:
    """(start_s, dur_s, pitch, vel); loop mode repeats the bar list twice back to back."""
    out = []
    for p in range(rs.passes):
        off = p * rs.loop_beats
        for n in part.notes:
            out.append(((n.start + off) * rs.beat_s, n.dur * rs.beat_s, n.pitch, n.vel))
    return out


def fx_seconds(part: StemPart, rs: RenderSpec) -> list[dict]:
    out = []
    for p in range(rs.passes):
        off = p * rs.loop_beats
        for f in part.fx:
            out.append({**f, "start": (f["start"] + off) * rs.beat_s, "end": (f["end"] + off) * rs.beat_s})
    return out


def total_samples(rs: RenderSpec) -> int:
    return rs.length * rs.passes


class Renderer(Protocol):
    name: str

    def render(self, part: StemPart, rs: RenderSpec) -> np.ndarray: ...

    def version(self) -> str: ...


def fit_length(audio: np.ndarray, n: int) -> np.ndarray:
    """Trim or zero-pad (n, 2)."""
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    if len(audio) >= n:
        return np.ascontiguousarray(audio[:n], dtype=np.float64)
    pad = np.zeros((n - len(audio), 2))
    return np.concatenate([audio.astype(np.float64), pad])
