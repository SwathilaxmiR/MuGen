"""Tempo / bar-count / exact-length planning (4/4 only). Pure functions.

Non-loop: N whole bars of music, a final hit on the downbeat at T = N*bar, then a decaying tail to D.
Loop:     D == N*bar exactly; no final hit.
"""
from dataclasses import dataclass, field
from math import floor

from ..errors import warning

BEATS_PER_BAR = 4
MIN_TAIL_S = 0.75
MAX_TAIL_S = 2.5
FREE_TEMPO_FLOOR = 80  # keeps one beat <= 0.75 s so section snaps stay within 0.5 s
LOOP_TEMPO_TOL = 0.08


@dataclass
class Grid:
    bpm: float
    n_bars: int
    hit_time_s: float          # == duration for loops
    tail_s: float
    duration_s: float
    length_samples: int
    loop: bool
    hit_on_bar: bool = True
    warnings: list[dict] = field(default_factory=list)

    @property
    def beat_s(self) -> float:
        return 60.0 / self.bpm

    @property
    def bar_s(self) -> float:
        return BEATS_PER_BAR * self.beat_s

    @property
    def n_beats(self) -> int:
        """Beats of music before the hit (the hit itself is beat n_beats)."""
        return round(self.hit_time_s / self.beat_s)

    def beats(self) -> list[dict]:
        out = []
        last = self.n_beats if not self.loop else self.n_beats - 1
        for k in range(last + 1):
            t = k * self.beat_s
            out.append({"t": round(t, 6), "bar": k // BEATS_PER_BAR, "beat": k % BEATS_PER_BAR,
                        "downbeat": k % BEATS_PER_BAR == 0})
        return out

    def bars(self) -> list[dict]:
        n = self.n_bars + (0 if self.loop else 1)  # include the hit downbeat
        return [{"index": i, "t": round(i * self.bar_s, 6)} for i in range(n)
                if i * self.bar_s < self.duration_s - 1e-9]


def tail_target(duration_s: float) -> float:
    return max(MIN_TAIL_S, min(2.0, 0.25 * duration_s))


def _clamp_range(lo: float, hi: float, free: bool) -> tuple[float, float]:
    if free:
        lo = max(lo, FREE_TEMPO_FLOOR)
        hi = max(hi, lo)
    return lo, hi


def plan_grid(duration_s: float, sr: int, tempo_bpm: float | None = None, loopable: bool = False,
              tempo_range: tuple[float, float] = (90, 130), tempo_centre: float | None = None) -> Grid:
    L = round(duration_s * sr)
    lo, hi = _clamp_range(*tempo_range, free=tempo_bpm is None)
    centre = tempo_centre if tempo_centre is not None else (lo + hi) / 2
    centre = min(max(centre, lo), hi)
    if loopable:
        return _plan_loop(duration_s, L, tempo_bpm, lo, hi, centre)
    if tempo_bpm is not None:
        return _plan_fixed(duration_s, L, float(tempo_bpm))
    return _plan_free(duration_s, L, lo, hi, centre)


def _plan_free(D: float, L: int, lo: float, hi: float, centre: float) -> Grid:
    target = tail_target(D)
    best = None
    for bpm in range(int(round(lo)), int(round(hi)) + 1):
        bar = BEATS_PER_BAR * 60.0 / bpm
        n = floor((D - MIN_TAIL_S) / bar)
        while n >= 1 and D - n * bar <= MAX_TAIL_S:
            tail = D - n * bar
            if tail >= MIN_TAIL_S:
                score = (abs(bpm - centre), abs(tail - target))
                if best is None or score < best[0]:
                    best = (score, float(bpm), n, tail)
            n -= 1
    if best is None:
        # no integer tempo fits the tail window: solve for an exact (fractional) tempo instead
        cands = []
        for n in range(1, 400):
            bpm = 240.0 * n / (D - target)
            if lo <= bpm <= hi:
                cands.append((abs(bpm - centre), round(bpm, 3), n))
        if not cands:  # very short track: take the slowest musical option
            n = 1
            bpm = 240.0 / (D - target)
        else:
            _, bpm, n = min(cands)
        tail = D - n * 240.0 / bpm
        best = (None, bpm, n, tail)
    _, bpm, n, tail = best
    T = n * 240.0 / bpm
    return Grid(bpm=bpm, n_bars=n, hit_time_s=T, tail_s=D - T, duration_s=D, length_samples=L, loop=False)


def _plan_fixed(D: float, L: int, bpm: float) -> Grid:
    bar = BEATS_PER_BAR * 60.0 / bpm
    n = floor((D - MIN_TAIL_S) / bar)
    if n >= 1:
        T = n * bar
        return Grid(bpm=bpm, n_bars=n, hit_time_s=T, tail_s=D - T, duration_s=D, length_samples=L, loop=False)
    beat = 60.0 / bpm
    k = max(1, floor((D - MIN_TAIL_S) / beat))
    T = k * beat
    g = Grid(bpm=bpm, n_bars=0, hit_time_s=T, tail_s=D - T, duration_s=D, length_samples=L,
             loop=False, hit_on_bar=False)
    g.warnings.append(warning("ENDING_ON_BEAT_NOT_BAR",
                              f"At {bpm:g} bpm one bar ({bar:.2f}s) does not fit in {D:g}s; "
                              f"the final hit lands on beat {k} at {T:.3f}s.", hit_time_s=round(T, 3)))
    return g


def _plan_loop(D: float, L: int, tempo: float | None, lo: float, hi: float, centre: float) -> Grid:
    warnings = [warning("LOOP_IGNORES_ENDING", "Loop mode has no final hit; the file ends on a bar "
                        "line and wraps seamlessly.")]
    if tempo is not None:
        n = max(1, round(D * tempo / 240.0))
        bpm = 240.0 * n / D
        if abs(bpm - tempo) > 1e-6:
            within = abs(bpm - tempo) / tempo <= LOOP_TEMPO_TOL
            warnings.append(warning(
                "TEMPO_ADJUSTED_FOR_LOOP",
                f"{tempo:g} bpm cannot fill {D:g}s with whole bars; using {bpm:.3f} bpm ({n} bars).",
                requested_bpm=tempo, applied_bpm=round(bpm, 4), within_8_percent=within))
    else:
        cands = []
        for n in range(1, 2000):
            bpm = 240.0 * n / D
            if bpm > hi:
                break
            if bpm >= lo:
                cands.append((abs(bpm - centre), n))
        if cands:
            n = min(cands)[1]
        else:  # range too narrow for this duration: nearest whole bar count to the centre tempo
            n = max(1, round(D * centre / 240.0))
        bpm = 240.0 * n / D
    return Grid(bpm=bpm, n_bars=n, hit_time_s=D, tail_s=0.0, duration_s=D, length_samples=L,
                loop=True, warnings=warnings)
