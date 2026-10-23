"""Drums: 16th-grid patterns by intensity, fills before section changes, crash on section downbeats,
riser on build sections, final hit (crash + kick) on the hit beat, then nothing."""
from .base import Ctx, Note, StemPart, apply_swing, clip_to_end, humanize_vel, keep_in_segment

KICK, SNARE, RIM, CLAP, CH, PH, OH, CRASH, RIDE, BELL = 36, 38, 37, 39, 42, 44, 46, 49, 51, 53
TOM_L, TOM_M, TOM_H, FLOOR = 45, 47, 50, 41
SHAKER, TAMB, WOOD_H, WOOD_L = 70, 54, 76, 77
VEL = {"x": 112, "o": 86, ".": 52}

# style -> tier (1 low, 2 mid, 3 high) -> {drum note: 16-step pattern}
P = {
    "four_on_floor": {
        1: {KICK: "x---x---x---x---", CH: "--.---.---.---.-"},
        2: {KICK: "x---x---x---x---", CLAP: "----o-------o---", CH: "--o---o---o---o-"},
        3: {KICK: "x---x---x---x---", CLAP: "----x-------x---", CH: "o.o.o.o.o.o.o.o.", OH: "--o---o---o---o-"},
    },
    "four_on_floor_pop": {
        1: {KICK: "x-------x-------", TAMB: "--.---.---.---.-"},
        2: {KICK: "x---x---x---x---", CLAP: "----o-------o---", TAMB: "o-o-o-o-o-o-o-o-"},
        3: {KICK: "x---x---x---x---", CLAP: "----x-------x---", TAMB: "o.o.o.o.o.o.o.o.", OH: "--o---o---o---o-"},
    },
    "pop_light": {
        1: {KICK: "x-------x-------", SHAKER: "o.o.o.o.o.o.o.o."},
        2: {KICK: "x-------x-x-----", CLAP: "----o-------o---", CH: "o-o-o-o-o-o-o-o-"},
        3: {KICK: "x-----x-x-x-----", SNARE: "----x-------x---", CH: "o.o.o.o.o.o.o.o.", CLAP: "----o-------o---"},
    },
    "acoustic": {
        1: {SHAKER: "o.o.o.o.o.o.o.o.", KICK: "x---------------"},
        2: {KICK: "x-----x---x-----", RIM: "----o-------o---", SHAKER: "o.o.o.o.o.o.o.o."},
        3: {KICK: "x-----x-x-x-----", SNARE: "----x-------x---", CH: "o-o-o-o-o-o-o-o-", TAMB: "----o-------o---"},
    },
    "lofi": {
        1: {CH: "o-.-o-.-o-.-o-.-", RIM: "----.-------.---"},
        2: {KICK: "x------o--x-----", SNARE: "----o-------o---", CH: "o-.-o-.-o-.-o-.-"},
        3: {KICK: "x------o--x--o--", SNARE: "----x-------x---", CH: "o.o.o.o.o.o.o.o.", OH: "--------------.-"},
    },
    "rock": {
        1: {KICK: "x-------x-------", CH: "o-o-o-o-o-o-o-o-"},
        2: {KICK: "x-----x-x-------", SNARE: "----x-------x---", CH: "x-o-x-o-x-o-x-o-"},
        3: {KICK: "x-----x-x-x-x---", SNARE: "----x-------x---", RIDE: "x-o-x-o-x-o-x-o-", CRASH: "x---------------"},
    },
    "jazz": {
        1: {RIDE: "o---o-.-o---o-.-", PH: "----.-------.---"},
        2: {RIDE: "x---o-.-x---o-.-", PH: "----o-------o---", KICK: ".-------.-------"},
        3: {RIDE: "x---o-o-x---o-o-", PH: "----o-------o---", KICK: "o-------.-----.-", SNARE: "------.-----.--."},
    },
    "cinematic": {
        1: {FLOOR: ".---------------"},
        2: {KICK: "x-------o-------", FLOOR: "------.-.-------", TOM_L: "--------------.."},
        3: {KICK: "x-----o-x-------", FLOOR: "x--o--o-x--o--o-", SNARE: "..o...o...o...o.", CRASH: "x---------------"},
    },
    "taiko": {
        1: {KICK: "x-------o-------", FLOOR: "--------.-------"},
        2: {KICK: "x--o--o-x-------", FLOOR: "x-------x--o-o--", TOM_L: "------o-------o-"},
        3: {KICK: "x--x--x-x--x-x--", FLOOR: "x-ox-ox-x-ox-oxo", SNARE: "o.o.o.o.o.o.o.o.", CRASH: "x-------x-------"},
    },
    "pulse": {
        1: {KICK: "x--.------------"},
        2: {KICK: "x--o----x--o----", CH: "..o...o...o...o."},
        3: {KICK: "x--o----x--o----", CH: "o.o.o.o.o.o.o.o.", FLOOR: "------o-------oo", SNARE: "------------o---"},
    },
    "playful": {
        1: {WOOD_H: "o-------o-------", WOOD_L: "----.-------.---"},
        2: {KICK: "x-------x-------", RIM: "----o-------o---", WOOD_H: "--o---o---o---o-"},
        3: {KICK: "x-----x-x-------", SNARE: "----o-------o---", WOOD_H: "o-o-o-o-o-o-o-o-", CLAP: "----o-------o---"},
    },
    "ambient": {
        1: {BELL: "o---------------"},
        2: {SHAKER: ".-.-.-.-.-.-.-.-", BELL: "o-------.-------"},
        3: {KICK: "o-------o-------", SHAKER: "o.o.o.o.o.o.o.o.", RIDE: "o-------o-------"},
    },
}
TIER = {0: 0, 1: 1, 2: 2, 3: 2, 4: 3}


def _pattern_notes(pattern: dict, bar_start: float, bar_len: float, intensity: int, ctx: Ctx) -> list[Note]:
    out = []
    boost = 1.0 if intensity < 3 else 1.08
    for drum, steps in pattern.items():
        for i, ch in enumerate(steps):
            if ch == "-":
                continue
            t = i * 0.25
            if t >= bar_len - 1e-9:
                continue
            out.append(Note(bar_start + t, 0.25, drum, humanize_vel(ctx.rng, VEL[ch] * boost)))
    # extra open hat lift at intensity 3 on the last off-beat
    if intensity == 3 and bar_len >= 4:
        out.append(Note(bar_start + 3.5, 0.25, OH, humanize_vel(ctx.rng, 70)))
    return out


def _fill(bar_start: float, bar_len: float, ctx: Ctx, orchestral: bool) -> list[Note]:
    """Last two beats of the bar before a section change: crescendo of 16ths."""
    out = []
    start = max(0.0, bar_len - 2.0)
    drums = [FLOOR, TOM_L] if orchestral else [SNARE, TOM_H, TOM_M, TOM_L]
    n = int(round((bar_len - start) / 0.25))
    for i in range(n):
        t = start + i * 0.25
        out.append(Note(bar_start + t, 0.25, drums[(i * len(drums)) // max(n, 1)],
                        humanize_vel(ctx.rng, 60 + 50 * i / max(n - 1, 1), 4)))
    return out


def compose_drums(ctx: Ctx) -> StemPart:
    p = ctx.preset
    style = P.get(p.drum_style, P["pop_light"])
    orchestral = p.drum_style in ("cinematic", "taiko", "pulse")
    notes: list[Note] = []
    fx: list[dict] = []
    sec_bars = ctx.section_start_bars()
    bars = list(ctx.music_bars())
    short = ctx.grid.duration_s < 8
    for bar in bars:
        inten = ctx.intensity(bar)
        bar_start, bar_len = bar * 4.0, ctx.bar_len(bar)
        if bar_len <= 0:
            continue
        tier = TIER[inten]
        for seg_start, seg_end, seg_int in ctx.bar_segments(bar):
            if not TIER[seg_int]:
                continue
            dens = p.layers["drums"][seg_int]
            pat_notes = _pattern_notes(style[TIER[seg_int]], bar_start, bar_len, seg_int, ctx)
            for n in keep_in_segment(pat_notes, seg_start, seg_end):
                on_beat = abs((n.start - bar_start) % 1.0) < 1e-6
                if dens >= 1 or n.pitch == KICK and on_beat or ctx.rng.random() < dens + 0.15:
                    notes.append(n)
        nxt = bar + 1
        changing = nxt in sec_bars and not short
        if changing and bar_len >= 4 and (ctx.intensity(nxt) >= inten or inten >= 2) and tier:
            notes = [n for n in notes if not (n.start >= bar_start + bar_len - 2.0 and n.pitch != KICK)]
            notes += _fill(bar_start, bar_len, ctx, orchestral)
        if bar in sec_bars and ctx.intensity(bar) >= 2:
            notes.append(Note(bar_start, 1.0, CRASH, humanize_vel(ctx.rng, 105)))
            notes.append(Note(bar_start, 0.25, KICK, humanize_vel(ctx.rng, 112)))
        if ctx.is_build(bar) and (nxt in sec_bars or (not ctx.loop and nxt == ctx.hit_bar)):
            span = min(8.0, bar_start + bar_len - _section_start_beat(ctx, bar))
            fx.append({"type": "riser", "start": bar_start + bar_len - span, "end": bar_start + bar_len})
    # section changes on a beat (not a bar line): accent the beat so the change is audible there
    for b in ctx.section_start_beats():
        if b % 4:
            notes.append(Note(float(b), 0.5, CRASH if ctx.intensity_at(b) >= 2 else RIDE,
                              humanize_vel(ctx.rng, 96)))
    notes = apply_swing(notes, p.swing)
    notes = clip_to_end(notes, ctx.end_beat, keep_final=False)
    if not ctx.loop:
        notes.append(Note(float(ctx.end_beat), 2.0, CRASH, 118))
        notes.append(Note(float(ctx.end_beat), 1.0, KICK, 120))
        if orchestral:
            notes.append(Note(float(ctx.end_beat), 1.0, FLOOR, 115))
    return StemPart("drums", p.programs["drums"], True, sorted(notes, key=lambda n: (n.start, n.pitch)), fx)


def _section_start_beat(ctx: Ctx, bar: int) -> float:
    start = 0.0
    for s in ctx.sections:
        if s.beat_index <= bar * 4:
            start = float(s.beat_index)
    return start
