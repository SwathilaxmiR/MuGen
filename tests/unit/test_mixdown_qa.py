import numpy as np
import pytest

from musicengine import mixdown, qa
from musicengine.config import Settings
from musicengine.interpreter import interpret
from musicengine.planner.plan import make_plan
from musicengine.schemas import MusicRequest
from musicengine.worker.pipeline import Timer, produce_audio
from tests_helpers import RENDERER

CASES = [  # (prompt, duration, target LUFS) : all 12 presets, D 5..180 s
    ("Epic cinematic orchestral score that builds to a heroic climax", 45, -16),
    ("chill lo-fi beats for studying late at night", 30, -14),
    ("upbeat corporate background for a tech product explainer", 20, -16),
    ("energetic EDM festival track with a big drop", 60, -14),
    ("warm acoustic guitar folk for a travel vlog", 12, -23),
    ("tense suspense thriller underscore, dark and ominous", 30, -16),
    ("playful quirky cartoon music for kids", 5, -16),
    ("calm ambient meditation pad, peaceful and serene", 90, -23),
    ("driving rock with guitar riffs for a sports montage", 10, -16),
    ("smooth jazz lounge with saxophone", 180, -16),
    ("happy cheerful summer celebration", 6, -16),
    ("massive trailer battle music, epic and powerful", 15, -16),
]


def run_case(tmp_path, prompt, D, lufs, renderer=RENDERER, **kw):
    s = Settings(renderer=renderer)
    req = MusicRequest(prompt=prompt, duration_s=D, seed=21,
                       output={"target_lufs": lufs, "formats": ["wav", "mp3"]}, **kw)
    plan = make_plan(req, interpret(prompt)[0])
    res, paths, infos, report = produce_audio(plan, str(tmp_path), True, [], Timer(), s)
    return plan, res, paths, report


@pytest.mark.parametrize("prompt,D,lufs", CASES, ids=[c[0].split()[0] + f"-{c[1]}s" for c in CASES])
def test_qa_gate_passes(tmp_path, prompt, D, lufs):
    plan, res, paths, report = run_case(tmp_path, prompt, D, lufs)
    m = report["metrics"]
    assert report["passed"], report["failures"]
    assert m["length_error_samples"] == 0
    assert m["sum_diff_db"] < -90
    assert abs(m["integrated_lufs"] - lufs) <= 0.5
    assert m["true_peak_dbtp"] <= -1.0 and m["mp3_true_peak_dbtp"] <= -1.0
    assert abs(m["ffmpeg_lufs_delta"]) <= 0.2, m["ffmpeg"]
    assert m["clicks"] == 0 and m["gaps"] == 0
    assert m["ending"]["silent_end"] and m["ending"]["hit_onset"]
    assert set(res.gains.values()) == {1.0}


def test_limiter_never_exceeds_ceiling_on_hot_input():
    sr = 48000
    rng = np.random.default_rng(0)
    x = rng.standard_normal((sr * 3, 2)) * 0.3
    x[sr:sr + 50] *= 8  # spikes
    curve = mixdown.limiter_curve(x, sr, -1.5)
    y = x * curve[:, None]
    assert qa.true_peak_dbtp(y) <= -1.4
    assert curve.max() <= 1.0 and np.all(np.abs(np.diff(curve)) < 0.05)  # smooth


def test_click_detector_finds_a_real_discontinuity():
    sr = 48000
    t = np.arange(sr * 4) / sr
    x = 0.2 * np.sin(2 * np.pi * 220 * t)
    x = np.stack([x, x], axis=1)
    assert qa.click_report(x, sr, [2.0])["clicks"] == 0
    y = x.copy()
    y[2 * sr:] += 0.3  # DC step = click
    assert qa.click_report(y, sr, [2.0])["clicks"] == 1


def test_gap_detector():
    sr = 48000
    x = np.full((sr * 3, 2), 0.05)
    assert qa.gap_report(x, sr, 0.1, 2.9)["gaps"] == 0
    x[sr:sr + sr // 4] = 0
    assert qa.gap_report(x, sr, 0.1, 2.9)["gaps"] > 0


def test_sum_diff_after_24bit_roundtrip(tmp_path):
    plan, res, paths, report = run_case(tmp_path, "upbeat corporate", 8, -16)
    mix, _ = mixdown.read_wav(paths["mix_wav"])
    stems = [mixdown.read_wav(p)[0] for p in paths["stems"].values()]
    assert qa.sum_diff_db(stems, mix) < -100
