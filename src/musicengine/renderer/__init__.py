"""Render one stem: primary renderer (retry once) -> fallback renderer -> RENDER_FAILED.
Then riser FX, per-stem FX, loop second-pass extraction and exact-length trim."""
import time

import numpy as np

from ..composer.base import StemPart
from ..config import Settings, get_settings
from ..errors import JobError, warning
from ..logging import get_logger
from ..planner.plan import Plan
from .base import RenderSpec, fit_length, render_spec
from .fluidsynth import FluidSynthRenderer
from .fx import apply_stem_fx, riser
from .mock import MockRenderer
from .numpy_synth import NumpyRenderer

RENDERERS = {"fluidsynth": FluidSynthRenderer, "numpy": NumpyRenderer, "mock": MockRenderer}
log = get_logger("renderer")


def get_renderer(name: str, settings: Settings | None = None):
    cls = RENDERERS[name]
    return cls(settings) if cls is FluidSynthRenderer else cls()


def _raw(part: StemPart, rs: RenderSpec, s: Settings, warnings: list[dict]) -> tuple[np.ndarray, dict]:
    chain = [s.renderer] + ([s.renderer_fallback] if s.renderer_fallback and s.renderer_fallback != s.renderer else [])
    errors = []
    for i, name in enumerate(chain):
        r = get_renderer(name, s)
        for attempt in (1, 2) if i == 0 else (1,):
            t0 = time.perf_counter()
            try:
                audio = r.render(part, rs)
                info = {"renderer": name, "version": r.version(), "attempts": attempt,
                        "fallback": i > 0, "seconds": round(time.perf_counter() - t0, 4)}
                if i > 0:
                    warnings.append(warning("PROVIDER_FALLBACK_USED",
                                            f"Renderer '{chain[0]}' failed for stem '{part.name}' "
                                            f"({errors[-1]}); rendered with '{name}'.",
                                            stem=part.name, primary=chain[0], fallback=name))
                return audio, info
            except Exception as e:  # noqa: BLE001 - any renderer failure moves down the chain
                errors.append(f"{name}#{attempt}: {type(e).__name__}: {str(e)[:200]}")
                log.warning("render_failed", stem=part.name, renderer=name, attempt=attempt, error=str(e)[:300])
    raise JobError("RENDER_FAILED", f"All renderers failed for stem '{part.name}'.", retryable=True,
                   details={"errors": errors})


def render_stem(part: StemPart, plan: Plan, warnings: list[dict], settings: Settings | None = None
                ) -> tuple[np.ndarray, dict]:
    """Return ((L, 2) float32 audio after FX, info)."""
    s = settings or get_settings()
    rs = render_spec(plan)
    audio, info = _raw(part, rs, s, warnings)
    audio = audio.astype(np.float32, copy=False)
    n = len(audio)
    for k, f in enumerate(_fx_seconds(part, rs)):
        if f["type"] == "riser":
            audio += riser(n, rs.sr, f["start"], f["end"], seed=plan.stem_seeds[part.name] + k).astype(np.float32)
    t0 = time.perf_counter()
    audio = apply_stem_fx(audio, part.name, rs.sr, plan.style)
    info["fx_seconds"] = round(time.perf_counter() - t0, 4)
    if rs.loop:
        audio = audio[rs.length:2 * rs.length]  # second pass: carries the wrapped tails of the first
    return fit_length(audio, rs.length), info


def _fx_seconds(part, rs):
    from .base import fx_seconds

    return fx_seconds(part, rs)
