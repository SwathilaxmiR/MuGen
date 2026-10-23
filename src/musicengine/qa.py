"""Audio QA. The same functions run at job time (self-check gate), in tests and in the batch runner."""
import re
import subprocess

import numpy as np
import pyloudnorm
from scipy.signal import resample_poly

EPS = 1e-12


def db(x: float) -> float:
    return 20 * np.log10(max(float(x), EPS))


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


# ---------------------------------------------------------------- loudness
def integrated_lufs(x: np.ndarray, sr: int) -> float:
    v = pyloudnorm.Meter(sr).integrated_loudness(x)
    return float(v) if np.isfinite(v) else -120.0


def loudness_range(x: np.ndarray, sr: int) -> float:
    try:
        v = pyloudnorm.Meter(sr).loudness_range(x)
        return float(v) if np.isfinite(v) else 0.0
    except Exception:
        return 0.0


def oversampled_peak_env(x: np.ndarray, factor: int = 4) -> np.ndarray:
    """Per original sample: max |x| over channels and the `factor` interpolated points (BS.1770 style)."""
    up = resample_poly(x, factor, 1, axis=0)
    n = len(x)
    up = np.abs(up[: n * factor]).max(axis=1).reshape(n, factor)
    return up.max(axis=1)


def true_peak_dbtp(x: np.ndarray) -> float:
    # resample_poly in chunks keeps memory bounded on 300 s files
    peak, step = 0.0, 1 << 20
    for s in range(0, len(x), step):
        seg = x[max(0, s - 64): s + step + 64]
        peak = max(peak, float(oversampled_peak_env(seg).max()))
    return db(peak)


def ffmpeg_ebur128(path: str, ffmpeg: str = "ffmpeg") -> dict:
    """Independent meter: ffmpeg's ebur128 filter (I, LRA, true peak)."""
    proc = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true",
                           "-f", "null", "-"], capture_output=True, timeout=300)
    txt = proc.stderr.decode(errors="replace")
    summary = txt[txt.rfind("Summary:"):]

    def grab(label):
        m = re.search(label + r":\s+(-?[\d.]+|-inf)", summary)
        return None if not m or m.group(1) == "-inf" else float(m.group(1))

    return {"integrated_lufs": grab("I"), "lra": grab("LRA"), "true_peak_dbtp": grab("Peak")}


# ---------------------------------------------------------------- structure checks
def sum_diff_db(stems: list[np.ndarray], mix: np.ndarray) -> float:
    diff = np.sum(stems, axis=0) - mix
    r = rms(mix)
    return db(rms(diff) / r) if r > 0 else 0.0


def length_errors(files: dict[str, np.ndarray], expected: int, sr: int) -> dict[str, float]:
    return {k: abs(len(v) - expected) / sr for k, v in files.items()}


def full_scale_samples(x: np.ndarray, bits: int = 24) -> int:
    lsb = 1.0 / (2 ** (bits - 1))
    return int(np.sum(np.abs(x) >= 1.0 - lsb))


def _window_max_jumps(mono: np.ndarray, win: int) -> np.ndarray:
    d = np.abs(np.diff(mono, prepend=mono[0]))
    n = len(d) // win
    return d[: n * win].reshape(n, win).max(axis=1)


def click_report(x: np.ndarray, sr: int, times_s: list[float], ratio: float = 2.0, pct: float = 99.0) -> dict:
    """Max sample-to-sample jump within +-20 ms of each boundary vs `ratio` x the `pct` percentile of the
    track's 40 ms-window maxima. The reference is the track's own loud transients (drum hits), because
    section downbeats carry an intentional crash; p95 flagged those in testing, p99 does not, and a real
    discontinuity (e.g. a 0.3 FS step) is still >10x the reference (see test_qa)."""
    mono = x.mean(axis=1) if x.ndim == 2 else x
    win = int(0.04 * sr)
    ref = float(np.percentile(_window_max_jumps(mono, win), pct))
    d = np.abs(np.diff(mono, prepend=mono[0]))
    out = []
    for t in times_s:
        i0, i1 = max(0, int((t - 0.02) * sr)), min(len(d), int((t + 0.02) * sr))
        if i1 <= i0:
            continue
        m = float(d[i0:i1].max())
        out.append({"t": round(t, 4), "max_jump": m, "ratio": m / max(ref, EPS), "click": m > ratio * ref})
    return {"reference_jump": ref, "boundaries": out, "clicks": sum(b["click"] for b in out)}


def gap_report(x: np.ndarray, sr: int, start_s: float, end_s: float, floor_db: float = -50.0) -> dict:
    """100 ms RMS (hop 50 ms) of the louder channel never below floor between start and end."""
    win, hop = int(0.1 * sr), int(0.05 * sr)
    i, gaps, worst = int(start_s * sr), [], 0.0
    stop = int(end_s * sr)
    worst = 0.0
    while i + win <= stop:
        seg = x[i:i + win]
        level = db(max(rms(seg[:, 0]), rms(seg[:, 1])) if seg.ndim == 2 else rms(seg))
        worst = min(worst, level)
        if level < floor_db:
            gaps.append(round(i / sr, 3))
        i += hop
    return {"gaps": len(gaps), "gap_times": gaps[:20], "min_rms_db": round(worst, 2)}


def _flux(mono: np.ndarray, sr: int, frame_s: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    f = int(frame_s * sr)
    n = len(mono) // f
    e = np.sqrt(np.mean(mono[: n * f].reshape(n, f) ** 2, axis=1)) + 1e-9
    le = 20 * np.log10(e)
    flux = np.maximum(0, np.diff(le, prepend=le[0]))
    return le, flux


def ending_report(x: np.ndarray, sr: int, hit_time_s: float | None) -> dict:
    tail = x[-int(0.05 * sr):]
    last_db = db(max(rms(tail[:, 0]), rms(tail[:, 1])))
    rep = {"last_50ms_db": round(last_db, 2), "silent_end": last_db < -60.0}
    if hit_time_s is not None:
        mono = x.mean(axis=1)
        le, flux = _flux(mono, sr)
        k = int(hit_time_s / 0.01)
        near = flux[max(0, k - 3): k + 6]
        med = float(np.median(flux[flux > 0])) if np.any(flux > 0) else 0.0
        rep["hit_onset_flux_db"] = round(float(near.max()) if len(near) else 0.0, 2)
        rep["median_flux_db"] = round(med, 2)
        rep["hit_onset"] = bool(len(near) and near.max() >= max(3 * med, 1.0))
    return rep


def section_alignment_report(x: np.ndarray, sr: int, sections: list[dict]) -> dict:
    """For each section change: is there an energy step within 0.5 s of the applied start? Either an
    onset (flux peak) within +-0.5 s while the section level (2 s windows, skipping the pre-section fill)
    moves the right way, or a >= 1 dB level step between the 0.5 s before and the 0.5 s after the
    applied start in the direction of the intensity change."""
    mono = x.mean(axis=1)
    le, flux = _flux(mono, sr)
    med = float(np.median(flux[flux > 0])) if np.any(flux > 0) else 0.0
    out = []
    for prev, cur in zip(sections, sections[1:]):
        t = cur["applied_start_s"]
        k = int(round(t / 0.01))
        lo, hi = max(0, k - 50), min(len(le), k + 50)
        onset_idx = lo + int(np.argmax(flux[lo:hi])) if hi > lo else k
        before = le[max(0, k - 50):k].mean() if k > 0 else le[0]
        after = le[k:k + 50].mean() if k < len(le) else le[-1]
        step = float(after - before)  # mean level 0.5 s after vs 0.5 s before the applied start
        d_int = cur["intensity"] - prev["intensity"]
        onset = bool(flux[onset_idx] >= max(3 * med, 1.0)) and abs(onset_idx * 0.01 - t) <= 0.5
        # direction over longer windows that skip the pre-section fill: [t-2.5, t-0.5) vs [t, t+2)
        long_before = le[max(0, k - 250):max(1, k - 50)].mean()
        long_after = le[k:k + 200].mean() if k < len(le) else le[-1]
        long_step = float(long_after - long_before)
        direction_ok = d_int == 0 or (long_step > 0) == (d_int > 0) or abs(long_step) < 0.5
        step_ok = d_int != 0 and (step > 0) == (d_int > 0) and abs(step) >= 1.0
        aligned = d_int == 0 or (onset and direction_ok) or step_ok
        out.append({"applied_start_s": round(t, 4), "onset_offset_s": round(onset_idx * 0.01 - t, 3),
                    "onset": onset, "level_step_db": round(step, 2), "section_level_step_db": round(long_step, 2),
                    "intensity_change": d_int,
                    "aligned": bool(aligned)})
    return {"sections": out, "misaligned": sum(not s["aligned"] for s in out)}


def loop_seam_report(x: np.ndarray, sr: int) -> dict:
    """Concatenate the file with itself and check the joint like any other boundary."""
    joined = np.concatenate([x, x])
    t = len(x) / sr
    clicks = click_report(joined, sr, [t])
    # jump at the seam vs typical neighbouring jumps
    mono = joined.mean(axis=1)
    j = len(x)
    seam_jump = float(abs(mono[j] - mono[j - 1]))
    local = np.abs(np.diff(mono[j - 2000:j - 1]))
    return {"seam_jump": seam_jump, "local_p99_jump": float(np.percentile(local, 99)),
            "click": bool(clicks["clicks"])}


# ---------------------------------------------------------------- the gate
def run_gate(mix: np.ndarray, stems: dict[str, np.ndarray], sr: int, *, expected_len: int, target_lufs: float,
             lufs_tol: float, tp_max: float, sections: list[dict], hit_time_s: float, loop: bool,
             mix_path: str | None = None, mp3_tp: float | None = None, ffmpeg: str = "ffmpeg",
             extra_files: dict[str, np.ndarray] | None = None) -> dict:
    """Return {"passed": bool, "failures": [...], "metrics": {...}}. Thresholds are the brief's."""
    files = {"mix": mix, **{f"stems/{k}": v for k, v in stems.items()}, **(extra_files or {})}
    lengths = length_errors(files, expected_len, sr)
    lufs = integrated_lufs(mix, sr)
    tp = true_peak_dbtp(mix)
    ext = ffmpeg_ebur128(mix_path, ffmpeg) if mix_path else {}
    bounds = [s["applied_start_s"] for s in sections[1:]]
    clicks = click_report(mix, sr, bounds)
    end_t = len(mix) / sr if loop else hit_time_s
    gaps = gap_report(mix, sr, 0.1, end_t)
    ending = ending_report(mix, sr, None if loop else hit_time_s)
    align = section_alignment_report(mix, sr, sections)
    seam = loop_seam_report(mix, sr) if loop else None
    sdiff = sum_diff_db(list(stems.values()), mix)
    m = {
        "length_error_s": max(lengths.values()),
        "length_error_samples": int(round(max(lengths.values()) * sr)),
        "sum_diff_db": round(sdiff, 2),
        "integrated_lufs": round(lufs, 3),
        "true_peak_dbtp": round(tp, 3),
        "ffmpeg": ext,
        "ffmpeg_lufs_delta": None if ext.get("integrated_lufs") is None else round(ext["integrated_lufs"] - lufs, 3),
        "mp3_true_peak_dbtp": None if mp3_tp is None else round(mp3_tp, 3),
        "full_scale_samples": full_scale_samples(mix),
        "clicks": clicks["clicks"],
        "click_detail": clicks,
        "gaps": gaps["gaps"],
        "gap_detail": gaps,
        "ending": ending,
        "section_alignment": align,
        "loop_seam": seam,
    }
    f = []
    if m["length_error_samples"] != 0:
        f.append("length")
    if sdiff > -90:
        f.append("sum_diff")
    if abs(lufs - target_lufs) > lufs_tol:
        f.append("lufs")
    if ext.get("integrated_lufs") is not None and abs(ext["integrated_lufs"] - target_lufs) > 1.0:
        f.append("lufs_ffmpeg")
    if tp > tp_max or (ext.get("true_peak_dbtp") is not None and ext["true_peak_dbtp"] > tp_max):
        f.append("true_peak")
    if mp3_tp is not None and mp3_tp > tp_max:
        f.append("mp3_true_peak")
    if m["full_scale_samples"]:
        f.append("full_scale")
    if clicks["clicks"]:
        f.append("clicks")
    if gaps["gaps"]:
        f.append("gaps")
    if not loop and not (ending["silent_end"] and ending.get("hit_onset", True)):
        f.append("ending")
    if align["misaligned"]:
        f.append("section_alignment")
    if seam and seam["click"]:
        f.append("loop_seam")
    return {"passed": not f, "failures": f, "metrics": m}
