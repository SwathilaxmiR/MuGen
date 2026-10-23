import pytest

from musicengine.composer.registry import STEM_REGISTRY, compose_all, compose_stem, reseed
from musicengine.interpreter import interpret
from musicengine.planner.plan import make_plan
from musicengine.schemas import MusicRequest
from musicengine.styles import FORBIDDEN_PROGRAMS, load_presets

STYLE_PROMPT = {name: f"{p.keywords[0]} {p.keywords[1]}" for name, p in load_presets().items()}


def build(prompt="calm cinematic piano", D=30.0, seed=11, **kw):
    req = MusicRequest(prompt=prompt, duration_s=D, seed=seed, **kw)
    spec, _, _ = interpret(prompt)
    return make_plan(req, spec)


def tuples(part):
    return [n.as_tuple() for n in part.notes]


@pytest.mark.parametrize("style", sorted(STYLE_PROMPT))
def test_deterministic_and_seed_sensitive(style):
    a = compose_all(build(STYLE_PROMPT[style], seed=3))
    b = compose_all(build(STYLE_PROMPT[style], seed=3))
    c = compose_all(build(STYLE_PROMPT[style], seed=4))
    assert all(tuples(a[s]) == tuples(b[s]) for s in a)
    assert any(tuples(a[s]) != tuples(c[s]) for s in a)


@pytest.mark.parametrize("style", sorted(STYLE_PROMPT))
@pytest.mark.parametrize("D", [5, 12, 45])
def test_pitches_in_key(style, D):
    plan = build(STYLE_PROMPT[style], D=D)
    allowed = set(plan.allowed_pcs)
    for name, part in compose_all(plan).items():
        if part.is_drum:
            continue
        bad = {n.pitch % 12 for n in part.notes} - allowed
        assert not bad, (style, name, bad, plan.key_name)


@pytest.mark.parametrize("style", sorted(STYLE_PROMPT))
def test_harmony_continuous_from_zero_and_across_boundaries(style):
    plan = build(STYLE_PROMPT[style], D=40, sections=[
        {"start_s": 0, "mood": "calm intro"}, {"start_s": 13.3, "mood": "build"}, {"start_s": 27, "mood": "peak"}])
    h = compose_stem(plan, "harmony")
    assert min(n.start for n in h.notes) == 0
    end = plan.g.n_beats
    # every point of the music (step 1/8 beat) is covered by some harmony note
    covered = [False] * (end * 8)
    for n in h.notes:
        for k in range(int(round(n.start * 8)), min(len(covered), int(round((n.start + n.dur) * 8)))):
            covered[k] = True
    assert all(covered), style


def test_intensity_changes_at_snapped_beats():
    plan = build("energetic EDM festival track", D=40, sections=[
        {"start_s": 0, "mood": "calm intro"}, {"start_s": 16.1, "mood": "peak"}])
    sec = plan.section_objs()[1]
    beat = sec.beat_index
    parts = compose_all(plan)
    drums_before = [n for n in parts["drums"].notes if beat - 4 <= n.start < beat]
    drums_after = [n for n in parts["drums"].notes if beat <= n.start < beat + 4]
    assert len(drums_after) > len(drums_before)
    assert any(abs(n.start - beat) < 1e-9 and n.pitch == 49 for n in parts["drums"].notes)  # crash on change
    assert abs(sec.applied_start_s - 16.1) <= 0.5


def test_beat_snapped_section_changes_mid_bar():
    plan = build("energetic EDM festival track", D=40, tempo_bpm=120, sections=[
        {"start_s": 0, "mood": "calm intro"}, {"start_s": 9.0, "mood": "peak"}])  # bar = 2 s -> beat 18
    sec = plan.section_objs()[1]
    assert sec.beat != 0
    mel = compose_stem(plan, "melody")
    assert not any(n.start < sec.beat_index - 1e-9 for n in mel.notes)  # melody silent at intensity 1
    assert any(abs(n.start - sec.beat_index) < 2 for n in mel.notes)


def test_forbidden_programs_never_used():
    for style in STYLE_PROMPT:
        for name, part in compose_all(build(STYLE_PROMPT[style])).items():
            if not part.is_drum:
                assert part.program not in FORBIDDEN_PROGRAMS


def test_final_hit_present_only_without_loop():
    plan = build(D=20)
    end = plan.g.n_beats
    for name, part in compose_all(plan).items():
        assert any(abs(n.start - end) < 1e-9 for n in part.notes), name
        assert max(n.start for n in part.notes) <= end + 1e-9
    loop = build(D=16, loopable=True)
    for name, part in compose_all(loop).items():
        assert all(n.start < loop.g.n_beats - 1e-9 for n in part.notes), name
        assert all(n.start + n.dur <= loop.g.n_beats + 1e-6 for n in part.notes), name


def test_reseed_changes_only_that_stem():
    plan = build(D=20)
    before = {s: tuples(compose_stem(plan, s)) for s in STEM_REGISTRY}
    reseed(plan, "drums", None)
    after = {s: tuples(compose_stem(plan, s)) for s in STEM_REGISTRY}
    assert before["drums"] != after["drums"]
    assert all(before[s] == after[s] for s in ("bass", "harmony", "melody"))


def test_build_section_gets_riser():
    plan = build("cinematic score", D=60, sections=[{"start_s": 0, "mood": "intro"},
                                                    {"start_s": 20, "mood": "build"},
                                                    {"start_s": 40, "mood": "peak"}])
    fx = compose_stem(plan, "drums").fx
    assert fx and fx[0]["type"] == "riser"
    peak_beat = plan.section_objs()[2].beat_index
    assert abs(fx[0]["end"] - peak_beat) < 1e-9


@pytest.mark.parametrize("style", sorted(STYLE_PROMPT))
@pytest.mark.parametrize("key", ["C major", "F# minor", "Bb major", "E minor"])
def test_user_key_respected_and_in_key(style, key):
    plan = build(STYLE_PROMPT[style], D=20, key=key)
    assert plan.key_name == key
    allowed = set(plan.allowed_pcs)
    for name, part in compose_all(plan).items():
        if not part.is_drum:
            assert not ({n.pitch % 12 for n in part.notes} - allowed), (style, key, name)
