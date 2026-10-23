"""Deterministic per-stem FX in numpy: high-pass, gentle EQ, own Schroeder reverb, pan/width, riser.

Every effect is applied to one stem at a time, so the mix (a weighted sum of stems) stays linear.
"""
import numpy as np
from scipy.signal import butter, sosfilt

COMB_MS = (32.4, 33.7, 35.6, 37.9)    # Freeverb-like tunings
ALLPASS_MS = (5.0, 1.7)
STEREO_SPREAD = 23                     # samples added to right-channel delays

# stem -> (highpass Hz, reverb wet, rt60 s, pan -1..1, width 0..1.5)
STEM_FX = {
    "drums":   (30, 0.10, 1.1, 0.0, 1.0),
    "bass":    (28, 0.04, 1.0, 0.0, 0.3),
    "harmony": (70, 0.22, 2.0, -0.08, 1.25),
    "melody":  (110, 0.20, 1.8, 0.12, 1.0),
}
WET_SCALE = {"ambient": 1.8, "cinematic": 1.5, "epic": 1.3, "tense": 1.4, "lofi": 0.7, "rock": 0.7,
             "electronic": 1.0, "jazz": 0.8}


def _comb(x: np.ndarray, d: int, g: float) -> np.ndarray:
    """y[n] = x[n] + g*y[n-d], vectorised in blocks of d (exact, O(N))."""
    y = np.empty_like(x)
    y[:d] = x[:d]
    for s in range(d, len(x), d):
        e = min(s + d, len(x))
        y[s:e] = x[s:e] + g * y[s - d:e - d]
    return y


def _allpass(x: np.ndarray, d: int, g: float = 0.5) -> np.ndarray:
    """y[n] = -g*x[n] + x[n-d] + g*y[n-d]."""
    y = np.empty_like(x)
    y[:d] = -g * x[:d]
    for s in range(d, len(x), d):
        e = min(s + d, len(x))
        y[s:e] = -g * x[s:e] + x[s - d:e - d] + g * y[s - d:e - d]
    return y


def schroeder(mono: np.ndarray, sr: int, rt60: float) -> np.ndarray:
    """4 parallel combs -> 2 series allpasses, per channel with spread delays. Returns (n, 2)."""
    chans = []
    for spread in (0, STEREO_SPREAD):
        acc = np.zeros_like(mono)
        for ms in COMB_MS:
            d = int(ms * sr / 1000) + spread
            g = 10 ** (-3 * d / (rt60 * sr))
            acc += _comb(mono, d, g)
        y = acc / len(COMB_MS)
        for ms in ALLPASS_MS:
            y = _allpass(y, int(ms * sr / 1000) + spread // 3)
        chans.append(y)
    wet = np.stack(chans, axis=1)
    return sosfilt(butter(1, 6000, "lowpass", fs=sr, output="sos"), wet, axis=0)


def riser(n: int, sr: int, start_s: float, end_s: float, seed: int) -> np.ndarray:
    """Noise sweep with rising band and level, ending exactly at end_s."""
    i0, i1 = int(start_s * sr), min(n, int(end_s * sr))
    out = np.zeros((n, 2))
    m = i1 - i0
    if m <= sr // 10:
        return out
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(m)
    # rising one-pole lowpass cutoff by processing in 32 chunks with increasing cutoffs
    y = np.empty(m)
    zi = None
    chunks = np.array_split(np.arange(m), 32)
    for k, idx in enumerate(chunks):
        fc = 300 * (40 ** (k / 31))
        sos = butter(1, min(fc, sr / 2.2), "lowpass", fs=sr, output="sos")
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        y[idx], zi = sosfilt(sos, x[idx], zi=zi)
    ramp = np.linspace(0, 1, m) ** 2
    ramp[-int(0.01 * sr):] *= np.linspace(1, 0, int(0.01 * sr))
    y *= ramp * 0.08
    out[i0:i1, 0] = y
    out[i0:i1, 1] = np.roll(y, 17)
    return out


def apply_stem_fx(audio: np.ndarray, stem: str, sr: int, style: str) -> np.ndarray:
    hp, wet, rt60, pan, width = STEM_FX.get(stem, (60, 0.15, 1.5, 0.0, 1.0))
    wet *= WET_SCALE.get(style, 1.0)
    x = sosfilt(butter(2, hp, "highpass", fs=sr, output="sos"), audio, axis=0)
    if stem == "harmony" and style == "lofi":
        x = sosfilt(butter(2, 4500, "lowpass", fs=sr, output="sos"), x, axis=0)  # dusty keys
    if stem == "bass":  # gentle low-mid dip for clarity
        x = x - 0.15 * sosfilt(butter(1, [250, 500], "bandpass", fs=sr, output="sos"), x, axis=0)
    mid = (x[:, 0] + x[:, 1]) / 2
    side = (x[:, 0] - x[:, 1]) / 2 * width
    x = np.stack([mid + side, mid - side], axis=1)
    if wet > 0:
        x = x + wet * schroeder(mid, sr, rt60)
    # constant-power balance
    ang = (pan + 1) * np.pi / 4
    x[:, 0] *= np.cos(ang) * np.sqrt(2)
    x[:, 1] *= np.sin(ang) * np.sqrt(2)
    return x
