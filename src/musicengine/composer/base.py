"""Shared composer types and helpers."""
from dataclasses import dataclass, field

import numpy as np

from ..planner.plan import Plan
from ..planner.timegrid import BEATS_PER_BAR


@dataclass
class Note:
    start: float      # beats
    dur: float        # beats
    pitch: int
    vel: int

    def as_tuple(self):
        return (round(self.start, 6), round(self.dur, 6), self.pitch, self.vel)


@dataclass
class StemPart:
    name: str
    program: int
    is_drum: bool
    notes: list[Note]
    fx: list[dict] = field(default_factory=list)  # e.g. {"type": "riser", "start": beats, "end": beats}


class Ctx:
    """Read-only view of a Plan that composers use."""

    def __init__(self, plan: Plan, rng: np.random.Generator):
        self.plan = plan
        self.rng = rng
        self.grid = plan.g
        self.preset = plan.preset
        self.n_bars = len(plan.chords)
        self.loop = self.grid.loop
        # beat of the final hit (non-loop) / loop length in beats
        self.end_beat = self.grid.n_beats
        self.hit_bar = None if self.loop else self.end_beat // BEATS_PER_BAR
        self.hit_beat_in_bar = None if self.loop else self.end_beat % BEATS_PER_BAR
        self.sections = plan.section_objs()
        self.tail_beats = self.grid.tail_s / self.grid.beat_s

    def chord(self, bar: int) -> dict:
        return self.plan.chords[min(bar, self.n_bars - 1)]

    def chord_pcs(self, bar: int) -> list[int]:
        c = self.chord(bar)
        return [(c["root_pc"] + i) % 12 for i in c["intervals"]]

    def intensity(self, bar: int) -> int:
        return self.plan.bar_intensity[min(bar, self.n_bars - 1)]

    def is_build(self, bar: int) -> bool:
        return self.plan.bar_build[min(bar, self.n_bars - 1)]

    def density(self, stem: str, bar: int) -> float:
        return self.preset.layers[stem][self.intensity(bar)]

    def music_bars(self) -> range:
        """Bars that contain music before the final hit (all bars for loops)."""
        if self.loop:
            return range(self.n_bars)
        return range(self.end_beat // BEATS_PER_BAR + (1 if self.hit_beat_in_bar else 0))

    def bar_len(self, bar: int) -> float:
        """Beats of music in this bar (the final hit cuts the last bar)."""
        start = bar * BEATS_PER_BAR
        return max(0.0, min(BEATS_PER_BAR, self.end_beat - start))

    def intensity_at(self, beat: float) -> int:
        cur = self.sections[0].intensity
        for s in self.sections:
            if s.beat_index <= beat + 1e-9:
                cur = s.intensity
        return cur

    def bar_segments(self, bar: int) -> list[tuple[float, float, int]]:
        """Split a bar at section starts that fall on a beat inside it: [(start, end, intensity)]."""
        start, end = bar * 4.0, bar * 4.0 + self.bar_len(bar)
        cuts = [start] + [float(b) for b in self.section_start_beats() if start < b < end] + [end]
        return [(a, b, self.intensity_at(a)) for a, b in zip(cuts, cuts[1:]) if b > a]

    def section_start_bars(self) -> set[int]:
        return {s.bar for s in self.sections if s.beat == 0 and s.beat_index > 0}

    def section_start_beats(self) -> list[int]:
        return [s.beat_index for s in self.sections if s.beat_index > 0]

    def scale(self) -> list[int]:
        from ..planner.plan import MAJOR, MINOR

        steps = MAJOR if self.plan.mode == "major" else MINOR
        return [(self.plan.tonic_pc + s) % 12 for s in steps]


def place_in_range(pc: int, lo: int, hi: int) -> int:
    """Lowest MIDI pitch with pitch class pc that is >= lo (wraps down if above hi)."""
    p = lo + ((pc - lo) % 12)
    return p if p <= hi else p - 12


def humanize_vel(rng, vel: float, spread: int = 6) -> int:
    return int(np.clip(round(vel + rng.integers(-spread, spread + 1)), 1, 127))


def apply_swing(notes: list[Note], swing: float, grid: float = 0.5) -> list[Note]:
    """Delay off-beat 8ths (or 16ths) by up to a triplet. Downbeats never move."""
    if swing <= 0:
        return notes
    shift = swing * grid / 3.0
    for n in notes:
        frac = (n.start / grid) % 2
        if abs(frac - 1) < 1e-6:
            n.start += shift
            n.dur = max(0.05, n.dur - shift)
    return notes


def clip_to_end(notes: list[Note], end_beat: float, keep_final: bool = True) -> list[Note]:
    """Drop notes starting after the hit/loop end; trim notes that overlap it."""
    out = []
    for n in notes:
        if n.start >= end_beat - 1e-9 and not (keep_final and abs(n.start - end_beat) < 1e-9):
            continue
        if n.start < end_beat - 1e-9 and n.start + n.dur > end_beat:
            n.dur = end_beat - n.start
        out.append(n)
    return out


def keep_in_segment(notes: list[Note], start: float, end: float) -> list[Note]:
    out = []
    for n in notes:
        if start - 1e-9 <= n.start < end - 1e-9:
            n.dur = min(n.dur, end - n.start)
            out.append(n)
    return out
