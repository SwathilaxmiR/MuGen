"""Signed job-status callbacks: X-IncuBrix-Signature: sha256=<hex HMAC-SHA256(body, CALLBACK_SECRET)>."""
import hashlib
import hmac
import json
import time

import httpx

from ..config import Settings, get_settings
from ..ducking import FetchError, check_public_url
from ..logging import get_logger

log = get_logger("callbacks")
BACKOFF_S = (0.5, 1.0, 2.0)


def sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify(body: bytes, header: str, secret: str) -> bool:
    return hmac.compare_digest(sign(body, secret), header or "")


def send(url: str, payload: dict, s: Settings | None = None) -> bool:
    """POST once, then up to 3 retries with backoff. Returns True on a 2xx."""
    s = s or get_settings()
    try:
        check_public_url(url, s.allow_private_urls)
    except FetchError as e:
        log.warning("callback_blocked", url=url, error=str(e))
        return False
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    headers = {"Content-Type": "application/json", "X-IncuBrix-Signature": sign(body, s.callback_secret),
               "X-Correlation-Id": payload.get("correlation_id") or ""}
    for attempt in range(len(BACKOFF_S) + 1):
        try:
            r = httpx.post(url, content=body, headers=headers, timeout=s.callback_timeout_s, follow_redirects=False)
            if 200 <= r.status_code < 300:
                log.info("callback_sent", url=url, status=r.status_code, attempt=attempt + 1)
                return True
            log.warning("callback_rejected", url=url, status=r.status_code, attempt=attempt + 1)
        except httpx.HTTPError as e:
            log.warning("callback_error", url=url, error=str(e), attempt=attempt + 1)
        if attempt < len(BACKOFF_S):
            time.sleep(BACKOFF_S[attempt])
    return False
