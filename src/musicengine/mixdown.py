"""Mixdown: shared ending envelope, per-stem balance, master loudness, one look-ahead limiter curve
computed from the sum and applied to every stem. Stems are written post-master, so
mix == sum(gain_i * stem_i) with gain_i == 1.0 exactly (up to 24-bit rounding)."""
import os
import subprocess
from dataclasses import dataclass, field

import numpy as np
import soundfile as sf
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import lfilter

from . import qa
from .config import Settings, get_settings
from .errors import JobError
from .planner.plan import Plan

LOOKAHEAD_MS = 5.0
RELEASE_MS = 80.0
STEM_REF_LUFS = -23.0
STEM_GAIN_LIMITS_DB = (-20.0, 12.0)


@dataclass
class MixResult:
    stems: dict[str, np.ndarray]
    mix: np.ndarray
    gains: dict[str, float]
    balance_db: dict[str, float]
    master_gain_db: float
    limiter: dict
    loudness: dict
    curve: np.ndarray | None = None      # limiter gain curve (kept for regenerate)
    passes: int = 1
    notes: list[str] = field(default_factory=list)


def ending_envelope(plan: Plan) -> np.ndarray:
    """Non-loop: 2 ms fade-in; after the hit, hold, then a squared raised-cosine to 0 at the last sample.
    Loop: flat (no fades, so the wrap stays seamless)."""
    g = plan.g
    n, sr = g.length_samples, plan.sample_rate
    env = np.ones(n)
    if g.loop:
        return env
    fi = int(0.002 * sr)
    env[:fi] = np.linspace(0, 1, fi)
    start = int((g.hit_time_s + 0.35 * g.tail_s) * sr)
    start = min(start, n - int(0.05 * sr))  # at least the 50 ms end fade
    m = n - start
    u = np.arange(m) / max(m - 1, 1)
    env[start:] = ((1 + np.cos(np.pi * u)) / 2) ** 2
    return env


def limiter_curve(x: np.ndarray, sr: int, ceiling_dbtp: float) -> np.ndarray:
    """Look-ahead gain curve from the (oversampled) peak envelope of the sum.
    m[n] = min(required[n .. n+la]); a = trailing mean of m over la (smooth attack, never above the
    requirement at a peak); release = one-pole on a, taken as min so peaks stay limited."""
    ceil = 10 ** (ceiling_dbtp / 20)
    peak = np.concatenate([qa.oversampled_peak_env(x[s:s + (1 << 20)]) for s in range(0, len(x), 1 << 20)])
    req = np.minimum(1.0, ceil / np.maximum(peak, 1e-12))
    if req.min() >= 1.0:
        return np.ones(len(x))
    la = max(1, int(LOOKAHEAD_MS * sr / 1000))
    m = minimum_filter1d(req, size=la + 1, origin=-(la // 2), mode="nearest")
    a = uniform_filter1d(m, size=la + 1, origin=la // 2, mode="nearest")
    alpha = np.exp(-1.0 / (RELEASE_MS * sr / 1000))
    rel = lfilter([1 - alpha], [1, -alpha], a, zi=[a[0] * alpha])[0]
    return np.minimum(np.minimum(a, rel), 1.0)


def _balance(stems: dict[str, np.ndarray], plan: Plan, sr: int) -> dict[str, float]:
    out = {}
    for name, a in stems.items():
        lufs = qa.integrated_lufs(a, sr)
        target = STEM_REF_LUFS + 20 * np.log10(plan.preset.gains.get(name, 1.0))
        gdb = 0.0 if lufs <= -70 else float(np.clip(target - lufs, *STEM_GAIN_LIMITS_DB))
        out[name] = gdb
    return out


def master(stems_in: dict[str, np.ndarray], plan: Plan, s: Settings | None = None,
           ceiling_dbtp: float | None = None, max_passes: int = 4) -> MixResult:
    s = s or get_settings()
    sr = plan.sample_rate
    target = plan.target_lufs
    ceiling = s.tp_ceiling_dbtp if ceiling_dbtp is None else ceiling_dbtp
    env = ending_envelope(plan)[:, None]
    balance = _balance(stems_in, plan, sr)
    pre = {k: v * env * 10 ** (balance[k] / 20) for k, v in stems_in.items()}
    pre_sum = np.sum(list(pre.values()), axis=0)
    gain_db = target - qa.integrated_lufs(pre_sum, sr)
    curve = np.ones(len(pre_sum))
    lufs = tp = None
    passes = 0
    for passes in range(1, max_passes + 1):
        x = pre_sum * 10 ** (gain_db / 20)
        curve = limiter_curve(x, sr, ceiling - 0.1)
        y = x * curve[:, None]
        lufs, tp = qa.integrated_lufs(y, sr), qa.true_peak_dbtp(y)
        if abs(lufs - target) <= s.lufs_tol * 0.6 and tp <= ceiling:
            break
        gain_db += target - lufs
    stems = {k: v * 10 ** (gain_db / 20) * curve[:, None] for k, v in pre.items()}
    mix = np.sum(list(stems.values()), axis=0)
    lim = {"ceiling_dbtp": ceiling, "lookahead_ms": LOOKAHEAD_MS, "release_ms": RELEASE_MS,
           "max_gain_reduction_db": round(-qa.db(curve.min()), 3), "passes": passes}
    loud = {"integrated_lufs": round(lufs, 3), "true_peak_dbtp": round(tp, 3),
            "lra": round(qa.loudness_range(mix, sr), 2), "target_lufs": target}
    return MixResult(stems=stems, mix=mix, gains={k: 1.0 for k in stems}, balance_db=balance,
                     master_gain_db=round(gain_db, 4), limiter=lim, loudness=loud, curve=curve, passes=passes)


# ---------------------------------------------------------------- file output
def write_wav(path: str, x: np.ndarray, sr: int) -> None:
    sf.write(path, np.clip(x, -1.0, 1.0), sr, subtype="PCM_24")


def read_wav(path: str) -> tuple[np.ndarray, int]:
    x, sr = sf.read(path, dtype="float64", always_2d=True)
    return x, sr


def encode_mp3(wav_path: str, mp3_path: str, s: Settings | None = None) -> None:
    s = s or get_settings()
    proc = subprocess.run([s.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-i", wav_path,
                           "-codec:a", "libmp3lame", "-b:a", "320k", mp3_path], capture_output=True, timeout=300)
    if proc.returncode != 0:
        raise JobError("INTERNAL_ERROR", f"mp3 encode failed: {proc.stderr.decode()[-300:]}")


def decode_audio(path: str, sr: int, s: Settings | None = None, mono16k: bool = False) -> np.ndarray:
    """Decode any audio file through ffmpeg to float (stereo at sr, or mono 16 kHz)."""
    s = s or get_settings()
    args = ["-ac", "1", "-ar", "16000"] if mono16k else ["-ac", "2", "-ar", str(sr)]
    proc = subprocess.run([s.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-i", path, *args,
                           "-f", "f32le", "-"], capture_output=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode()[-300:])
    a = np.frombuffer(proc.stdout, dtype=np.float32).astype(np.float64)
    return a if mono16k else a.reshape(-1, 2)


def mp3_true_peak(mp3_path: str, sr: int, n: int, s: Settings | None = None) -> float:
    x = decode_audio(mp3_path, sr, s)
    return qa.true_peak_dbtp(x[:n] if len(x) >= n else x)


def write_outputs(res: MixResult, out_dir: str, sr: int, want_mp3: bool, s: Settings | None = None) -> dict:
    os.makedirs(os.path.join(out_dir, "stems"), exist_ok=True)
    paths = {"mix_wav": os.path.join(out_dir, "mix.wav"), "stems": {}}
    write_wav(paths["mix_wav"], res.mix, sr)
    for k, v in res.stems.items():
        p = os.path.join(out_dir, "stems", f"{k}.wav")
        write_wav(p, v, sr)
        paths["stems"][k] = p
    if want_mp3:
        paths["mix_mp3"] = os.path.join(out_dir, "mix.mp3")
        encode_mp3(paths["mix_wav"], paths["mix_mp3"], s)
    return paths
