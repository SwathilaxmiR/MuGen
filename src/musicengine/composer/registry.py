"""Stem registry. Adding a stem type = one composer function + one line here (+ a program in presets)."""
import numpy as np

from ..planner.plan import Plan, stem_seed
from .base import Ctx, StemPart
from .bass import compose_bass
from .drums import compose_drums
from .harmony import compose_harmony
from .melody import compose_melody

STEM_REGISTRY = {
    "drums": compose_drums,
    "bass": compose_bass,
    "harmony": compose_harmony,
    "melody": compose_melody,
}


def compose_stem(plan: Plan, stem: str) -> StemPart:
    rng = np.random.default_rng([plan.stem_seeds[stem], plan.stem_variants.get(stem, 0)])
    return STEM_REGISTRY[stem](Ctx(plan, rng))


def compose_all(plan: Plan) -> dict[str, StemPart]:
    return {s: compose_stem(plan, s) for s in STEM_REGISTRY}


def reseed(plan: Plan, stem: str, seed: int | None) -> int:
    """New seed for one stem (explicit, or derived from parent seed + stem + n)."""
    plan.stem_variants[stem] = plan.stem_variants.get(stem, 0) + 1
    plan.stem_seeds[stem] = seed if seed is not None else stem_seed(plan.seed, stem, plan.stem_variants[stem])
    return plan.stem_seeds[stem]
