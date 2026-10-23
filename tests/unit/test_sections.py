import pytest

from musicengine.planner.sections import mood_intensity, plan_sections
from musicengine.planner.timegrid import plan_grid

SR = 48000


def codes(ws):
    return [w["code"] for w in ws]


@pytest.mark.parametrize("bpm", [80, 90, 100, 120, 140, 160])
@pytest.mark.parametrize("req", [3.1, 7.77, 11.2, 15.49, 20.01])
def test_snap_within_half_second_on_a_beat(bpm, req):
    g = plan_grid(30, SR, tempo_bpm=bpm)
    secs, _ = plan_sections(g, [{"start_s": 0, "mood": "calm"}, {"start_s": req, "mood": "peak"}])
    s = secs[-1]
    assert abs(s.applied_start_s - req) <= 0.5 + 1e-9
    assert abs(s.applied_start_s / g.beat_s - round(s.applied_start_s / g.beat_s)) < 1e-9


def test_snap_prefers_bar_line():
    g = plan_grid(30, SR, tempo_bpm=120)  # bar = 2 s
    secs, ws = plan_sections(g, [{"start_s": 0, "mood": "calm"}, {"start_s": 8.3, "mood": "peak"}])
    assert secs[1].applied_start_s == pytest.approx(8.0)
    assert secs[1].beat == 0 and secs[1].bar == 4
    assert "SECTION_SNAPPED" in codes(ws)


def test_snap_falls_back_to_beat():
    g = plan_grid(30, SR, tempo_bpm=90)  # bar 2.667 s, beat 0.667 s
    secs, _ = plan_sections(g, [{"start_s": 0, "mood": "calm"}, {"start_s": 4.0, "mood": "peak"}])
    assert secs[1].applied_start_s == pytest.approx(4.0)
    assert secs[1].beat != 0


def test_merge_min_gap_keeps_earlier_start_and_higher_intensity():
    g = plan_grid(30, SR, tempo_bpm=120)
    secs, ws = plan_sections(g, [{"start_s": 0, "mood": "calm"}, {"start_s": 10, "mood": "build"},
                                 {"start_s": 11, "mood": "peak"}], min_gap_s=1.5)
    assert len(secs) == 2
    assert secs[1].applied_start_s == pytest.approx(10.0)
    assert secs[1].intensity == 4
    assert "SECTIONS_MERGED_MIN_GAP" in codes(ws)


def test_section_after_end_dropped():
    g = plan_grid(20, SR, tempo_bpm=120)
    secs, ws = plan_sections(g, [{"start_s": 0, "mood": "calm"}, {"start_s": 25, "mood": "peak"},
                                 {"start_s": g.hit_time_s - 0.1, "mood": "outro"}])
    assert len(secs) == 1
    assert codes(ws).count("SECTION_AFTER_END_DROPPED") == 2


def test_first_section_after_zero_gets_intro():
    g = plan_grid(30, SR, tempo_bpm=120)
    secs, _ = plan_sections(g, [{"start_s": 10, "mood": "peak"}])
    assert secs[0].applied_start_s == 0 and secs[0].derived
    assert secs[1].intensity == 4


def test_default_arc_and_short_track():
    g = plan_grid(60, SR)
    secs, ws = plan_sections(g, None, prompt_text="slowly builds to a climax")
    assert [s.mood for s in secs] == ["intro", "build", "peak"]
    assert secs[0].intensity < secs[-1].intensity
    assert not ws
    short = plan_grid(5, SR)
    secs, _ = plan_sections(short, None)
    assert len(secs) == 1


def test_slow_fixed_tempo_warns():
    g = plan_grid(30, SR, tempo_bpm=50)
    _, ws = plan_sections(g, [{"start_s": 0, "mood": "calm"}])
    assert "TEMPO_OUTSIDE_SNAP_RANGE" in codes(ws)


def test_mood_intensity_map():
    assert mood_intensity("calm intro")[0] == 1
    assert mood_intensity("uplifting peak")[0] == 4
    assert mood_intensity("tense")[0] == 3
    assert mood_intensity("builds up") == (2, True)
    assert mood_intensity("outro fade")[0] == 1
    assert mood_intensity("xyz")[0] == 2
