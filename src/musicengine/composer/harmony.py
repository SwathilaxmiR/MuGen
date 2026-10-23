"""Harmony: pad / block / strum / arp / comp... Always sounding from t=0 and continuous across
section changes (a sustained layer under every rhythmic style), last chord held on the hit."""
from .base import Ctx, Note, StemPart, apply_swing, clip_to_end, humanize_vel, keep_in_segment

LO, HI = 50, 76

# rhythmic layer per style: (onset, dur) within a bar, by tier
RHYTHMS = {
    "block_soft": {1: [(0, 3.5)], 2: [(0, 1.5), (2.5, 1.5)], 3: [(0, 1.5), (1.5, 0.5), (2.5, 1.5)]},
    "block": {1: [(0, 4)], 2: [(i, 0.9) for i in range(4)], 3: [(i * 0.5, 0.45) for i in range(8)]},
    "comp": {1: [(0, 3.5)], 2: [(0, 0.75), (1.5, 0.5)], 3: [(0, 0.75), (1.5, 0.5), (3, 0.5)]},
    "staccato": {1: [(0, 0.4), (2, 0.4)], 2: [(1, 0.3), (2, 0.3), (3, 0.3), (0, 0.3)],
                 3: [(i * 0.5, 0.25) for i in range(8)]},
    "stabs": {1: [(0, 4)], 2: [(0, 1.5), (1.5, 1.5), (3, 1)], 3: [(0, 0.75), (0.75, 0.75), (1.5, 1), (3, 0.5), (3.5, 0.5)]},
    "power": {1: [(0, 4)], 2: [(i * 0.5, 0.45) for i in range(8)], 3: [(i * 0.5, 0.45) for i in range(8)]},
    "pad_pulse": {1: [(0, 4)], 2: [(0, 4)], 3: [(i * 0.5 + 0.5, 0.4) for i in range(0, 8, 2)]},
    "strum": {1: [(0, 4)], 2: [(0, 1), (1, 0.5), (1.5, 1), (2.5, 0.5), (3, 0.5), (3.5, 0.5)],
              3: [(i * 0.5, 0.5) for i in range(8)]},
}
TIER = {0: 1, 1: 1, 2: 2, 3: 2, 4: 3}
# GM programs whose notes die away even when held (piano, mallets, plucked): a "sustained" chord is
# re-struck instead, every beat for fast-decaying ones, every two beats for the rest
FAST_DECAY = set(range(8, 16)) | {45, 47, 105, 106, 107, 108}
SLOW_DECAY = set(range(0, 8)) | {24, 25, 26, 27, 28, 46, 104}


def voice(pcs: list[int], prev: list[int] | None, n_voices: int = 4) -> list[int]:
    """Closest voicing to the previous chord inside [LO, HI] (simple voice leading)."""
    cands = []
    for base in range(LO, LO + 12):
        v = []
        p = base
        for i in range(n_voices):
            pc = pcs[i % len(pcs)]
            while p % 12 != pc:
                p += 1
            v.append(p)
            p += 1
        if v[-1] <= HI + 4:
            cands.append(v)
    if not prev:
        target = (LO + HI) / 2
        return min(cands, key=lambda v: abs(sum(v) / len(v) - target))
    return min(cands, key=lambda v: sum(abs(a - b) for a, b in zip(sorted(v), sorted(prev))))


def power_voicing(root_pc: int) -> list[int]:
    r = 40 + ((root_pc - 40) % 12)  # E2..D#3
    return [r, r + 7, r + 12]


def _segment(ctx: Ctx, style: str, v: list[int], bar_start: float, bar_len: float,
             seg_start: float, seg_end: float, inten: int) -> list[Note]:
    out: list[Note] = []
    vel = 55 + 9 * inten
    # sustained layer: covers the whole segment, ends exactly where the next one starts -> no gaps
    rhythmic = style in RHYTHMS and TIER[inten] > 1
    # (beds sit an octave below the hits: a MIDI note-off for a shared pitch would cut the bed short)
    program = ctx.preset.programs["harmony"]
    if not rhythmic and style != "arp" and program in FAST_DECAY | SLOW_DECAY:
        step = 1.0 if program in FAST_DECAY else 2.0
        t = seg_start
        while t < seg_end - 1e-9:
            d = min(step, seg_end - t)
            out += [Note(t, d, pitch, humanize_vel(ctx.rng, vel - (0 if t == seg_start else 8), 3)) for pitch in v]
            t += step
    elif not rhythmic and style != "arp":
        out += [Note(seg_start, seg_end - seg_start, pitch, humanize_vel(ctx.rng, vel, 3)) for pitch in v]
    else:  # quiet bed under rhythmic styles so there is never silence between hits
        bed_vel = int(vel * (0.6 if style == "arp" else 0.4))
        out += [Note(seg_start, seg_end - seg_start, pitch - 12, humanize_vel(ctx.rng, bed_vel, 2))
                for pitch in v[:2 if style == "power" else 3]]
    hits: list[Note] = []
    if style == "arp":
        step = 0.5 if inten >= 2 else 1.0
        seq = v + [v[1] + 12, v[2] + 12] if inten >= 3 else v + [v[1] + 12]
        seq = seq + seq[-2:0:-1]
        t, i = 0.0, 0
        while t < bar_len - 1e-9:
            hits.append(Note(bar_start + t, step * 0.95, seq[i % len(seq)] + 12 * (inten >= 4),
                             humanize_vel(ctx.rng, vel + 8)))
            t += step
            i += 1
    elif rhythmic:
        for t, d in RHYTHMS[style][TIER[inten]]:
            if t >= bar_len:
                continue
            d = min(d, bar_len - t)
            offs = 0.0
            order = v if (int(t * 2) % 2 == 0) else v[::-1]
            for pitch in order:
                if style == "strum":
                    offs += 0.02  # strummed spread
                hits.append(Note(bar_start + t + offs, max(0.1, d - offs), pitch,
                                 humanize_vel(ctx.rng, vel + (10 if t == 0 else 0))))
    out += keep_in_segment(hits, seg_start, seg_end)
    return out


def compose_harmony(ctx: Ctx) -> StemPart:
    p = ctx.preset
    style = p.harmony_style
    notes: list[Note] = []
    prev = None
    bars = list(ctx.music_bars())
    for bar in bars:
        bar_start, bar_len = bar * 4.0, ctx.bar_len(bar)
        if bar_len <= 0:
            continue
        pcs = ctx.chord_pcs(bar)
        v = power_voicing(ctx.chord(bar)["root_pc"]) if style == "power" else voice(pcs, prev)
        prev = v
        for seg_start, seg_end, inten in ctx.bar_segments(bar):
            notes += _segment(ctx, style, v, bar_start, bar_len, seg_start, seg_end, inten)
    notes = apply_swing(notes, p.swing)
    notes = clip_to_end(notes, ctx.end_beat, keep_final=False)
    if not ctx.loop:
        pcs = ctx.chord_pcs(ctx.hit_bar) if ctx.hit_bar is not None else ctx.chord_pcs(len(ctx.plan.chords) - 1)
        v = power_voicing(ctx.plan.tonic_pc) if style == "power" else voice(pcs, prev)
        hold = max(0.5, min(4.0, 0.45 * ctx.tail_beats))
        for pitch in v:
            notes.append(Note(float(ctx.end_beat), hold, pitch, 100))
    return StemPart("harmony", p.programs["harmony"], False, sorted(notes, key=lambda n: (n.start, n.pitch)))
