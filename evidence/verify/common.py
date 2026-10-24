"""Shared helpers for the evidence verifiers. Verifiers read delivered files (WAV, mp3, manifest) only."""
import csv
import glob
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import soundfile as sf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EV = os.path.join(ROOT, "evidence")
sys.path.insert(0, os.path.join(ROOT, "src"))

VERDICTS = os.path.join(EV, "verdicts.json")
VALID = {"PASS", "PARTIAL", "FAIL", "NOT_RUN", "PENDING_HUMAN", "HUMAN", "INFO"}


def run_id() -> str:
    return os.environ.get("EVIDENCE_RUN") or open(os.path.join(EV, "runs", "LATEST")).read().strip()


def runs_dir() -> str:
    return os.path.join(EV, "runs", run_id())


def audio_dir() -> str:
    return os.path.join(ROOT, "out", "evidence", run_id())


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


def git_sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()


def tool_versions() -> dict:
    ff = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()
    return {"python": platform.python_version(), "ffmpeg": ff[0] if ff else "missing", "numpy": np.__version__,
            "soundfile": sf.__version__, "platform": platform.platform()}


def out_dir(*parts: str) -> str:
    d = os.path.join(EV, *parts)
    os.makedirs(d, exist_ok=True)
    return d


def write_csv(path: str, rows: list[dict], cols: list[str] | None = None) -> str:
    cols = cols or (list(rows[0]) if rows else ["empty"])
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def cases(prefix: str | None = None, succeeded_only: bool = True) -> list[dict]:
    """Every stored case of the current run: {name, dir, audio, manifest, status, request, extra}."""
    out = []
    for d in sorted(glob.glob(os.path.join(runs_dir(), "*"))):
        if not os.path.isdir(d):
            continue
        name = os.path.basename(d)
        if prefix and not name.startswith(prefix):
            continue
        st = json.load(open(os.path.join(d, "status.json"))) if os.path.exists(os.path.join(d, "status.json")) else {}
        man = os.path.join(d, "music_manifest.json")
        if succeeded_only and not os.path.exists(man):
            continue
        a = os.path.join(audio_dir(), name.split("__regen_")[0])
        if "__regen_" in name:
            a = os.path.join(a, "regen_" + name.split("__regen_")[1])
        out.append({"name": name, "dir": d, "audio": a, "status": st,
                    "manifest": json.load(open(man)) if os.path.exists(man) else None,
                    "request": json.load(open(os.path.join(d, "request.json"))),
                    "extra": json.load(open(os.path.join(d, "extra.json"))) if os.path.exists(os.path.join(d, "extra.json")) else {}})
    return out


def audio_files(case: dict) -> dict[str, str]:
    """Delivered audio files of one case (mix, mp3, ducked, stems)."""
    files = {}
    for p in ["mix.wav", "mix.mp3", "mix_ducked.wav"] + [f"stems/{s}.wav" for s in ("drums", "bass", "harmony", "melody")]:
        full = os.path.join(case["audio"], p)
        if os.path.exists(full):
            files[p] = full
    return files


def read(path: str) -> tuple[np.ndarray, int]:
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    return x, sr


def ffmpeg_meter(path: str) -> dict:
    """Independent loudness/true-peak meter (ffmpeg ebur128)."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    s = p.stderr[p.stderr.rfind("Summary:"):]

    def g(label):
        m = re.search(label + r":\s+(-?[\d.]+|-inf)", s)
        return None if not m or m.group(1) == "-inf" else float(m.group(1))

    return {"I": g("I"), "LRA": g("LRA"), "TP": g("Peak")}


def ffmpeg_decode(path: str, sr: int) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True, timeout=300)
    return np.frombuffer(p.stdout, dtype=np.float32).reshape(-1, 2)


def to_mp3(x: np.ndarray, sr: int, path: str, kbps: int = 128) -> str:
    """Small listening clips for the committed evidence (the full WAVs are in audio-pack.zip)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp.wav"
    sf.write(tmp, np.clip(x, -1, 1), sr, subtype="PCM_16")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", tmp, "-b:a", f"{kbps}k", path], check=True)
    os.remove(tmp)
    return path


# ---------------------------------------------------------------- verdicts
def verdict(key: str, sheet: str, cell: str, verdict_: str, value: str, note: str, evidence: list[str],
            data: dict | None = None) -> dict:
    assert verdict_ in VALID, verdict_
    missing = [e for e in evidence if not e.startswith("http") and not e.startswith("VIDEO@")
               and not os.path.exists(os.path.join(ROOT, e.split(" ")[0].split("::")[0]))]
    if missing and verdict_ == "PASS":
        verdict_, note = "PARTIAL", f"{note} [downgraded: evidence missing {missing}]"
    entry = {"key": key, "sheet": sheet, "cell": cell, "verdict": verdict_, "value": value, "note": note,
             "evidence": evidence, "git_sha": git_sha(), "run_id": run_id(),
             "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tools": tool_versions()}
    if data is not None:
        entry["data"] = data
    allv = json.load(open(VERDICTS)) if os.path.exists(VERDICTS) else {}
    allv[key] = entry
    with open(VERDICTS, "w") as fh:
        json.dump(allv, fh, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(f"  {key:28s} {verdict_:14s} {value[:90]}")
    return entry


def jsonable(x):
    from musicengine.manifest import jsonable as j

    return j(x)
