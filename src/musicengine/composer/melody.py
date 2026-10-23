"""Melody: a 1-2 bar motif from rhythm templates, scale-degree random walk with chord tones on strong
beats; silent/sparse at intensity 1, fuller at 3, octave-doubled at 4; resolves to the tonic on the hit."""
from .base import Ctx, Note, StemPart, apply_swing, clip_to_end, humanize_vel

# style -> rhythm templates (onset, dur) over 2 bars (8 beats)
RHYTHMS = {
    "lyrical": [[(0, 1.5), (1.5, 0.5), (2, 2), (4, 1), (5, 1), (6, 2)],
                [(0, 2), (2, 1), (3, 1), (4, 3), (7, 1)],
                [(0.5, 0.5), (1, 1), (2, 1.5), (3.5, 0.5), (4, 4)]],
    "sparse": [[(0, 3), (4, 2), (6, 2)], [(1, 2), (4, 4)], [(0, 1.5), (2, 2), (6, 2)]],
    "pluck": [[(0, 0.5), (0.5, 0.5), (1.5, 0.5), (2, 1), (3, 0.5), (4, 0.5), (4.5, 0.5), (5.5, 0.5), (6, 1.5)],
              [(0, 0.75), (0.75, 0.75), (1.5, 0.5), (2.5, 1), (4, 0.75), (4.75, 0.75), (5.5, 0.5), (6.5, 1)]],
    "riff": [[(0, 0.5), (0.75, 0.25), (1, 0.5), (1.5, 0.5), (2.5, 0.5), (3, 0.5), (3.5, 0.5),
              (4, 0.5), (4.75, 0.25), (5, 0.5), (5.5, 0.5), (6.5, 0.5), (7, 1)],
             [(0, 0.75), (0.75, 0.75), (1.5, 0.5), (2, 0.5), (3, 1), (4, 0.75), (4.75, 0.75), (5.5, 0.5), (6, 2)]],
    "ostinato": [[(i * 0.5, 0.45) for i in range(16)]],
    "bouncy": [[(0, 0.5), (1, 0.5), (1.5, 0.5), (2, 1), (3, 0.5), (4, 0.5), (4.5, 0.5), (5, 0.5), (6, 1.5)],
               [(0, 0.25), (0.5, 0.5), (1, 0.5), (2, 0.5), (2.5, 0.5), (3, 1), (4, 0.5), (5, 0.5), (6, 2)]],
    "anthem": [[(0, 1), (1, 1), (2, 2), (4, 1.5), (5.5, 0.5), (6, 2)],
               [(0, 2), (2, 1), (3, 1), (4, 2), (6, 1), (7, 1)]],
}
START_INTENSITY = {"sparse": 1, "ostinato": 2}


def _walk(ctx: Ctx, rhythm, bar0: int, centre_deg: int, register: int, scale: list[int]) -> list[tuple]:
    """Return [(onset_in_motif, dur, degree)] using a bounded random walk over scale degrees."""
    deg = centre_deg
    out = []
    for t, d in rhythm:
        step = int(ctx.rng.choice([-2, -1, -1, 0, 1, 1, 2, 3, -3], p=[.1, .2, .15, .05, .2, .15, .07, .04, .04]))
        deg = max(-4, min(9, deg + step))
        bar = bar0 + int(t // 4)
        strong = abs(t % 2) < 1e-9
        if strong:
            deg = _nearest_chord_degree(ctx, bar, deg, scale)
        out.append((t, d, deg))
    return out


def _nearest_chord_degree(ctx: Ctx, bar: int, deg: int, scale: list[int]) -> int:
    pcs = set(ctx.chord_pcs(bar))
    for delta in (0, -1, 1, -2, 2, 3, -3):
        if scale[(deg + delta) % 7] in pcs:
            return max(-4, min(9, deg + delta))
    return deg


def deg_to_pitch(deg: int, scale: list[int], register: int, tonic: int) -> int:
    octave, idx = divmod(deg, 7)
    base = register - ((register - tonic) % 12)  # tonic at or below the register centre
    pc_off = (scale[idx] - tonic) % 12
    return base + 12 * octave + pc_off


def compose_melody(ctx: Ctx) -> StemPart:
    p = ctx.preset
    style = p.melody_style
    templates = RHYTHMS.get(style, RHYTHMS["lyrical"])
    scale = ctx.scale()
    tonic = ctx.plan.tonic_pc
    reg = p.melody_register
    notes: list[Note] = []
    rhythm = templates[int(ctx.rng.integers(len(templates)))]
    motif = None
    short = ctx.grid.duration_s < 8
    min_int = START_INTENSITY.get(style, 2)
    bars = list(ctx.music_bars())
    phrase = 0
    for bar in bars[::2]:
        if max(ctx.intensity_at(bar * 4.0 + b) for b in range(8)) < min_int and not short:
            motif = None
            continue
        # new motif at every section change, variation every second phrase (A A' A B)
        sec_change = any(b in ctx.section_start_bars() for b in (bar, bar + 1))
        if motif is None or sec_change:
            rhythm = templates[int(ctx.rng.integers(len(templates)))]
            motif = _walk(ctx, rhythm, bar, int(ctx.rng.integers(0, 4)), reg, scale)
            phrase = 0
        cur = list(motif)
        if phrase % 4 == 1 and len(cur) > 2:
            cur[-2:] = _walk(ctx, [(t, d) for t, d, _ in cur[-2:]], bar, cur[-3][2], reg, scale)
        elif phrase % 4 == 3:
            cur = _walk(ctx, [(t, d) for t, d, _ in cur], bar, cur[0][2], reg, scale)
        phrase += 1
        for i, (t, d, deg) in enumerate(cur):
            b = bar + int(t // 4)
            if b not in bars:
                continue
            note_int = ctx.intensity_at(bar * 4.0 + t)
            if note_int < min_int and not short:
                continue
            dens = p.layers["melody"][note_int] if not short else 0.8
            if i and ctx.rng.random() > dens + 0.1:
                continue
            # re-check chord tones on strong beats against the actual bar (motif may repeat over new chords)
            if abs(t % 2) < 1e-9:
                deg = _nearest_chord_degree(ctx, b, deg, scale)
            pitch = deg_to_pitch(deg, scale, reg, tonic)
            vel = humanize_vel(ctx.rng, 72 + 8 * note_int)
            notes.append(Note(bar * 4.0 + t, d * 0.95, pitch, vel))
            if note_int >= 4:
                notes.append(Note(bar * 4.0 + t, d * 0.95, pitch + 12 if pitch < 84 else pitch - 12, int(vel * 0.75)))
    notes = apply_swing(notes, p.swing)
    notes = clip_to_end(notes, ctx.end_beat, keep_final=False)
    if not ctx.loop:
        pitch = deg_to_pitch(0, scale, reg, tonic)
        notes.append(Note(float(ctx.end_beat), max(0.5, min(2.0, 0.4 * ctx.tail_beats)), pitch, 92))
    return StemPart("melody", p.programs["melody"], False, sorted(notes, key=lambda n: (n.start, n.pitch)))
