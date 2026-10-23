"""Sine-per-note renderer for fast tests (RENDERER=mock)."""
import numpy as np

from ..composer.base import StemPart
from .base import RenderSpec, events_seconds, total_samples


class MockRenderer:
    name = "mock"

    def version(self) -> str:
        return "1"

    def render(self, part: StemPart, rs: RenderSpec) -> np.ndarray:
        n = total_samples(rs)
        out = np.zeros(n)
        for start, dur, pitch, vel in events_seconds(part, rs):
            i = int(round(start * rs.sr))
            m = max(1, min(int(max(dur, 0.05) * rs.sr) + int(0.05 * rs.sr), n - i))
            if i >= n:
                continue
            t = np.arange(m) / rs.sr
            f = 440.0 * 2 ** (((pitch if not part.is_drum else 60 + pitch % 24) - 69) / 12)
            env = np.exp(-t / max(dur, 0.05)) * np.minimum(1, t / 0.005) * np.minimum(1, (m - np.arange(m)) / 64)
            out[i:i + m] += 0.2 * (vel / 127) * env * np.sin(2 * np.pi * f * t)
        return np.stack([out, out], axis=1)
