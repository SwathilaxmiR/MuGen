"""music_manifest.json: the single place the manifest is built and validated."""
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pretty_midi
import yaml
from pydantic import BaseModel, ConfigDict

from .config import get_settings
from .planner.plan import Plan

SCHEMA_VERSION = "1.0"
AI_LABEL = "AI-generated instrumental music (rule-based symbolic composition rendered with sampled instruments)"
PRODUCTION = "symbolic MIDI -> {renderer} render + numpy FX"
DRUM_KITS = {0: "Standard Kit", 8: "Room Kit", 16: "Power Kit", 24: "Electronic Kit", 25: "TR-808 Kit",
             32: "Jazz Kit", 40: "Brush Kit", 48: "Orchestra Kit"}
LICENSES_PATH = Path(__file__).resolve().parents[2] / "licenses.yaml"


@lru_cache
def components() -> list[dict]:
    data = yaml.safe_load(LICENSES_PATH.read_text())
    return [{"name": c["name"], "version": str(c["version"]), "licence": c["licence"],
             "licence_url": c["licence_url"], "commercial_use": c["commercial_use"], "role": c.get("role", "")}
            for c in data["components"]]


class _Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


class StemEntry(_Loose):
    name: str
    file: str
    gain: float
    production: str
    program: int
    program_name: str
    soundfont: str | None
    renderer: str
    seed: int


class Manifest(BaseModel):
    """Every field from the brief; validated before upload."""
    model_config = ConfigDict(extra="forbid")
    schema_version: str
    ai_generated: bool
    ai_label: str
    job_id: str
    parent_job_id: str | None
    regenerated_stem: str | None
    request: dict
    seed: int
    stem_seeds: dict[str, int]
    style: str
    tempo_bpm: float
    key: dict
    time_signature: str
    duration_s: float
    sample_rate: int
    bit_depth: int
    length_samples: int
    sections: list[dict]
    bars: list[dict]
    beats: list[dict]
    hit_time_s: float | None
    loop: dict
    stems: list[StemEntry]
    mix_formula: str
    master_gain_db: float
    limiter: dict
    loudness: dict
    qa: dict
    ducking: dict
    providers: list[dict]
    components: list[dict]
    timings_s: dict[str, float]
    cost: dict[str, Any]
    warnings: list[dict]


def stem_entry(name: str, program: int, is_drum: bool, info: dict, seed: int) -> dict:
    s = get_settings()
    renderer = info.get("renderer", "unknown")
    return {"name": name, "file": f"stems/{name}.wav", "gain": 1.0,
            "production": PRODUCTION.format(renderer=renderer),
            "program": program,
            "program_name": DRUM_KITS.get(program, f"Drum kit {program}") if is_drum
            else pretty_midi.program_to_instrument_name(program),
            "soundfont": Path(s.soundfont_path).name if renderer == "fluidsynth" else None,
            "renderer": renderer, "renderer_version": info.get("version"), "fallback": info.get("fallback", False),
            "seed": seed}


def build(*, job_id: str, parent_job_id: str | None, regenerated_stem: str | None, request: dict, plan: Plan,
          stems: list[dict], master_gain_db: float, limiter: dict, loudness: dict, qa_metrics: dict,
          ducking: dict, providers: list[dict], timings: dict, compute_seconds: float,
          warnings: list[dict]) -> dict:
    s = get_settings()
    g = plan.g
    m = {
        "schema_version": SCHEMA_VERSION,
        "ai_generated": True,
        "ai_label": AI_LABEL,
        "job_id": job_id,
        "parent_job_id": parent_job_id,
        "regenerated_stem": regenerated_stem,
        "request": request,
        "seed": plan.seed,
        "stem_seeds": dict(plan.stem_seeds),
        "style": plan.style,
        "tempo_bpm": round(g.bpm, 4),
        "key": {"tonic": plan.key_name.split()[0], "mode": plan.mode, "name": plan.key_name},
        "time_signature": "4/4",
        "duration_s": g.duration_s,
        "sample_rate": plan.sample_rate,
        "bit_depth": 24,
        "length_samples": g.length_samples,
        "sections": plan.sections,
        "bars": g.bars(),
        "beats": g.beats(),
        "hit_time_s": None if g.loop else round(g.hit_time_s, 6),
        "loop": {"enabled": g.loop, "bars": g.n_bars if g.loop else None,
                 "seamless_method": "rendered twice back-to-back, second pass kept" if g.loop else None},
        "stems": stems,
        "mix_formula": "mix = sum(stems[i].gain * stems[i]) (stems stored post master gain and limiter)",
        "master_gain_db": master_gain_db,
        "limiter": limiter,
        "loudness": loudness,
        "qa": qa_metrics,
        "ducking": ducking,
        "providers": providers,
        "components": components(),
        "timings_s": timings,
        "cost": {"compute_seconds": round(compute_seconds, 3),
                 "usd_estimate": round(compute_seconds * s.cost_per_cpu_second, 6),
                 "cost_per_cpu_second_usd": s.cost_per_cpu_second, "api_fees_usd": 0.0},
        "warnings": warnings,
    }
    return Manifest.model_validate(jsonable(m)).model_dump(mode="json")


def jsonable(x):
    """numpy scalars/bools -> plain Python, recursively."""
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    return x


def qa_summary(report: dict) -> dict:
    m = report["metrics"]
    return {"passed": report["passed"], "failures": report["failures"], "attempt": report.get("attempt", 1),
            "length_error_s": m["length_error_s"], "sum_diff_db": m["sum_diff_db"],
            "integrated_lufs": m["integrated_lufs"], "true_peak_dbtp": m["true_peak_dbtp"],
            "ffmpeg_ebur128": m["ffmpeg"], "mp3_true_peak_dbtp": m["mp3_true_peak_dbtp"],
            "full_scale_samples": m["full_scale_samples"], "clicks": m["clicks"], "gaps": m["gaps"],
            "min_rms_db": m["gap_detail"]["min_rms_db"], "ending": m["ending"],
            "section_alignment": m["section_alignment"]["sections"], "loop_seam": m["loop_seam"]}
