"""PromptSpec + request -> Plan: tempo, key, grid, sections, chord per bar, per-bar intensity.

The Plan is saved as plan.json so a single stem can be regenerated later with identical structure.
"""
import secrets
from dataclasses import asdict, dataclass, field

import numpy as np

from ..interpreter.base import PromptSpec
from ..schemas import MusicRequest, parse_key
from ..styles import STEMS, Preset, get_preset
from .sections import Section, intensity_at_beat, plan_sections
from .timegrid import BEATS_PER_BAR, Grid, plan_grid

MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
DEFAULT_KEYS = {"major": ["C", "D", "Eb", "F", "G", "A", "Bb"], "minor": ["A", "B", "C", "D", "E", "F#", "G"]}
FALLBACK_PROG = {"major": [["I", "V", "vi", "IV"]], "minor": [["i", "VI", "III", "VII"]]}
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7}


def scale_pcs(tonic: int, mode: str) -> set[int]:
    """Key pitch classes. Minor includes the raised 7th (harmonic-minor V chord)."""
    steps = MAJOR if mode == "major" else MINOR
    pcs = {(tonic + s) % 12 for s in steps}
    if mode == "minor":
        pcs.add((tonic + 11) % 12)
    return pcs


def parse_roman(sym: str, tonic: int, mode: str) -> dict:
    """'bVII', 'ii7', 'Imaj7', 'V7', 'vi' -> {root_pc, intervals, chromatic}."""
    s = sym
    flat = s.startswith("b")
    if flat:
        s = s[1:]
    i = 0
    while i < len(s) and s[i] in "ivIV":
        i += 1
    num, suffix = s[:i], s[i:]
    degree = _ROMAN[num.lower()]
    upper = num.isupper()
    steps = MAJOR if mode == "major" else MINOR
    root = (tonic + steps[degree - 1] - (1 if flat else 0)) % 12
    if flat:  # explicit chromatic flag: bII / bVII are taken from the major scale degree, lowered
        root = (tonic + MAJOR[degree - 1] - 1) % 12
    if suffix == "dim":
        iv = (0, 3, 6)
    elif suffix == "maj7":
        iv = (0, 4, 7, 11)
    elif suffix == "7":
        iv = (0, 4, 7, 10) if upper else (0, 3, 7, 10)
    else:
        iv = (0, 4, 7) if upper else (0, 3, 7)
    return {"symbol": sym, "root_pc": root, "intervals": list(iv), "chromatic": flat}


@dataclass
class Plan:
    style: str
    seed: int
    stem_seeds: dict[str, int]
    stem_variants: dict[str, int]
    tonic_pc: int
    mode: str
    key_name: str
    sample_rate: int
    target_lufs: float
    grid: dict
    sections: list[dict]
    chords: list[dict]            # one per bar (incl. the hit bar for non-loop)
    bar_intensity: list[int]
    bar_build: list[bool]
    energy: float
    valence: float
    swing: float
    allowed_pcs: list[int]
    warnings: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------- helpers
    @property
    def g(self) -> Grid:
        d = dict(self.grid)
        d.pop("warnings", None)
        return Grid(**d)

    @property
    def preset(self) -> Preset:
        return get_preset(self.style)

    def section_objs(self) -> list[Section]:
        return [Section(**s) for s in self.sections]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(**d)


def stem_seed(seed: int, stem: str, variant: int = 0) -> int:
    from zlib import crc32

    return int(np.random.default_rng([seed, crc32(stem.encode()), variant]).integers(0, 2**31 - 1))


def make_plan(req: MusicRequest, spec: PromptSpec) -> Plan:
    preset = get_preset(spec.style)
    warnings: list[dict] = []
    seed = req.seed if req.seed is not None else secrets.randbelow(2**31 - 1)
    rng = np.random.default_rng([seed, 0])

    # ---- key
    key_text = req.key or spec.key_hint
    if key_text:
        tonic, mode, key_name = parse_key(key_text)
    else:
        mode = spec.mode or preset.default_mode
        if mode not in preset.modes:
            mode = preset.default_mode
        letter = DEFAULT_KEYS[mode][int(rng.integers(len(DEFAULT_KEYS[mode])))]
        tonic, mode, key_name = parse_key(f"{letter} {mode}")

    # ---- tempo
    lo, hi = preset.tempo.min, preset.tempo.max
    if spec.flags.contradictory:
        pos = 0.3
    else:
        pos = 0.5 + 0.8 * (spec.energy - preset.energy)
    pos = min(max(pos, 0.0), 1.0)
    centre = lo + pos * (hi - lo)
    fixed = req.tempo_bpm if req.tempo_bpm is not None else spec.tempo_hint
    grid = plan_grid(req.duration_s, req.output.sample_rate, tempo_bpm=fixed, loopable=req.loopable,
                     tempo_range=(lo, hi), tempo_centre=centre)
    warnings += grid.warnings

    # ---- sections
    from ..config import get_settings

    base = preset.base_intensity + (1 if spec.energy > preset.energy + 0.2 else
                                    -1 if spec.energy < preset.energy - 0.2 else 0)
    base = min(max(base, 1), 4)
    secs, w = plan_sections(grid, [s.model_dump() for s in req.sections] if req.sections else None,
                            min_gap_s=get_settings().min_section_gap_s, prompt_text=spec.english_prompt,
                            base_intensity=base)
    warnings += w

    # ---- chords per bar (progression restarts, with a fresh variation, at each section)
    progs = preset.progressions.get(mode) or FALLBACK_PROG[mode]
    if grid.hit_on_bar:
        n_bars_total = grid.n_bars + (0 if grid.loop else 1)  # + the bar holding the final hit
    else:
        n_bars_total = grid.n_beats // BEATS_PER_BAR + 1
    chords, intens, builds = [], [], []
    prog = progs[int(rng.integers(len(progs)))]
    pos_in_prog = 0
    prev_sec = None
    for bar in range(n_bars_total):
        sec = intensity_at_beat(secs, bar * BEATS_PER_BAR)
        if sec is not prev_sec and bar > 0:
            if len(progs) > 1:
                choices = [p for p in progs if p != prog]
                prog = choices[int(rng.integers(len(choices)))]
            pos_in_prog = 0
        prev_sec = sec
        sym = prog[pos_in_prog % len(prog)]
        pos_in_prog += 1
        chords.append(parse_roman(sym, tonic, mode))
        intens.append(sec.intensity)
        builds.append(sec.build)
    if not grid.loop:
        chords[-1] = parse_roman("I" if mode == "major" else "i", tonic, mode)  # resolve on the hit
        if len(chords) >= 3 and chords[-2]["symbol"] not in ("V", "V7", "IV", "bVII", "VII"):
            chords[-2] = parse_roman("V", tonic, mode)  # cadence into the final hit
    elif len(chords) >= 2:
        chords[-1] = parse_roman("V" if mode == "major" else "VII", tonic, mode)  # leads back to bar 0

    allowed = scale_pcs(tonic, mode)
    for c in chords:
        if c["chromatic"]:
            allowed |= {(c["root_pc"] + i) % 12 for i in c["intervals"]}

    gd = asdict(grid)
    gd.pop("warnings")
    return Plan(style=preset.name, seed=seed, stem_seeds={s: stem_seed(seed, s) for s in STEMS},
                stem_variants={s: 0 for s in STEMS}, tonic_pc=tonic, mode=mode, key_name=key_name,
                sample_rate=req.output.sample_rate, target_lufs=req.output.target_lufs, grid=gd,
                sections=[s.to_dict() for s in secs], chords=chords, bar_intensity=intens, bar_build=builds,
                energy=spec.energy, valence=spec.valence, swing=preset.swing, allowed_pcs=sorted(allowed),
                warnings=warnings)
