"""The generation pipeline (no DB / HTTP here): interpret -> plan -> compose -> render -> mix -> QA."""
import os
import time
from collections.abc import Callable

import numpy as np

from .. import mixdown, qa
from ..composer.registry import STEM_REGISTRY, compose_stem
from ..config import Settings, get_settings
from ..errors import JobError
from ..logging import get_logger
from ..planner.plan import Plan
from ..renderer import render_stem

log = get_logger("pipeline")
Progress = Callable[[int, str], None]


class Timer:
    def __init__(self):
        self.t: dict[str, float] = {}

    def add(self, key: str, seconds: float):
        self.t[key] = round(self.t.get(key, 0.0) + seconds, 4)


def render_all(plan: Plan, warnings: list[dict], timer: Timer, s: Settings, progress: Progress,
               stems: list[str] | None = None, p0: int = 20, p1: int = 70) -> tuple[dict, dict, dict]:
    names = stems or list(STEM_REGISTRY)
    audio, infos, parts = {}, {}, {}
    for i, name in enumerate(names):
        t0 = time.perf_counter()
        parts[name] = compose_stem(plan, name)
        timer.add("compose", time.perf_counter() - t0)
        t0 = time.perf_counter()
        audio[name], infos[name] = render_stem(parts[name], plan, warnings, s)
        timer.add("render", time.perf_counter() - t0)
        progress(p0 + (p1 - p0) * (i + 1) // len(names), f"rendered {name}")
    return audio, infos, parts


def gate_files(paths: dict, plan: Plan, s: Settings, extra: dict | None = None) -> dict:
    sr = plan.sample_rate
    mix, _ = mixdown.read_wav(paths["mix_wav"])
    stems = {k: mixdown.read_wav(p)[0] for k, p in paths["stems"].items()}
    mp3_tp = mixdown.mp3_true_peak(paths["mix_mp3"], sr, len(mix), s) if paths.get("mix_mp3") else None
    g = plan.g
    return qa.run_gate(mix, stems, sr, expected_len=g.length_samples, target_lufs=plan.target_lufs,
                       lufs_tol=s.lufs_tol, tp_max=-1.0, sections=plan.sections, hit_time_s=g.hit_time_s,
                       loop=g.loop, mix_path=paths["mix_wav"], mp3_tp=mp3_tp, ffmpeg=s.ffmpeg_bin,
                       extra_files=extra)


def produce_audio(plan: Plan, out_dir: str, want_mp3: bool, warnings: list[dict], timer: Timer,
                  s: Settings | None = None, progress: Progress = lambda p, m: None,
                  pre_rendered: dict[str, np.ndarray] | None = None) -> tuple[mixdown.MixResult, dict, dict, dict]:
    """Returns (mix result, file paths, render infos, qa report). One automatic retry on QA failure."""
    s = s or get_settings()
    infos = {}
    if pre_rendered is None:
        audio, infos, _ = render_all(plan, warnings, timer, s, progress)
    else:
        audio = pre_rendered
    ceiling = s.tp_ceiling_dbtp
    report = None
    for attempt in (1, 2):
        t0 = time.perf_counter()
        res = mixdown.master(audio, plan, s, ceiling_dbtp=ceiling)
        timer.add("mix", time.perf_counter() - t0)
        t0 = time.perf_counter()
        paths = mixdown.write_outputs(res, out_dir, plan.sample_rate, want_mp3, s)
        timer.add("encode", time.perf_counter() - t0)
        progress(80, "mixed")
        t0 = time.perf_counter()
        report = gate_files(paths, plan, s)
        timer.add("qa", time.perf_counter() - t0)
        report["attempt"] = attempt
        if report["passed"]:
            return res, paths, infos, report
        log.warning("qa_failed", attempt=attempt, failures=report["failures"])
        ceiling -= 0.5  # retry with more headroom (fixes TP / mp3 overshoot)
    raise JobError("MIX_QA_FAILED", f"Mix failed QA after retry: {', '.join(report['failures'])}",
                   retryable=True, details={"failures": report["failures"],
                                            "metrics": _jsonable(report["metrics"])})


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path
