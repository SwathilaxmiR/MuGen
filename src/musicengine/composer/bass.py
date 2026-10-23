"""Bass: root/fifth/octave patterns that follow the chords; density follows intensity."""
from .base import Ctx, Note, StemPart, apply_swing, clip_to_end, humanize_vel, keep_in_segment, place_in_range

LO, HI = 33, 47  # A1 .. B2

# style -> list of (onset beats, dur beats, degree) where degree: 0 root, 1 fifth, 2 octave, 3 third
PATTERNS = {
    "sustained": {1: [(0, 4, 0)], 2: [(0, 4, 0)], 3: [(0, 2, 0), (2, 2, 1)]},
    "lofi": {1: [(0, 2, 0)], 2: [(0, 1.5, 0), (1.75, 0.5, 1), (2.5, 1.5, 0)],
             3: [(0, 1.5, 0), (1.75, 0.5, 1), (2.5, 1, 0), (3.5, 0.5, 2)]},
    "eighths": {1: [(0, 2, 0), (2, 2, 0)], 2: [(i * 0.5, 0.45, 0) for i in range(8)],
                3: [(i * 0.5, 0.45, 0 if i % 4 != 3 else 2) for i in range(8)]},
    "offbeat": {1: [(0, 4, 0)], 2: [(0.5 + i, 0.45, 0) for i in range(4)],
                3: [(0, 0.45, 0)] + [(0.5 + i, 0.45, 0 if i % 2 == 0 else 2) for i in range(4)]},
    "roots": {1: [(0, 4, 0)], 2: [(0, 2, 0), (2, 2, 1)], 3: [(0, 1.5, 0), (1.5, 0.5, 0), (2, 1.5, 1), (3.5, 0.5, 3)]},
    "ostinato": {1: [(0, 1, 0), (2, 1, 0)], 2: [(i * 0.5, 0.4, 0 if i % 4 else 2) for i in range(8)],
                 3: [(i * 0.5, 0.4, (0, 0, 1, 0, 2, 0, 1, 0)[i]) for i in range(8)]},
    "bouncy": {1: [(0, 0.5, 0), (2, 0.5, 1)], 2: [(0, 0.45, 0), (1, 0.45, 1), (2, 0.45, 0), (3, 0.45, 1)],
               3: [(0, 0.45, 0), (1, 0.45, 1), (2, 0.45, 2), (3, 0.45, 1), (3.5, 0.4, 0)]},
    "drone": {1: [(0, 4, 0)], 2: [(0, 4, 0)], 3: [(0, 4, 0)]},
    "octaves": {1: [(0, 2, 0), (2, 2, 0)], 2: [(i * 0.5, 0.45, 0 if i % 2 == 0 else 2) for i in range(8)],
                3: [(i * 0.5, 0.45, 0 if i % 2 == 0 else 2) for i in range(8)]},
}
TIER = {0: 0, 1: 1, 2: 2, 3: 2, 4: 3}


def _degree_pitch(ctx: Ctx, bar: int, degree: int, root: int) -> int:
    c = ctx.chord(bar)
    if degree == 0:
        return root
    if degree == 1:
        return root + 7 if root + 7 <= HI + 5 else root - 5
    if degree == 2:
        return root + 12
    third = c["intervals"][1]
    return root + third


def _walking(ctx: Ctx, bar: int, root: int, bar_len: float) -> list[tuple[float, float, int]]:
    """Jazz walk: root, chord tone, fifth, scale step toward the next root."""
    pcs = ctx.chord_pcs(bar)
    nxt = place_in_range(ctx.chord(bar + 1)["root_pc"], LO, HI)
    scale = ctx.scale()
    tone = place_in_range(pcs[1], root, root + 12)
    fifth = root + 7 if root + 7 <= HI + 7 else root - 5
    step_pc = scale[(scale.index(nxt % 12) + (1 if nxt <= root else -1)) % 7] if nxt % 12 in scale else pcs[0]
    approach = place_in_range(step_pc, nxt - 3, nxt + 3)
    seq = [root, tone, fifth, approach]
    return [(i, 0.95, p) for i, p in enumerate(seq) if i < bar_len]


def compose_bass(ctx: Ctx) -> StemPart:
    p = ctx.preset
    pats = PATTERNS.get(p.bass_style, PATTERNS["roots"])
    notes: list[Note] = []
    for bar in ctx.music_bars():
        bar_start, bar_len = bar * 4.0, ctx.bar_len(bar)
        if bar_len <= 0:
            continue
        root = place_in_range(ctx.chord(bar)["root_pc"], LO, HI)
        for seg_start, seg_end, inten in ctx.bar_segments(bar):
            tier = TIER[inten]
            if not tier:
                continue
            vel = 70 + 10 * inten
            if p.bass_style == "walking":
                events = _walking(ctx, bar, root, bar_len) if inten >= 2 else [(0, 4, root)]
            else:
                events = [(t, d, _degree_pitch(ctx, bar, deg, root)) for t, d, deg in pats.get(tier, pats[max(pats)])]
            dens = p.layers["bass"][inten]
            seg = []
            for i, (t, d, pitch) in enumerate(events):
                if t >= bar_len or (i and dens < 1 and ctx.rng.random() > dens + 0.2):
                    continue
                seg.append(Note(bar_start + t, d, pitch, humanize_vel(ctx.rng, vel)))
            seg = keep_in_segment(seg, seg_start, seg_end)
            if seg_start > bar_start and not any(abs(n.start - seg_start) < 1e-9 for n in seg):
                seg.insert(0, Note(seg_start, min(1.0, seg_end - seg_start), root, humanize_vel(ctx.rng, vel + 6)))
            notes += seg
    notes = apply_swing(notes, p.swing)
    notes = clip_to_end(notes, ctx.end_beat, keep_final=False)
    if not ctx.loop:
        root = place_in_range(ctx.plan.tonic_pc, LO, HI)
        notes.append(Note(float(ctx.end_beat), max(0.5, min(2.0, 0.4 * ctx.tail_beats)), root, 105))
    return StemPart("bass", p.programs["bass"], False, sorted(notes, key=lambda n: n.start))
