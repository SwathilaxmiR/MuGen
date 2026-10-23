"""Optional LLM adapter (INTERPRETER=llm). Same PromptSpec schema; validated; falls back to rules on failure.

Uses the official Anthropic SDK (install with `pip install -e ".[llm]"`). Never used by tests or the default path.
"""
import json

from ..config import get_settings
from ..errors import warning
from ..styles import load_presets
from .base import Flags, PromptSpec

SYSTEM = (
    "You turn a request for instrumental background music into JSON settings for a symbolic composer. "
    "Pick the single closest style from the allowed list. valence is -1 (dark/sad) to 1 (bright/happy); "
    "energy is 0 (very calm) to 1 (very intense). If the prompt is not English, translate it into a short "
    "English description in english_prompt. Never reproduce or name any artist, song or film; describe only "
    "generic mood and genre."
)


def _schema(styles: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["style", "valence", "energy", "mode", "descriptors", "english_prompt", "language"],
        "properties": {
            "style": {"type": "string", "enum": styles},
            "valence": {"type": "number"},
            "energy": {"type": "number"},
            "mode": {"type": "string", "enum": ["major", "minor", "any"]},
            "descriptors": {"type": "array", "items": {"type": "string"}},
            "english_prompt": {"type": "string"},
            "language": {"type": "string"},
        },
    }


class LLMAdapter:
    name = "llm"

    def analyze(self, cleaned: str, original: str) -> tuple[PromptSpec, list[dict]]:
        s = get_settings()
        if s.fault_inject == "llm_fail":
            raise RuntimeError("fault injected: llm_fail")
        if not s.llm_api_key:
            raise RuntimeError("LLM_API_KEY not set")
        import anthropic  # optional dependency

        presets = load_presets()
        client = anthropic.Anthropic(api_key=s.llm_api_key, timeout=s.llm_timeout_s, max_retries=1)
        resp = client.beta.messages.create(
            model=s.llm_model,
            max_tokens=1024,
            system=SYSTEM,
            output_config={"effort": "low",
                           "format": {"type": "json_schema", "schema": _schema(sorted(presets))}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": cleaned or original}],
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("LLM declined the request")
        text = next(b.text for b in resp.content if b.type == "text")
        data = json.loads(text)
        p = presets[data["style"]]
        mode = data["mode"] if data["mode"] in p.modes else None
        lang = (data.get("language") or "en")[:2].lower()
        warnings = []
        flags = Flags(language=lang)
        if lang != "en":
            flags.translated = True
            warnings.append(warning("PROMPT_TRANSLATED", "Prompt translated by the LLM adapter.",
                                    method="llm", language=lang, english=data["english_prompt"]))
        spec = PromptSpec(style=p.name, valence=max(-1, min(1, float(data["valence"]))),
                          energy=max(0, min(1, float(data["energy"]))), mode=mode,
                          descriptors=data["descriptors"][:12], flags=flags, cleaned_prompt=cleaned,
                          english_prompt=data["english_prompt"])
        return spec, warnings
