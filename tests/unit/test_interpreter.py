import pytest

from musicengine.config import get_settings
from musicengine.interpreter import interpret
from musicengine.interpreter.base import apply_safety
from musicengine.styles import FORBIDDEN_PROGRAMS, STEMS, load_presets

TEN_PROMPTS = {
    "Epic cinematic orchestral score that builds to a heroic climax": "cinematic",
    "chill lo-fi beats for studying late at night": "lofi",
    "upbeat corporate background for a tech product explainer": "corporate",
    "energetic EDM festival track with a big drop": "electronic",
    "warm acoustic guitar folk for a travel vlog": "acoustic",
    "tense suspense thriller underscore, dark and ominous": "tense",
    "playful quirky cartoon music for kids": "playful",
    "calm ambient meditation pad, peaceful and serene": "ambient",
    "driving rock with guitar riffs for a sports montage": "rock",
    "smooth jazz lounge with saxophone": "jazz",
    "happy cheerful summer celebration": "upbeat",
    "massive trailer battle music, epic and powerful": "epic",
}


def codes(ws):
    return [w["code"] for w in ws]


def test_twelve_presets_load_and_validate():
    presets = load_presets()
    assert len(presets) >= 12
    for p in presets.values():
        assert set(p.programs) == set(STEMS)
        assert not ({p.programs[s] for s in STEMS if s != "drums"} & FORBIDDEN_PROGRAMS)


def test_no_vocal_programs_anywhere():
    for p in load_presets().values():
        for stem, prog in p.programs.items():
            if stem != "drums":
                assert prog not in FORBIDDEN_PROGRAMS, (p.name, stem, prog)


def test_ten_prompts_distinct_presets():
    got = {p: interpret(p)[0].style for p in TEN_PROMPTS}
    assert got == TEN_PROMPTS
    assert len(set(got.values())) >= 8


def test_named_song_stripped():
    spec, ws, _ = interpret("song in the style of Hans Zimmer, dark and epic")
    assert "NAMED_WORK_IGNORED" in codes(ws)
    assert "zimmer" not in spec.cleaned_prompt.lower()
    assert spec.style in ("epic", "tense", "cinematic")
    spec, ws, _ = interpret('make me a cover of "Bohemian Rhapsody" but calm')
    assert "NAMED_WORK_IGNORED" in codes(ws)
    assert "bohemian" not in spec.cleaned_prompt.lower()


def test_generic_like_is_kept():
    res = apply_safety("music that feels like a sunrise over the ocean")
    assert not res.named
    assert "sunrise" in res.text


def test_vocals_stripped_and_warned():
    spec, ws, _ = interpret("upbeat pop with a female singer and catchy lyrics")
    assert "VOCALS_NOT_SUPPORTED" in codes(ws)
    assert spec.flags.wants_vocals
    assert "lyrics" not in spec.cleaned_prompt


def test_named_and_vocals_together():
    _, ws, _ = interpret("in the style of Hans Zimmer with a choir singing")
    assert {"NAMED_WORK_IGNORED", "VOCALS_NOT_SUPPORTED"} <= set(codes(ws))


def test_no_vocals_is_not_a_warning():
    _, ws, _ = interpret("instrumental cinematic, no vocals")
    assert "VOCALS_NOT_SUPPORTED" not in codes(ws)
    _, ws, _ = interpret("acoustic singer-songwriter vibe for a voice-over")
    assert "VOCALS_NOT_SUPPORTED" not in codes(ws)


def test_contradiction_resolved():
    spec, ws, _ = interpret("calm but aggressive")
    assert "CONTRADICTORY_PROMPT" in codes(ws)
    assert spec.energy == 0.5 and spec.mode == "minor" and spec.style == "tense"


def test_vague_defaults():
    for p in ["music", "something", "xqzv blorp"]:
        spec, ws, _ = interpret(p)
        assert "VAGUE_PROMPT_DEFAULTS" in codes(ws), p
        assert spec.style == "corporate"


@pytest.mark.parametrize("prompt,lang,style", [
    ("música tranquila y relajante para meditar", "es", "ambient"),
    ("संगीत शांत और रहस्यमय फिल्म", "hi", None),
    ("அமைதியான இசை", "ta", "ambient"),
    ("穏やかな映画音楽", "ja", "cinematic"),
    ("musique électronique énergique pour danser", "fr", "electronic"),
])
def test_non_english(prompt, lang, style):
    spec, ws, _ = interpret(prompt)
    assert spec.flags.language == lang
    assert "PROMPT_TRANSLATED" in codes(ws)
    if style:
        assert spec.style == style


def test_unknown_language_falls_back():
    spec, ws, _ = interpret("Здравствуйте друзья мои")  # Russian, no lexicon
    assert "PROMPT_LANGUAGE_FALLBACK" in codes(ws)


def test_tempo_and_key_hints():
    spec, _, _ = interpret("corporate track in F# minor at 96 bpm")
    assert spec.tempo_hint == 96 and spec.key_hint == "F# minor"


def test_llm_failure_falls_back(monkeypatch):
    monkeypatch.setattr(get_settings(), "fault_inject", "llm_fail")
    spec, ws, info = interpret("smooth jazz lounge", adapter="llm")
    assert "LLM_UNAVAILABLE_RULES_USED" in codes(ws)
    assert spec.style == "jazz" and info["name"] == "rules"


def test_llm_without_key_falls_back(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_api_key", "")
    _, ws, _ = interpret("smooth jazz lounge", adapter="llm")
    assert "LLM_UNAVAILABLE_RULES_USED" in codes(ws)


def test_mock_adapter():
    spec, ws, info = interpret("anything at all", adapter="mock")
    assert spec.style == "corporate" and info["name"] == "mock" and not ws
