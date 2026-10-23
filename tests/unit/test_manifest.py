import hashlib
import json
import os
import shutil

import numpy as np
import pytest
import soundfile as sf

from musicengine import ducking, manifest, mixdown, qa
from musicengine.config import Settings
from musicengine.schemas import MusicRequest
from musicengine.worker.pipeline import run_generate, run_regenerate
from tests_helpers import RENDERER

S = Settings(renderer=RENDERER)
REQUIRED = ["schema_version", "ai_generated", "job_id", "parent_job_id", "request", "seed", "stem_seeds",
            "tempo_bpm", "key", "time_signature", "duration_s", "sample_rate", "sections", "bars", "beats",
            "hit_time_s", "loop", "stems", "master_gain_db", "limiter", "loudness", "qa", "ducking",
            "providers", "components", "timings_s", "cost", "warnings"]


def gen(tmp_path, **req):
    r = MusicRequest(**{"prompt": "calm cinematic piano that builds to an uplifting peak", "duration_s": 20,
                        "seed": 9, **req})
    return run_generate("job-test", r, str(tmp_path), S)


def test_manifest_has_every_field_and_licences(tmp_path):
    out = gen(tmp_path, sections=[{"start_s": 0, "mood": "calm intro"}, {"start_s": 8, "mood": "build"},
                                  {"start_s": 14, "mood": "uplifting peak"}])
    m = out["manifest"]
    for k in REQUIRED:
        assert k in m, k
    assert m["ai_generated"] is True
    assert {c["name"] for c in m["components"]} == {c["name"] for c in manifest.components()}
    assert all(c["licence"] and c["licence_url"] and c["commercial_use"] for c in m["components"])
    assert [s["name"] for s in m["stems"]] == ["drums", "bass", "harmony", "melody"]
    assert all(s["gain"] == 1.0 for s in m["stems"])
    assert m["cost"]["api_fees_usd"] == 0 and m["cost"]["compute_seconds"] > 0
    assert set(m["timings_s"]) >= {"interpret", "plan", "compose", "render", "mix", "encode", "total"}
    assert m["qa"]["passed"] and m["qa"]["length_error_s"] == 0
    json.dumps(m)  # serialisable


def test_grid_matches_render(tmp_path):
    out = gen(tmp_path, tempo_bpm=120, duration_s=12)
    m = out["manifest"]
    beats = [b["t"] for b in m["beats"]]
    assert np.allclose(np.diff(beats), 0.5)
    assert m["hit_time_s"] == pytest.approx(beats[-1])
    assert m["hit_time_s"] == pytest.approx(len(m["bars"]) * 2.0 - 2.0)  # hit on the last listed bar line
    mix, sr = sf.read(out["files"]["mix.wav"])
    assert len(mix) == m["length_samples"] == 12 * 48000
    rep = qa.ending_report(mix, sr, m["hit_time_s"])
    assert rep["hit_onset"]


def test_loop_seam_and_no_hit(tmp_path):
    out = gen(tmp_path, duration_s=16, loopable=True, prompt="chill lo-fi beats")
    m = out["manifest"]
    assert m["loop"]["enabled"] and m["hit_time_s"] is None
    assert "LOOP_IGNORES_ENDING" in [w["code"] for w in m["warnings"]]
    mix, sr = sf.read(out["files"]["mix.wav"], always_2d=True)
    seam = qa.loop_seam_report(mix, sr)
    assert not seam["click"]
    # beat phase: the loop is an integer number of bars, so beat grid continues across the joint
    bar = 240 / m["tempo_bpm"]
    assert abs(m["loop"]["bars"] * bar - m["duration_s"]) * sr < 1


def test_regenerate_one_stem_keeps_others_byte_identical(tmp_path):
    parent_dir = tmp_path / "parent"
    out = gen(parent_dir, duration_s=15)
    pm = out["manifest"]
    pm["job_id"] = "parent-job"
    before = {f: hashlib.sha256(open(p, "rb").read()).hexdigest() for f, p in out["files"].items()
              if f.startswith("stems/")}
    child = run_regenerate("child-job", pm, str(parent_dir), "drums", None, str(tmp_path / "child"), S)
    cm = child["manifest"]
    assert cm["parent_job_id"] == "parent-job" and cm["regenerated_stem"] == "drums"
    assert cm["stem_seeds"]["drums"] != pm["stem_seeds"]["drums"]
    assert all(cm["stem_seeds"][k] == pm["stem_seeds"][k] for k in ("bass", "harmony", "melody"))
    assert child["reused_stems"] == ["bass", "harmony", "melody"]
    after = {k: hashlib.sha256(open(p, "rb").read()).hexdigest() for k, p in out["files"].items()
             if k.startswith("stems/")}
    assert before == after  # parent files untouched
    new = open(child["files"]["stems/drums.wav"], "rb").read()
    assert hashlib.sha256(new).hexdigest() != before["stems/drums.wav"]
    assert cm["qa"]["passed"]
    assert abs(cm["loudness"]["integrated_lufs"] - pm["loudness"]["target_lufs"]) <= 1.0
    assert cm["loudness"]["true_peak_dbtp"] <= -1.0


def test_narration_in_pipeline(tmp_path, monkeypatch):
    sr16 = 16000
    rng = np.random.default_rng(1)
    nar = rng.standard_normal(10 * sr16) * 0.0003
    nar[2 * sr16:5 * sr16] += rng.standard_normal(3 * sr16) * 0.1
    src = tmp_path / "narr.wav"
    sf.write(src, nar, sr16)

    def fake_fetch(url, work, storage=None, s=None):
        dst = os.path.join(work, "narration.input")
        shutil.copy(src, dst)
        return dst

    monkeypatch.setattr(ducking, "fetch_narration", fake_fetch)
    out = gen(tmp_path / "job", duration_s=10, narration_url="https://example.com/n.wav")
    m = out["manifest"]
    assert m["ducking"]["applied"] and m["ducking"]["depth_db"] == 12
    assert m["ducking"]["segments"][0]["start_s"] == pytest.approx(2.0, abs=0.05)
    ducked, _ = mixdown.read_wav(out["files"]["mix_ducked.wav"])
    assert len(ducked) == 10 * 48000
    assert m["ducking"]["true_peak_dbtp"] <= m["loudness"]["true_peak_dbtp"] + 0.01


def test_narration_fetch_failure_degrades(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ducking.FetchError("address 127.0.0.1 is not public")

    monkeypatch.setattr(ducking, "fetch_narration", boom)
    out = gen(tmp_path, duration_s=8, narration_url="http://127.0.0.1/x.wav")
    assert "mix_ducked.wav" not in out["files"]
    assert "NARRATION_FETCH_FAILED" in [w["code"] for w in out["warnings"]]
