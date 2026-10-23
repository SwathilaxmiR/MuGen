"""The generation pipeline (no DB / HTTP here): interpret -> plan -> compose -> render -> mix -> QA."""
import json
import os
import resource
import time
from collections.abc import Callable

import numpy as np

from .. import ducking, manifest, mixdown, qa
from ..composer.registry import STEM_REGISTRY, compose_stem, reseed
from ..config import Settings, get_settings
from ..errors import JobError, warning
from ..interpreter import interpret
from ..logging import get_logger
from ..planner.plan import Plan, make_plan
from ..renderer import render_stem
from ..schemas import MusicRequest

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
    mp3_tp = mixdown.mp3_true_peak(paths["mix_mp3"], sr, len(mix), s) if paths.get("mix_mp3") else None
    g = plan.g
    return qa.run_gate(mix, {}, sr, expected_len=g.length_samples, target_lufs=plan.target_lufs,
                       lufs_tol=s.lufs_tol, tp_max=-1.0, sections=plan.sections, hit_time_s=g.hit_time_s,
                       loop=g.loop, mix_path=paths["mix_wav"], mp3_tp=mp3_tp, ffmpeg=s.ffmpeg_bin,
                       extra_files=extra, stem_paths=paths["stems"])


def produce_audio(plan: Plan, out_dir: str, want_mp3: bool, warnings: list[dict], timer: Timer,
                  s: Settings | None = None, progress: Progress = lambda p, m: None,
                  pre_rendered: dict[str, np.ndarray] | None = None) -> tuple[mixdown.MixResult, dict, dict, dict]:
    """Returns (mix result, file paths, render infos, qa report). One automatic retry on QA failure."""
    s = s or get_settings()
    infos = {}
    if pre_rendered is None:
        audio, infos, _ = render_all(plan, warnings, timer, s, progress)
    else:
        audio = {k: v.copy() for k, v in pre_rendered.items()}
    ceiling = s.tp_ceiling_dbtp
    report = None
    for attempt in (1, 2):
        if attempt == 2:  # master() works in place, so the retry re-renders (deterministic, rare)
            if pre_rendered is None:
                audio, infos, _ = render_all(plan, [], timer, s, progress)
            else:
                audio = {k: v.copy() for k, v in pre_rendered.items()}
        t0 = time.perf_counter()
        res = mixdown.master(audio, plan, s, ceiling_dbtp=ceiling)
        timer.add("mix", time.perf_counter() - t0)
        t0 = time.perf_counter()
        paths = mixdown.write_outputs(res, out_dir, plan.sample_rate, want_mp3, s)
        timer.add("encode", time.perf_counter() - t0)
        res.stems, audio = {}, None  # written to disk; keep only the mix (needed for ducking)
        progress(80, "mixed")
        t0 = time.perf_counter()
        report = gate_files(paths, plan, s)
        timer.add("qa", time.perf_counter() - t0)
        report["attempt"] = attempt
        res.loudness["lra"] = report["metrics"]["ffmpeg"].get("lra")
        if report["passed"]:
            return res, paths, infos, report
        log.warning("qa_failed", attempt=attempt, failures=report["failures"])
        ceiling -= 0.5  # retry with more headroom (fixes TP / mp3 overshoot)
    raise JobError("MIX_QA_FAILED", f"Mix failed QA after retry: {', '.join(report['failures'])}",
                   retryable=True, details={"failures": report["failures"],
                                            "metrics": manifest.jsonable(report["metrics"])})


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


# ====================================================================== full jobs


def _cpu() -> float:
    a, b = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def _dedupe(ws: list[dict]) -> list[dict]:
    seen, out = set(), []
    for w in ws:
        k = json.dumps(w, sort_keys=True, default=str)
        if k not in seen:
            seen.add(k)
            out.append(w)
    return out


def _save_master_state(path: str, res: mixdown.MixResult) -> None:
    np.savez_compressed(path, curve=res.curve.astype(np.float32), master_gain_db=res.master_gain_db,
                        balance=json.dumps(res.balance_db))


def _ducking_step(mix: np.ndarray, plan: Plan, url: str, work: str, s: Settings, warnings: list[dict],
                  timer: Timer) -> tuple[str | None, dict]:
    t0 = time.perf_counter()
    info = {"applied": False, "depth_db": s.duck_db, "segments": [], "curve": []}
    try:
        src = ducking.fetch_narration(url, work, s=s)
        narration = mixdown.decode_audio(src, plan.sample_rate, s, mono16k=True)
    except Exception as e:  # noqa: BLE001 - degrade, don't fail the job
        warnings.append(warning("NARRATION_FETCH_FAILED", f"Could not fetch/decode narration ({type(e).__name__}: "
                                f"{str(e)[:160]}); returned music without mix_ducked.wav."))
        timer.add("ducking", time.perf_counter() - t0)
        return None, info
    ducked, info, w = ducking.duck(mix, plan.sample_rate, narration, s)
    warnings += w
    path = os.path.join(work, "mix_ducked.wav")
    mixdown.write_wav(path, ducked, plan.sample_rate)
    info["true_peak_dbtp"] = round(qa.true_peak_dbtp(ducked), 3)
    timer.add("ducking", time.perf_counter() - t0)
    return path, info


def run_generate(job_id: str, req: MusicRequest, work: str, s: Settings | None = None,
                 progress: Progress = lambda p, m: None) -> dict:
    """Run the whole job locally into `work`. Returns {"files": {key: path}, "manifest": dict, "warnings": []}."""
    s = s or get_settings()
    cpu0, t_start = _cpu(), time.perf_counter()
    timer, warnings = Timer(), []
    t0 = time.perf_counter()
    spec, w, interp_info = interpret(req.prompt)
    warnings += w
    timer.add("interpret", time.perf_counter() - t0)
    progress(5, "interpreted")
    t0 = time.perf_counter()
    plan = make_plan(req, spec)
    warnings += plan.warnings
    timer.add("plan", time.perf_counter() - t0)
    progress(10, "planned")

    res, paths, infos, report = produce_audio(plan, work, "mp3" in req.output.formats, warnings, timer, s, progress)
    files = {"mix.wav": paths["mix_wav"], **{f"stems/{k}.wav": p for k, p in paths["stems"].items()}}
    if paths.get("mix_mp3"):
        files["mix.mp3"] = paths["mix_mp3"]

    duck_info = {"applied": False, "depth_db": None, "segments": [], "curve": [], "requested": False}
    if req.narration_url:
        progress(85, "ducking")
        ducked_path, duck_info = _ducking_step(res.mix, plan, req.narration_url, work, s, warnings, timer)
        duck_info["requested"] = True
        if ducked_path:
            x, _ = mixdown.read_wav(ducked_path)
            if len(x) != plan.g.length_samples:
                raise JobError("MIX_QA_FAILED", "mix_ducked.wav length mismatch")
            files["mix_ducked.wav"] = ducked_path

    plan_path = os.path.join(work, "plan.json")
    with open(plan_path, "w") as fh:
        json.dump(plan.to_dict(), fh)
    files["plan.json"] = plan_path
    _save_master_state(os.path.join(work, "master.npz"), res)
    files["master.npz"] = os.path.join(work, "master.npz")

    parts_meta = [manifest.stem_entry(k, plan.preset.programs[k], k == "drums", infos.get(k, {}), plan.stem_seeds[k])
                  for k in paths["stems"]]
    providers = [interp_info] + [{"role": "renderer", "name": n, "version": v, "mode": "local subprocess"
                                  if n == "fluidsynth" else "local"}
                                 for n, v in sorted({(i["renderer"], i["version"]) for i in infos.values()})]
    timer.add("total", time.perf_counter() - t_start)
    warnings = _dedupe(warnings)
    m = manifest.build(job_id=job_id, parent_job_id=None, regenerated_stem=None,
                       request=req.model_dump(mode="json"), plan=plan, stems=parts_meta,
                       master_gain_db=res.master_gain_db, limiter=res.limiter, loudness=res.loudness,
                       qa_metrics=manifest.qa_summary(report), ducking=duck_info, providers=providers,
                       timings=timer.t, compute_seconds=_cpu() - cpu0, warnings=warnings)
    return {"files": files, "manifest": m, "warnings": warnings, "work": work}


def run_regenerate(job_id: str, parent_manifest: dict, parent_dir: str, stem: str, seed: int | None, work: str,
                   s: Settings | None = None, progress: Progress = lambda p, m: None) -> dict:
    """Regenerate one stem. `parent_dir` holds the parent's plan.json, master.npz and stems/*.wav.
    Other stems are reused unchanged (the worker copies their objects byte-for-byte)."""
    s = s or get_settings()
    cpu0, t_start = _cpu(), time.perf_counter()
    timer, warnings = Timer(), []
    with open(os.path.join(parent_dir, "plan.json")) as fh:
        plan = Plan.from_dict(json.load(fh))
    state = np.load(os.path.join(parent_dir, "master.npz"))
    curve = state["curve"].astype(np.float64)
    new_seed = reseed(plan, stem, seed)
    progress(10, "reseeded")
    sr = plan.sample_rate
    audio, infos, _ = render_all(plan, warnings, timer, s, progress, stems=[stem], p0=15, p1=60)
    t0 = time.perf_counter()
    env = mixdown.ending_envelope(plan)[:, None]
    new_pre = audio[stem] * env * curve[:, None]
    old, _ = mixdown.read_wav(os.path.join(parent_dir, "stems", f"{stem}.wav"))
    l_old, l_new = qa.integrated_lufs(old, sr), qa.integrated_lufs(new_pre, sr)
    k_db = 0.0 if l_new <= -70 or l_old <= -70 else l_old - l_new  # loudness-match the replaced stem
    others = {n: mixdown.read_wav(os.path.join(parent_dir, "stems", f"{n}.wav"))[0]
              for n in parent_manifest_stems(parent_manifest) if n != stem}
    new = new_pre * 10 ** (k_db / 20)
    trims = 0
    others_sum = np.zeros_like(new)
    for v in others.values():
        others_sum += v
    while True:
        mix = new + others_sum
        tp = qa.true_peak_dbtp(mix)
        if tp <= -1.0 - 0.05 or trims >= 12:
            break
        new *= 10 ** (-0.5 / 20)  # lower only the new stem
        trims += 1
    timer.add("mix", time.perf_counter() - t0)
    progress(75, "mixed")
    os.makedirs(os.path.join(work, "stems"), exist_ok=True)
    new_path = os.path.join(work, "stems", f"{stem}.wav")
    mixdown.write_wav(new_path, new, sr)
    mix_path = os.path.join(work, "mix.wav")
    # mix from the exact samples that will be stored (24-bit stems)
    stored_new, _ = mixdown.read_wav(new_path)
    mix = stored_new + others_sum
    mixdown.write_wav(mix_path, mix, sr)
    del mix, others_sum
    paths = {"mix_wav": mix_path, "stems": {**{n: os.path.join(parent_dir, "stems", f"{n}.wav") for n in others},
                                            stem: new_path}}
    want_mp3 = "mp3" in parent_manifest["request"]["output"]["formats"]
    if want_mp3:
        paths["mix_mp3"] = os.path.join(work, "mix.mp3")
        mixdown.encode_mp3(mix_path, paths["mix_mp3"], s)
    t0 = time.perf_counter()
    s_regen = s.model_copy(update={"lufs_tol": 1.0})  # brief tolerance; the new stem may shift loudness
    report = gate_files(paths, plan, s_regen)
    timer.add("qa", time.perf_counter() - t0)
    if not report["passed"]:
        raise JobError("MIX_QA_FAILED", f"Regenerated mix failed QA: {', '.join(report['failures'])}",
                       details={"failures": report["failures"]})
    loud = {"integrated_lufs": report["metrics"]["integrated_lufs"],
            "true_peak_dbtp": report["metrics"]["true_peak_dbtp"],
            "lra": report["metrics"]["ffmpeg"].get("lra"), "target_lufs": plan.target_lufs}
    files = {"mix.wav": mix_path, f"stems/{stem}.wav": new_path, "plan.json": os.path.join(work, "plan.json")}
    if want_mp3:
        files["mix.mp3"] = paths["mix_mp3"]
    with open(files["plan.json"], "w") as fh:
        json.dump(plan.to_dict(), fh)
    stems_meta = []
    for e in parent_manifest["stems"]:
        if e["name"] == stem:
            e = manifest.stem_entry(stem, plan.preset.programs[stem], stem == "drums", infos[stem], new_seed)
            e["level_match_db"] = round(k_db, 3)
            e["tp_trim_db"] = -0.5 * trims
        stems_meta.append(e)
    duck_info = {"applied": False, "depth_db": None, "segments": [], "curve": [], "requested": False,
                 "note": "regenerate does not re-duck; request a new job with narration_url"}
    if trims:
        warnings.append(warning("REGEN_STEM_TRIMMED", f"New {stem} stem lowered {0.5 * trims:.1f} dB to keep "
                                "the true peak under -1 dBTP.", stem=stem, trim_db=-0.5 * trims))
    timer.add("total", time.perf_counter() - t_start)
    limiter = dict(parent_manifest["limiter"], reused_from_parent=True)
    providers = [{"role": "renderer", "name": i["renderer"], "version": i["version"], "mode": "local"}
                 for i in infos.values()]
    m = manifest.build(job_id=job_id, parent_job_id=parent_manifest["job_id"], regenerated_stem=stem,
                       request=parent_manifest["request"], plan=plan, stems=stems_meta,
                       master_gain_db=parent_manifest["master_gain_db"], limiter=limiter, loudness=loud,
                       qa_metrics=manifest.qa_summary(report), ducking=duck_info, providers=providers,
                       timings=timer.t, compute_seconds=_cpu() - cpu0, warnings=_dedupe(warnings))
    return {"files": files, "manifest": m, "warnings": m["warnings"], "reused_stems": sorted(others),
            "work": work}


def parent_manifest_stems(m: dict) -> list[str]:
    return [e["name"] for e in m["stems"]]
