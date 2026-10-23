"""Error and warning codes. README lists every code defined here."""
from typing import Any

# code -> (http status, retryable)
API_ERRORS: dict[str, tuple[int, bool]] = {
    "VALIDATION_ERROR": (422, False),
    "UNAUTHORIZED": (401, False),
    "RATE_LIMITED": (429, True),
    "QUEUE_FULL": (503, True),
    "JOB_NOT_FOUND": (404, False),
    "IDEMPOTENCY_KEY_REUSED": (409, False),
    "PARENT_JOB_NOT_READY": (409, True),
    "STEM_NOT_FOUND": (422, False),
    "PAYLOAD_TOO_LARGE": (413, False),
    "INTERNAL_ERROR": (500, True),
}

JOB_ERRORS = {"RENDER_FAILED", "JOB_TIMEOUT", "MIX_QA_FAILED", "STORAGE_ERROR", "INTERNAL_ERROR"}

WARNINGS = {
    "CONTRADICTORY_PROMPT",
    "NAMED_WORK_IGNORED",
    "VOCALS_NOT_SUPPORTED",
    "PROMPT_LANGUAGE_FALLBACK",
    "PROMPT_TRANSLATED",
    "VAGUE_PROMPT_DEFAULTS",
    "SECTIONS_MERGED_MIN_GAP",
    "SECTION_AFTER_END_DROPPED",
    "SECTION_SNAPPED",
    "TEMPO_ADJUSTED_FOR_LOOP",
    "TEMPO_OUTSIDE_SNAP_RANGE",
    "ENDING_ON_BEAT_NOT_BAR",
    "NARRATION_NO_SPEECH",
    "NARRATION_FETCH_FAILED",
    "NARRATION_TRUNCATED",
    "PROVIDER_FALLBACK_USED",
    "LLM_UNAVAILABLE_RULES_USED",
    "LOOP_IGNORES_ENDING",
}


class ApiError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        assert code in API_ERRORS, code
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status, self.retryable = API_ERRORS[code]

    def body(self) -> dict:
        return error_body(self.code, self.message, self.retryable, self.details)


class JobError(Exception):
    """Raised inside the pipeline; ends up in the `error` field of a failed job."""

    def __init__(self, code: str, message: str, retryable: bool = True, details: dict | None = None):
        assert code in JOB_ERRORS, code
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

    def body(self) -> dict:
        return error_body(self.code, self.message, self.retryable, self.details)["error"]


def error_body(code: str, message: str, retryable: bool, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "retryable": retryable, "details": details or {}}}


def warning(code: str, message: str, **details) -> dict:
    assert code in WARNINGS, code
    w = {"code": code, "message": message}
    if details:
        w["details"] = details
    return w
