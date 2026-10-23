"""Idempotency-Key handling: (key, route) -> job; same body returns the same job, a different body is a 409."""
import hashlib
import json
import re

from .. import db
from ..errors import ApiError

_KEY_RE = re.compile(r"^[\x21-\x7e]{1,200}$")


def request_hash(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def validate_key(key: str | None) -> str | None:
    if key is None:
        return None
    if not _KEY_RE.match(key):
        raise ApiError("VALIDATION_ERROR", "Idempotency-Key must be 1-200 printable ASCII characters.")
    return key


def existing_job(conn, key: str | None, route: str, h: str) -> str | None:
    if not key:
        return None
    row = conn.execute("SELECT * FROM idempotency WHERE key = %s AND route = %s", (key, route)).fetchone()
    if not row:
        return None
    if row["request_hash"] != h:
        raise ApiError("IDEMPOTENCY_KEY_REUSED", "This Idempotency-Key was already used with a different body.",
                       {"job_id": str(row["job_id"])})
    return str(row["job_id"])


def create(conn, key: str | None, route: str, h: str, job_id: str, **fields) -> tuple[str, bool]:
    try:
        return db.create_job_idempotent(conn, key=key, route=route, request_hash=h, job_id=job_id, **fields)
    except db.KeyReused as e:
        raise ApiError("IDEMPOTENCY_KEY_REUSED", "This Idempotency-Key was already used with a different body.",
                       {"job_id": str(e)}) from None
