"""Fixed output for tests (INTERPRETER=mock)."""
from .base import PromptSpec


class MockAdapter:
    name = "mock"

    def analyze(self, cleaned: str, original: str) -> tuple[PromptSpec, list[dict]]:
        return PromptSpec(style="corporate", valence=0.5, energy=0.5, descriptors=["mock"],
                          cleaned_prompt=cleaned, english_prompt=cleaned), []
