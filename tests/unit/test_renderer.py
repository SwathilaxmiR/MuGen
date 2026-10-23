import time

import numpy as np
import pytest

from musicengine.composer.registry import compose_all
from musicengine.config import Settings
from musicengine.errors import JobError
from musicengine.interpreter import interpret
from musicengine.planner.plan import make_plan
from musicengine.renderer import render_stem
from musicengine.schemas import MusicRequest


def plan_for(D=10.0, prompt="upbeat corporate background", **kw):
    req = MusicRequest(prompt=prompt, duration_s=D, seed=2, **kw)
    return make_plan(req, interpret(prompt)[0])


def _render_all(plan, s):
    warnings, out, infos = [], {}, {}
    t0 = time.perf_counter()
    for name, part in compose_all(plan).items():
        out[name], infos[name] = render_stem(part, plan, warnings, s)
    return out, infos, warnings, time.perf_counter() - t0


@pytest.mark.parametrize("renderer", ["numpy", "mock"])
def test_local_renderers_exact_length(renderer):
    plan = plan_for()
    stems, infos, warnings, _ = _render_all(plan, Settings(renderer=renderer, renderer_fallback=""))
    assert set(stems) == {"drums", "bass", "harmony", "melody"}
    for a in stems.values():
        assert a.shape == (480000, 2)
        assert np.isfinite(a).all() and np.abs(a).max() > 1e-3
    assert not warnings
    assert all(i["renderer"] == renderer for i in infos.values())


def test_44k_sample_rate():
    plan = plan_for(output={"sample_rate": 44100})
    stems, *_ = _render_all(plan, Settings(renderer="mock"))
    assert all(a.shape == (441000, 2) for a in stems.values())


@pytest.mark.fluidsynth
def test_fluidsynth_10s_faster_than_10x_realtime(record_property):
    plan = plan_for()
    stems, infos, warnings, secs = _render_all(plan, Settings(renderer="fluidsynth"))
    assert all(a.shape == (480000, 2) for a in stems.values())
    assert all(i["renderer"] == "fluidsynth" for i in infos.values()), warnings
    per_stem = {k: v["seconds"] for k, v in infos.items()}
    record_property("fluidsynth_render_seconds", per_stem)
    assert max(per_stem.values()) < 10.0 / 10  # each stem renders >= 10x real time


def test_primary_failure_falls_back_with_warning():
    s = Settings(renderer="fluidsynth", renderer_fallback="numpy", fault_inject="render_primary_fail")
    plan = plan_for()
    stems, infos, warnings, _ = _render_all(plan, s)
    assert all(i["renderer"] == "numpy" and i["fallback"] for i in infos.values())
    assert [w["code"] for w in warnings].count("PROVIDER_FALLBACK_USED") == 4
    assert all(a.shape == (480000, 2) for a in stems.values())


@pytest.mark.fluidsynth
def test_timeout_retries_then_falls_back():
    s = Settings(renderer="fluidsynth", renderer_fallback="numpy", fault_inject="render_timeout")
    plan = plan_for()
    warnings = []
    part = compose_all(plan)["bass"]
    audio, info = render_stem(part, plan, warnings, s)
    assert info["renderer"] == "numpy" and info["fallback"]
    assert "TimeoutExpired" in warnings[0]["message"]
    assert "fluidsynth#2" in warnings[0]["message"]  # it retried before falling back


def test_all_renderers_fail_is_render_failed():
    s = Settings(renderer="fluidsynth", renderer_fallback="", fault_inject="render_primary_fail")
    plan = plan_for()
    with pytest.raises(JobError) as e:
        render_stem(compose_all(plan)["drums"], plan, [], s)
    assert e.value.code == "RENDER_FAILED" and e.value.retryable
