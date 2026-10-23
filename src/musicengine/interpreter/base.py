"""PromptSpec + safety filters that run before every adapter."""
import re
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, Field

from ..errors import warning


class Flags(BaseModel):
    named_work: bool = False
    wants_vocals: bool = False
    contradictory: bool = False
    language: str = "en"
    translated: bool = False
    vague: bool = False


class PromptSpec(BaseModel):
    style: str
    valence: float = Field(0.0, ge=-1, le=1)
    energy: float = Field(0.5, ge=0, le=1)
    mode: str | None = None
    tempo_hint: float | None = None
    key_hint: str | None = None
    descriptors: list[str] = Field(default_factory=list)
    flags: Flags = Field(default_factory=Flags)
    cleaned_prompt: str = ""
    english_prompt: str = ""
    style_scores: dict[str, float] = Field(default_factory=dict)


class Adapter(Protocol):
    name: str

    def analyze(self, cleaned: str, original: str) -> tuple[PromptSpec, list[dict]]: ...


# ---------------------------------------------------------------- safety filters
KNOWN_NAMES = [
    "hans zimmer", "john williams", "ennio morricone", "howard shore", "ludwig göransson", "danny elfman",
    "a.r. rahman", "ar rahman", "a r rahman", "ilaiyaraaja", "anirudh", "pritam",
    "the beatles", "beatles", "taylor swift", "daft punk", "coldplay", "beyonce", "beyoncé", "drake",
    "eminem", "ed sheeran", "adele", "queen", "metallica", "bts", "blackpink", "billie eilish",
    "the weeknd", "dua lipa", "avicii", "skrillex", "deadmau5", "calvin harris", "marshmello",
    "imagine dragons", "linkin park", "nirvana", "pink floyd", "led zeppelin", "radiohead",
    "kanye", "kanye west", "travis scott", "bad bunny", "shakira", "michael jackson", "madonna",
    "lofi girl", "nujabes", "joe hisaishi", "studio ghibli", "ghibli", "star wars", "harry potter",
    "game of thrones", "interstellar", "inception", "stranger things", "james bond", "007",
    "mission impossible", "the dark knight", "jurassic park", "lord of the rings", "pirates of the caribbean",
    "mozart", "beethoven", "bach", "chopin", "vivaldi",
]
_NAMES_RE = re.compile(r"(?<![\w])(" + "|".join(re.escape(n) for n in sorted(KNOWN_NAMES, key=len, reverse=True))
                       + r")(?![\w])", re.IGNORECASE)
_REF_RE = re.compile(
    r"\b(in the style of|style of|in the vein of|inspired by|à la|a la|sounds? like|similar to|"
    r"cover of|remix of|version of|just like|like)\s+"
    r"([^,.;!?\n]+?)(?=\s+(?:with|and|but|for|that|while|in|at)\b|[,.;!?\n]|$)", re.IGNORECASE)
_ALWAYS_REF = {"in the style of", "style of", "in the vein of", "cover of", "remix of", "version of",
               "sounds like", "sound like", "à la", "a la"}
_QUOTED_RE = re.compile(r"[\"“”«»]([^\"“”«»]{2,80})[\"“”«»]")
_VOCAL_RE = re.compile(
    r"\b(sing(?:s|ing)?|singer(?!-songwriter)|vocals?|vocalist|lyrics?|rap(?:s|ping|per)?|choir|"
    r"voices?(?![- ]?over)|a ?cappella|humming|chant(?:s|ing)?)\b", re.IGNORECASE)
_NEGATION_RE = re.compile(r"\b(no|without|non|zero|minus|instrumental)\W+(\w+\W+)?$", re.IGNORECASE)


@dataclass
class SafetyResult:
    text: str
    named: list[str] = field(default_factory=list)
    vocals: list[str] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)


def _is_named(phrase: str) -> bool:
    p = phrase.strip()
    if not p:
        return False
    if _NAMES_RE.search(p):
        return True
    # proper noun: first word capitalised and not a sentence-initial generic word
    first = p.split()[0]
    return first[:1].isupper() and first.lower() not in {"a", "an", "the", "some", "something"}


def apply_safety(prompt: str) -> SafetyResult:
    text = prompt
    vocals = [m.group(0) for m in _VOCAL_RE.finditer(text)
              if not _NEGATION_RE.search(text[:m.start()])]  # "no vocals" is a request we already meet
    text = _VOCAL_RE.sub(" ", text)
    text = re.sub(r"\b(no|without)\s+(?=[,.;]|$)", " ", text, flags=re.IGNORECASE)
    named: list[str] = []

    def _ref(m: re.Match) -> str:
        lead, phrase = m.group(1).lower(), m.group(2)
        if lead in _ALWAYS_REF or _is_named(phrase):
            named.append(m.group(0).strip())
            return " "
        return m.group(0)

    text = _REF_RE.sub(_ref, text)
    for m in _QUOTED_RE.finditer(text):
        named.append(m.group(0))
    text = _QUOTED_RE.sub(" ", text)
    for m in _NAMES_RE.finditer(text):
        named.append(m.group(0))
    text = _NAMES_RE.sub(" ", text)

    # tidy dangling connectors left by removals ("with  and", "a  track")
    text = re.sub(r"\s+", " ", text).strip(" ,.;-")
    res = SafetyResult(text=text, named=named, vocals=vocals)
    if named:
        res.warnings.append(warning("NAMED_WORK_IGNORED",
                                    "References to specific songs, artists or works were removed; only generic "
                                    "mood and genre words were used.", removed=named))
    if vocals:
        res.warnings.append(warning("VOCALS_NOT_SUPPORTED",
                                    "The engine produces instrumental music only; vocal requests were ignored.",
                                    removed=vocals))
    return res
