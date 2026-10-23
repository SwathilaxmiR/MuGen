"""Own wavetable/additive synth + synthesized drum kit. No external dependency; fallback renderer."""
from functools import lru_cache

import numpy as np
from scipy.signal import butter, sosfilt

from ..composer.base import StemPart
from .base import RenderSpec, events_seconds, total_samples

TABLE = 2048


def _table(harmonics: list[float], phases: str = "sine") -> np.ndarray:
    t = np.arange(TABLE) / TABLE
    w = sum(a * np.sin(2 * np.pi * (k + 1) * t) for k, a in enumerate(harmonics) if a)
    return (w / np.max(np.abs(w))).astype(np.float64)


# family -> (harmonic amplitudes, attack s, decay tau s (None = sustain), release s, sustain level, detune)
FAMILIES = {
    "piano": ([1, .5, .3, .2, .12, .08, .05, .03], 0.004, 1.2, 0.25, 0.0, 0),
    "mallet": ([1, 0, .25, 0, .08], 0.002, 0.45, 0.2, 0.0, 0),
    "organ": ([1, .6, .3, .25, .1, .1], 0.01, None, 0.08, 0.9, 0),
    "guitar": ([1, .6, .45, .3, .2, .14, .1], 0.003, 0.8, 0.12, 0.0, 0),
    "dist": ([1, .7, .6, .5, .45, .4, .35, .3, .25, .2], 0.005, None, 0.1, 0.85, 4),
    "bass": ([1, .55, .3, .18, .1], 0.006, 0.9, 0.08, 0.35, 0),
    "strings": ([1, .5, .33, .25, .2, .16, .14, .12], 0.18, None, 0.35, 0.85, 6),
    "pizz": ([1, .4, .2, .1], 0.002, 0.25, 0.1, 0.0, 0),
    "brass": ([1, .8, .6, .45, .35, .25, .18, .12], 0.06, None, 0.18, 0.8, 3),
    "reed": ([1, 0, .45, 0, .25, 0, .12, 0, .06], 0.04, None, 0.12, 0.8, 0),
    "flute": ([1, .25, .05], 0.06, None, 0.15, 0.85, 0),
    "lead": ([1, .5, .33, .25, .2, .17, .14, .12, .11, .1], 0.01, None, 0.1, 0.8, 8),
    "pad": ([1, .5, .33, .25, .2, .16], 0.4, None, 0.8, 0.9, 9),
}


def family(program: int) -> str:
    if program == 45:
        return "pizz"
    if program in (29, 30):
        return "dist"
    groups = ["piano", "mallet", "organ", "guitar", "bass", "strings", "strings", "brass", "reed", "flute",
              "lead", "pad", "pad", "mallet", "mallet", "mallet"]
    return groups[program // 8]


@lru_cache
def _tables(fam: str) -> np.ndarray:
    return _table(FAMILIES[fam][0])


def _note(freq: float, dur: float, vel: int, fam: str, sr: int) -> np.ndarray:
    _, att, tau, rel, sus, detune = FAMILIES[fam]
    n = int((dur + rel) * sr)
    if n <= 0:
        return np.zeros(0)
    t = np.arange(n) / sr
    table = _tables(fam)
    out = np.zeros(n)
    voices = [0.0] if not detune else [-detune, detune]
    for cents in voices:
        f = freq * 2 ** (cents / 1200)
        idx = (np.cumsum(np.full(n, f * TABLE / sr)) % TABLE).astype(np.int64)
        out += table[idx]
    out /= len(voices)
    env = np.minimum(1.0, t / att)
    if tau is not None:
        env *= np.exp(-t / tau) * (1 - sus) + sus
    else:
        env *= sus + (1 - sus) * np.exp(-t / 0.3)
    off = int(dur * sr)
    if off < n:
        level = env[off - 1] if off > 0 else 0.0
        env[off:] = level * np.exp(-(t[off:] - t[off]) / max(rel / 4, 1e-3))
    env[-min(64, n):] *= np.linspace(1, 0, min(64, n))
    return out * env * (vel / 127) ** 1.5 * 0.3


# ------------------------------------------------------------------ drums
@lru_cache
def _drum(pitch: int, sr: int) -> np.ndarray:
    rng = np.random.default_rng(pitch)

    def noise(sec, lo=None, hi=None):
        x = rng.standard_normal(int(sec * sr))
        if lo and hi:
            x = sosfilt(butter(2, [lo, hi], "bandpass", fs=sr, output="sos"), x)
        elif lo:
            x = sosfilt(butter(2, lo, "highpass", fs=sr, output="sos"), x)
        return x

    def decay(x, tau):
        return x * np.exp(-np.arange(len(x)) / sr / tau)

    def sweep(f0, f1, sec, tau):
        n = int(sec * sr)
        t = np.arange(n) / sr
        f = f1 + (f0 - f1) * np.exp(-t / 0.04)
        return decay(np.sin(2 * np.pi * np.cumsum(f) / sr), tau)

    def mix(*parts):
        m = max(len(p) for p in parts)
        return sum(np.pad(p, (0, m - len(p))) for p in parts)

    if pitch in (35, 36):
        x = mix(sweep(130, 45, 0.6, 0.25), 0.3 * decay(noise(0.01, 2000, 8000), 0.003))
    elif pitch in (38, 40):
        x = mix(0.7 * decay(noise(0.35, 1200, 7000), 0.09), 0.6 * sweep(260, 185, 0.25, 0.08))
    elif pitch == 37:
        x = mix(decay(noise(0.08, 2000, 6000), 0.02), 0.5 * sweep(500, 450, 0.08, 0.02))
    elif pitch == 39:
        x = mix(*[np.pad(decay(noise(0.25, 900, 4000), 0.06 if k == 2 else 0.008), (int(k * 0.012 * sr), 0))
                  for k in range(3)])
    elif pitch in (42, 44):
        x = 0.5 * decay(noise(0.12, 7000), 0.03)
    elif pitch == 46:
        x = 0.45 * decay(noise(0.6, 6000), 0.22)
    elif pitch in (49, 52, 55, 57):
        x = 0.5 * decay(noise(2.5, 4000), 0.9)
    elif pitch in (51, 53, 59):
        x = mix(0.25 * decay(noise(1.2, 5000), 0.45), 0.2 * sweep(3200, 3150, 1.2, 0.5))
    elif pitch in (41, 43, 45, 47, 48, 50):
        base = {41: 70, 43: 85, 45: 100, 47: 125, 48: 140, 50: 165}[pitch]
        x = sweep(base * 1.6, base, 0.7, 0.28)
    elif pitch in (54, 70, 69, 82):
        x = 0.4 * decay(noise(0.15, 5000), 0.04)
    elif pitch in (76, 77):
        x = sweep(900 if pitch == 76 else 650, 800 if pitch == 76 else 600, 0.12, 0.03)
    else:
        x = decay(noise(0.2, 1000, 5000), 0.05)
    n = len(x)
    x[-min(64, n):] *= np.linspace(1, 0, min(64, n))
    return x * 0.5


class NumpyRenderer:
    name = "numpy"

    def version(self) -> str:
        return "1"

    def render(self, part: StemPart, rs: RenderSpec) -> np.ndarray:
        n = total_samples(rs)
        out = np.zeros(n)
        fam = None if part.is_drum else family(part.program)
        for start, dur, pitch, vel in events_seconds(part, rs):
            i = int(round(start * rs.sr))
            if i >= n:
                continue
            if part.is_drum:
                x = _drum(pitch, rs.sr) * (vel / 127) ** 1.3
            else:
                x = _note(440.0 * 2 ** ((pitch - 69) / 12), dur, vel, fam, rs.sr)
            j = min(n, i + len(x))
            out[i:j] += x[: j - i]
        if fam == "bass":
            out = sosfilt(butter(2, 1500, "lowpass", fs=rs.sr, output="sos"), out)
        return np.stack([out, out], axis=1)
