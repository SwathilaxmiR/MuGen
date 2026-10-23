"""Section placement: default arc, drop-after-end, snap to bar/beat, min-gap merge, mood -> intensity."""
from dataclasses import asdict, dataclass

from ..errors import warning
from .timegrid import BEATS_PER_BAR, Grid

SNAP_MAX_S = 0.5

# mood word -> intensity 0..4 (first match wins, checked in order); "build" ramps 2 -> 3
MOOD_INTENSITY: list[tuple[tuple[str, ...], int]] = [
    (("peak", "climax", "uplifting", "drop", "chorus", "triumphant", "epic", "full", "huge", "max",
      "clímax", "climax", "pico", "höhepunkt", "उत्कर्ष", "உச்ச"), 4),
    (("build", "rising", "grow", "swell", "crescendo", "intensify", "subida", "montée", "aufbau"), 2),
    (("tense", "tension", "suspense", "dark", "danger", "urgent", "tenso", "tendu", "angespannt"), 3),
    (("energetic", "driving", "upbeat", "action", "intense", "groove", "busy", "main"), 3),
    (("outro", "fade", "ending", "resolve", "close", "final", "end", "final", "fin", "ende"), 1),
    (("calm", "intro", "soft", "quiet", "gentle", "ambient", "sparse", "minimal", "reflective", "sad",
      "tranquilo", "calme", "ruhig", "शांत", "அமைதி"), 1),
    (("silence", "breakdown", "break", "pause"), 0),
]
DEFAULT_INTENSITY = 2


def mood_intensity(mood: str, default: int = DEFAULT_INTENSITY) -> tuple[int, bool]:
    """Return (intensity, is_build)."""
    m = (mood or "").lower()
    for words, level in MOOD_INTENSITY:
        if any(w in m for w in words):
            return level, level == 2 and any(w in m for w in MOOD_INTENSITY[1][0])
    return default, False


@dataclass
class Section:
    requested_start_s: float | None
    applied_start_s: float
    bar: int
    beat: int
    beat_index: int
    mood: str
    intensity: int
    build: bool = False
    derived: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["applied_start_s"] = round(d["applied_start_s"], 6)
        return d


def default_arc(grid: Grid, prompt_text: str = "", base_intensity: int = 2) -> list[dict]:
    T = grid.hit_time_s
    text = prompt_text.lower()
    if T < 8:  # very short track: one section, no changes
        return [{"start_s": 0.0, "mood": "main", "_intensity": base_intensity}]
    if any(w in text for w in ("build", "builds", "rising", "crescendo", "grows")):
        return [{"start_s": 0.0, "mood": "intro", "_intensity": 1},
                {"start_s": 0.35 * T, "mood": "build", "_intensity": 2},
                {"start_s": 0.7 * T, "mood": "peak", "_intensity": 4}]
    if T < 20:
        return [{"start_s": 0.0, "mood": "intro", "_intensity": max(1, base_intensity - 1)},
                {"start_s": 0.4 * T, "mood": "main", "_intensity": base_intensity}]
    return [{"start_s": 0.0, "mood": "intro", "_intensity": max(1, base_intensity - 1)},
            {"start_s": 0.3 * T, "mood": "build", "_intensity": base_intensity},
            {"start_s": 0.65 * T, "mood": "peak", "_intensity": min(4, base_intensity + 2)}]


def _snap(t: float, grid: Grid) -> int:
    """Return a beat index: nearest bar line if within 0.5 s, else nearest beat."""
    beat = grid.beat_s
    bar_idx = round(t / grid.bar_s)
    if abs(bar_idx * grid.bar_s - t) <= SNAP_MAX_S:
        return bar_idx * BEATS_PER_BAR
    return round(t / beat)


def plan_sections(grid: Grid, requested: list[dict] | None, min_gap_s: float = 1.5,
                  prompt_text: str = "", base_intensity: int = 2,
                  mood_map=mood_intensity) -> tuple[list[Section], list[dict]]:
    warnings: list[dict] = []
    T = grid.hit_time_s
    beat = grid.beat_s
    last_beat_idx = grid.n_beats - 1  # no section may start at/after T - 1 beat

    if grid.bpm < 60:
        warnings.append(warning("TEMPO_OUTSIDE_SNAP_RANGE",
                                f"At {grid.bpm:g} bpm a beat lasts {beat:.2f}s, so a section change can "
                                f"land more than 0.5s from its requested time.", bpm=grid.bpm))

    items = sorted((dict(s) for s in requested or []), key=lambda s: float(s["start_s"]))
    derived = False
    if not items:
        items = default_arc(grid, prompt_text, base_intensity)
        derived = True

    kept = []
    for s in items:
        if float(s["start_s"]) >= T - beat - 1e-9 and float(s["start_s"]) > 0:
            warnings.append(warning("SECTION_AFTER_END_DROPPED",
                                    f"Section '{s.get('mood', '')}' at {float(s['start_s']):g}s starts at or "
                                    f"after the music ends (final hit {T:.2f}s); dropped.",
                                    start_s=float(s["start_s"])))
            continue
        kept.append(s)
    if not kept or float(kept[0]["start_s"]) > 0:
        first_mood = "intro"
        kept.insert(0, {"start_s": 0.0, "mood": first_mood, "_derived": True,
                        "_intensity": max(1, base_intensity - 1)})

    sections: list[Section] = []
    for s in kept:
        req = float(s["start_s"])
        idx = min(max(_snap(req, grid), 0), max(last_beat_idx, 0))
        applied = idx * beat
        if abs(applied - req) > 1e-3 and not s.get("_derived") and not derived:
            warnings.append(warning("SECTION_SNAPPED",
                                    f"Section '{s.get('mood', '')}' moved {applied - req:+.3f}s to the "
                                    f"{'bar line' if idx % BEATS_PER_BAR == 0 else 'beat'} at {applied:.3f}s.",
                                    requested_s=req, applied_s=round(applied, 6),
                                    delta_s=round(applied - req, 6)))
        if "_intensity" in s:
            inten, build = s["_intensity"], s.get("mood") == "build"
        else:
            inten, build = mood_map(s.get("mood", ""), base_intensity)
        sections.append(Section(
            requested_start_s=None if (s.get("_derived") or derived) else req,
            applied_start_s=applied, bar=idx // BEATS_PER_BAR, beat=idx % BEATS_PER_BAR, beat_index=idx,
            mood=s.get("mood", ""), intensity=int(inten), build=build,
            derived=bool(s.get("_derived") or derived)))

    merged: list[Section] = []
    for sec in sections:
        if merged and sec.applied_start_s - merged[-1].applied_start_s < min_gap_s - 1e-9:
            prev = merged[-1]
            warnings.append(warning("SECTIONS_MERGED_MIN_GAP",
                                    f"Sections '{prev.mood}' and '{sec.mood}' are "
                                    f"{sec.applied_start_s - prev.applied_start_s:.2f}s apart (< {min_gap_s:g}s);"
                                    f" merged at {prev.applied_start_s:.3f}s.",
                                    kept_start_s=round(prev.applied_start_s, 6),
                                    dropped_start_s=round(sec.applied_start_s, 6)))
            if sec.intensity >= prev.intensity:
                prev.intensity, prev.build = sec.intensity, sec.build
                prev.mood = sec.mood if prev.derived else f"{prev.mood}+{sec.mood}"
            continue
        merged.append(sec)
    return merged, warnings


def intensity_at_beat(sections: list[Section], beat_idx: float) -> Section:
    cur = sections[0]
    for s in sections:
        if s.beat_index <= beat_idx + 1e-9:
            cur = s
    return cur
