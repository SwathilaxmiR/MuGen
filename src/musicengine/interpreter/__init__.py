"""Prompt -> PromptSpec. Safety filters run first, for every adapter."""
from ..config import get_settings
from ..errors import warning
from ..logging import get_logger
from .base import PromptSpec, apply_safety
from .llm import LLMAdapter
from .mock import MockAdapter
from .rules import RulesAdapter

ADAPTERS = {"rules": RulesAdapter, "llm": LLMAdapter, "mock": MockAdapter}
log = get_logger("interpreter")


def interpret(prompt: str, adapter: str | None = None) -> tuple[PromptSpec, list[dict], dict]:
    """Return (spec, warnings, provider_info)."""
    name = adapter or get_settings().interpreter
    safety = apply_safety(prompt)
    warnings = list(safety.warnings)
    try:
        spec, w = ADAPTERS[name]().analyze(safety.text, prompt)
        used = name
    except Exception as e:  # noqa: BLE001 - any llm failure falls back to rules
        if name != "llm":
            raise
        log.warning("llm_interpreter_failed", error=str(e))
        warnings.append(warning("LLM_UNAVAILABLE_RULES_USED",
                                f"LLM interpreter failed ({type(e).__name__}); used the rules interpreter."))
        spec, w = RulesAdapter().analyze(safety.text, prompt)
        used = "rules"
    warnings += w
    spec.flags.named_work = bool(safety.named)
    spec.flags.wants_vocals = bool(safety.vocals)
    info = {"role": "interpreter", "name": used, "version": "1",
            "mode": "local" if used != "llm" else get_settings().llm_model}
    return spec, warnings, info


__all__ = ["interpret", "PromptSpec"]
