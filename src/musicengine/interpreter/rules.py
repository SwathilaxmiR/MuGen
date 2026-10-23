"""Deterministic keyword interpreter (default adapter). No network, no keys."""
import re
import unicodedata
from functools import lru_cache
from importlib import resources

import yaml

from ..errors import warning
from ..styles import load_presets
from .base import Flags, PromptSpec

VAGUE_STYLE = "corporate"
CONTRADICTION_STYLE = "tense"


@lru_cache
def _lex():
    root = resources.files("musicengine.interpreter").joinpath("lexicon")
    en = yaml.safe_load(root.joinpath("en.yaml").read_text())
    foreign = yaml.safe_load(root.joinpath("foreign.yaml").read_text(encoding="utf-8"))
    return en, foreign


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s.lower())


def _has(text: str, phrase: str) -> bool:
    return re.search(r"(?<![\w])" + re.escape(phrase) + r"(?![\w])", text) is not None


def detect_script_language(text: str) -> str | None:
    for ch in text:
        o = ord(ch)
        if 0x0900 <= o <= 0x097F:
            return "hi"
        if 0x0B80 <= o <= 0x0BFF:
            return "ta"
        if 0x3040 <= o <= 0x30FF:
            return "ja"
    if any(0x4E00 <= ord(ch) <= 0x9FFF for ch in text):
        return "zh"
    return None


def detect_language(text: str) -> str:
    lang = detect_script_language(text)
    if lang:
        return lang
    if text.isascii():  # langdetect is unreliable on short ASCII prompts; foreign lexicons still get tried
        return "en"
    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0
        best = detect_langs(text)[0]
        return best.lang if best.prob > 0.7 else "en"
    except Exception:
        return "en"


def translate_lexicon(text: str, lang: str) -> tuple[str, list[str]]:
    """Replace known foreign words (longest first) with English ones."""
    _, foreign = _lex()
    table = foreign.get(lang, {})
    out, hits = _norm(text), []
    for word in sorted(table, key=len, reverse=True):
        w = _norm(word)
        if lang in ("ja", "zh", "hi", "ta"):
            if w in out:
                out = out.replace(w, f" {table[word]} ")
                hits.append(word)
        elif _has(out, w):
            out = re.sub(r"(?<![\w])" + re.escape(w) + r"(?![\w])", table[word], out)
            hits.append(word)
    return re.sub(r"\s+", " ", out).strip(), hits


_KEY_RE = re.compile(r"\bin\s+([a-g])\s*(#|♯|b|♭|sharp|flat)?\s*(major|minor|maj|min|m)\b", re.IGNORECASE)
_BPM_RE = re.compile(r"\b(\d{2,3})\s*(?:bpm|beats per minute)\b", re.IGNORECASE)


class RulesAdapter:
    name = "rules"

    def analyze(self, cleaned: str, original: str) -> tuple[PromptSpec, list[dict]]:
        en, _ = _lex()
        presets = load_presets()
        warnings: list[dict] = []
        flags = Flags()

        text = _norm(cleaned)
        lang = detect_language(original) if original.strip() else "en"
        style_hits, axis_hits = self._score(text, presets, en)
        if lang != "en" or (not style_hits and not axis_hits):
            # try every lexicon whose language we detected (or all, for short Latin-script prompts)
            langs = [lang] if lang in _lex()[1] else list(_lex()[1])
            for lg in langs:
                translated, hits = translate_lexicon(cleaned, lg)
                if hits:
                    text = translated
                    style_hits, axis_hits = self._score(text, presets, en)
                    flags.translated, lang = True, lg
                    warnings.append(warning("PROMPT_TRANSLATED",
                                            f"Prompt read as '{lg}' and mapped with the built-in lexicon.",
                                            method="lexicon", language=lg, matched=hits, english=text))
                    break
        flags.language = lang

        valence = sum(en["valence"][w] for w in axis_hits["valence"])
        energy_delta = sum(en["energy"][w] for w in axis_hits["energy"])
        n_val = len(axis_hits["valence"])

        if style_hits:
            style = max(style_hits, key=lambda s: (style_hits[s], -abs(presets[s].valence - valence)))
        elif n_val or axis_hits["energy"]:
            v = max(-1, min(1, valence / max(n_val, 1)))
            e = max(0, min(1, 0.5 + energy_delta))
            style = min(presets, key=lambda s: abs(presets[s].valence - v) + abs(presets[s].energy - e))
        else:
            style = None

        if style is None:
            flags.vague = True
            style = VAGUE_STYLE
            if lang != "en" and not flags.translated:
                warnings.append(warning("PROMPT_LANGUAGE_FALLBACK",
                                        f"Prompt language '{lang}' was not understood; used neutral defaults "
                                        f"({style}).", language=lang))
            else:
                warnings.append(warning("VAGUE_PROMPT_DEFAULTS",
                                        f"Prompt had no recognisable mood or genre words; used the neutral "
                                        f"'{style}' preset at moderate energy."))

        p = presets[style]
        v = p.valence if not n_val else max(-1, min(1, 0.5 * p.valence + 0.5 * valence / n_val))
        e = max(0.0, min(1.0, p.energy + 0.6 * energy_delta))
        mode = None
        if v < -0.25 and "minor" in p.modes:
            mode = "minor"
        elif v > 0.25 and "major" in p.modes:
            mode = "major"

        high = [w for w in en["contradiction"]["high"] if _has(text, w)]
        low = [w for w in en["contradiction"]["low"] if _has(text, w)]
        if high and low:
            flags.contradictory = True
            opposed = set(high) | set(low)
            genre_hits = {k: v for k, v in style_hits.items()
                          if any(_has(text, kw) for kw in presets[k].keywords if kw not in opposed)}
            if not genre_hits:
                style, p = CONTRADICTION_STYLE, presets[CONTRADICTION_STYLE]
            e = 0.5
            mode = "minor" if "minor" in p.modes else p.default_mode
            warnings.append(warning(
                "CONTRADICTORY_PROMPT",
                f"Prompt asks for both {high[0]!r} and {low[0]!r}. Resolved to mid energy, {mode} mode, a "
                f"slow-to-mid tempo and hard percussive timbre ('{style}').", high=high, low=low,
                resolution={"style": style, "energy": e, "mode": mode, "tempo": "slow-to-mid"}))
        if flags.vague:
            e = 0.4

        tempo_hint = None
        if m := _BPM_RE.search(original):
            tempo_hint = float(m.group(1))
        key_hint = None
        if m := _KEY_RE.search(original):
            acc = {"#": "#", "♯": "#", "sharp": "#", "b": "b", "♭": "b", "flat": "b"}.get((m.group(2) or "").lower(), "")
            q = m.group(3).lower()
            key_hint = f"{m.group(1).upper()}{acc} {'minor' if q in ('minor', 'min', 'm') else 'major'}"

        descriptors = sorted({*axis_hits["valence"], *axis_hits["energy"],
                              *[k for s in style_hits for k in presets[s].keywords if _has(text, k)]})
        spec = PromptSpec(style=style, valence=round(v, 3), energy=round(e, 3), mode=mode, tempo_hint=tempo_hint,
                          key_hint=key_hint, descriptors=descriptors, flags=flags, cleaned_prompt=cleaned,
                          english_prompt=text, style_scores=style_hits)
        return spec, warnings

    @staticmethod
    def _score(text: str, presets, en):
        style_hits: dict[str, float] = {}
        for name, p in presets.items():
            score = sum(1.0 for k in p.keywords if _has(text, k))
            if _has(text, name):
                score += 1.0
            if score:
                style_hits[name] = score
        axis = {"valence": [w for w in en["valence"] if _has(text, w)],
                "energy": [w for w in en["energy"] if _has(text, w)]}
        return style_hits, axis
