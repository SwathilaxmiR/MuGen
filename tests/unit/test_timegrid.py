import itertools

import pytest

from musicengine.planner.timegrid import BEATS_PER_BAR, MAX_TAIL_S, MIN_TAIL_S, plan_grid

DURS = [5, 5.5, 6, 10, 45, 180, 300]
TEMPOS = [None, 60, 90, 120, 140]
SR = 48000


@pytest.mark.parametrize("D,tempo,loop", list(itertools.product(DURS, TEMPOS, [False, True])))
def test_grid_matrix(D, tempo, loop):
    g = plan_grid(D, SR, tempo_bpm=tempo, loopable=loop, tempo_range=(70, 130), tempo_centre=100)
    assert g.length_samples == round(D * SR)
    codes = {w["code"] for w in g.warnings}
    if loop:
        assert g.n_bars >= 1
        # D == N * bar within one sample
        assert abs(g.n_bars * g.bar_s * SR - D * SR) < 1
        assert "LOOP_IGNORES_ENDING" in codes
        if tempo is not None and abs(g.bpm - tempo) > 1e-6:
            assert "TEMPO_ADJUSTED_FOR_LOOP" in codes
        return
    if g.hit_on_bar:
        assert g.n_bars >= 1
        assert abs(g.hit_time_s - g.n_bars * g.bar_s) < 1e-9
    else:
        assert "ENDING_ON_BEAT_NOT_BAR" in codes
        assert abs(g.hit_time_s / g.beat_s - round(g.hit_time_s / g.beat_s)) < 1e-9
    assert g.tail_s >= MIN_TAIL_S - 1e-9
    if tempo is None:
        assert g.tail_s <= MAX_TAIL_S + 1e-9
        assert g.bpm >= 80  # free tempo floor keeps beat snaps within 0.5 s
    else:
        assert g.bpm == tempo
        assert g.tail_s < MIN_TAIL_S + g.bar_s + 1e-9


def test_free_tempo_prefers_centre():
    g = plan_grid(60, SR, tempo_range=(90, 130), tempo_centre=120)
    assert abs(g.bpm - 120) <= 3


def test_slow_fixed_tempo_short_track_ends_on_beat():
    g = plan_grid(5, SR, tempo_bpm=40)  # bar = 6 s > 5 - 0.75
    assert not g.hit_on_bar
    assert g.warnings[0]["code"] == "ENDING_ON_BEAT_NOT_BAR"


def test_beats_and_bars_arrays():
    g = plan_grid(10, SR, tempo_bpm=120)
    beats = g.beats()
    assert beats[0]["downbeat"] and beats[0]["t"] == 0
    assert all(b["downbeat"] == (b["beat"] == 0) for b in beats)
    assert beats[-1]["t"] == pytest.approx(g.hit_time_s)
    bars = g.bars()
    assert bars[1]["t"] == pytest.approx(g.bar_s)
    assert len([b for b in beats if b["downbeat"]]) == len(bars)
    assert BEATS_PER_BAR * g.beat_s == pytest.approx(g.bar_s)


def test_loop_beats_stop_before_wrap():
    g = plan_grid(8, SR, tempo_bpm=120, loopable=True)
    assert g.n_bars == 4
    assert g.beats()[-1]["t"] < 8
    assert len(g.beats()) == 16
