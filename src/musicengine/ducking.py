"""Narration ducking: energy VAD -> gain curve (attack before speech, smooth release) -> mix_ducked.wav.
Also the SSRF-guarded narration fetch."""
import ipaddress
import os
import socket
from urllib.parse import urljoin, urlparse

import httpx
import numpy as np

from .config import Settings, get_settings
from .errors import warning

FRAME_S = 0.02
GRID_HZ = 100
MIN_SPEECH_S = 0.15
HYSTERESIS_DB = 3.0


# ---------------------------------------------------------------- VAD
def detect_speech(mono: np.ndarray, sr: int, bridge_gap_s: float) -> tuple[list[tuple[float, float]], dict]:
    f = int(FRAME_S * sr)
    n = len(mono) // f
    if n == 0:
        return [], {"threshold_db": None, "noise_floor_db": None}
    e = 10 * np.log10(np.mean(mono[: n * f].reshape(n, f) ** 2, axis=1) + 1e-12)
    floor = float(np.percentile(e, 10))
    on = max(floor + 10.0, -45.0)
    off = on - HYSTERESIS_DB
    segs, active, start = [], False, 0
    for i, v in enumerate(e):
        if not active and v >= on:
            active, start = True, i
        elif active and v < off:
            active = False
            segs.append((start * FRAME_S, i * FRAME_S))
    if active:
        segs.append((start * FRAME_S, n * FRAME_S))
    # bridge short gaps between words so the music does not pump, then drop blips
    bridged: list[list[float]] = []
    for a, b in segs:
        if bridged and a - bridged[-1][1] < bridge_gap_s:
            bridged[-1][1] = b
        else:
            bridged.append([a, b])
    out = [(round(a, 3), round(b, 3)) for a, b in bridged if b - a >= MIN_SPEECH_S]
    return out, {"threshold_db": round(on, 2), "noise_floor_db": round(floor, 2)}


# ---------------------------------------------------------------- curve
def gain_curve_db(segments: list[tuple[float, float]], duration_s: float, depth_db: float,
                  attack_ms: float, release_ms: float) -> np.ndarray:
    """dB gain on a 100 Hz grid. Raised-cosine ramps: attack ends at speech onset, release starts at
    speech end. Overlapping ramps take the deeper value, so every transition is monotonic."""
    n = int(np.ceil(duration_s * GRID_HZ)) + 1
    t = np.arange(n) / GRID_HZ
    g = np.zeros(n)
    att, rel = attack_ms / 1000, release_ms / 1000
    for a, b in segments:
        seg = np.zeros(n)
        inside = (t >= a) & (t <= b)
        seg[inside] = -depth_db
        ra = (t >= a - att) & (t < a)
        seg[ra] = -depth_db * (1 - np.cos(np.pi * (t[ra] - (a - att)) / att)) / 2
        rr = (t > b) & (t <= b + rel)
        seg[rr] = -depth_db * (1 + np.cos(np.pi * (t[rr] - b) / rel)) / 2
        g = np.minimum(g, seg)
    return g


def breakpoints(curve_db: np.ndarray) -> list[dict]:
    """Only the points where the curve changes (start, end, and every point inside a ramp edge)."""
    out = []
    for i, v in enumerate(curve_db):
        prev = curve_db[i - 1] if i else None
        nxt = curve_db[i + 1] if i + 1 < len(curve_db) else None
        if prev is None or nxt is None or not (abs(v - prev) < 1e-9 and abs(v - nxt) < 1e-9):
            if out and abs(out[-1]["db"] - v) < 1e-9 and nxt is not None and abs(nxt - v) < 1e-9:
                continue
            out.append({"t": round(i / GRID_HZ, 3), "db": round(float(v), 3)})
    return out


def apply_curve(mix: np.ndarray, sr: int, curve_db: np.ndarray) -> np.ndarray:
    t_audio = np.arange(len(mix)) / sr
    t_grid = np.arange(len(curve_db)) / GRID_HZ
    gain = 10 ** (np.interp(t_audio, t_grid, curve_db) / 20)
    return mix * gain[:, None]


def duck(mix: np.ndarray, sr: int, narration_16k: np.ndarray, s: Settings | None = None) -> tuple[np.ndarray, dict, list[dict]]:
    s = s or get_settings()
    D = len(mix) / sr
    warnings: list[dict] = []
    nar_len = len(narration_16k) / 16000
    if nar_len > D + 1e-3:
        warnings.append(warning("NARRATION_TRUNCATED",
                                f"Narration is {nar_len:.2f}s but the music is {D:.2f}s; speech after the end "
                                f"is ignored.", narration_s=round(nar_len, 3)))
        narration_16k = narration_16k[: int(D * 16000)]
    segs, vad = detect_speech(narration_16k, 16000, s.duck_bridge_gap_s)
    curve = gain_curve_db(segs, D, s.duck_db, s.duck_attack_ms, s.duck_release_ms)
    info = {"applied": bool(segs), "depth_db": s.duck_db, "attack_ms": s.duck_attack_ms,
            "release_ms": s.duck_release_ms, "bridge_gap_s": s.duck_bridge_gap_s, "vad": vad,
            "segments": [{"start_s": a, "end_s": b} for a, b in segs], "curve": breakpoints(curve),
            "narration_s": round(nar_len, 3), "assumption": "narration starts at t=0"}
    if not segs:
        warnings.append(warning("NARRATION_NO_SPEECH", "No speech detected in the narration; "
                                "mix_ducked.wav equals mix.wav."))
        return mix.copy(), info, warnings
    return apply_curve(mix, sr, curve), info, warnings


# ---------------------------------------------------------------- fetch (SSRF-guarded)
class FetchError(Exception):
    pass


def check_public_url(url: str, allow_private: bool = False) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise FetchError("only http(s) URLs with a host are allowed")
    if allow_private:
        return
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror as e:
        raise FetchError(f"cannot resolve host: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
                or ip.is_unspecified or (ip.version == 6 and ip.ipv4_mapped and not ip.ipv4_mapped.is_global)):
            raise FetchError(f"address {ip} is not public")


def fetch_url(url: str, dest: str, s: Settings | None = None, max_redirects: int = 3) -> str:
    s = s or get_settings()
    limit = s.max_narration_mb * 1024 * 1024
    for _ in range(max_redirects + 1):
        check_public_url(url, s.allow_private_urls)
        with httpx.Client(timeout=s.narration_fetch_timeout_s, follow_redirects=False) as c:
            with c.stream("GET", url) as r:
                if r.is_redirect:
                    url = urljoin(url, r.headers.get("location", ""))
                    continue
                if r.status_code != 200:
                    raise FetchError(f"HTTP {r.status_code}")
                if int(r.headers.get("content-length") or 0) > limit:
                    raise FetchError("narration too large")
                size = 0
                with open(dest, "wb") as fh:
                    for chunk in r.iter_bytes():
                        size += len(chunk)
                        if size > limit:
                            raise FetchError("narration too large")
                        fh.write(chunk)
                return dest
    raise FetchError("too many redirects")


def fetch_narration(url: str, work_dir: str, storage=None, s: Settings | None = None) -> str:
    dest = os.path.join(work_dir, "narration.input")
    if url.startswith("upload://"):
        from .storage import get_storage

        upload_id = url.removeprefix("upload://")
        (storage or get_storage()).get_file(f"uploads/{upload_id}", dest)
        return dest
    return fetch_url(url, dest, s)
