"""Correlation IDs, bearer auth, in-memory rate limiting, JSON error handlers."""
import hmac
import re
import threading
import time
import uuid
from collections import defaultdict, deque

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..config import get_settings
from ..errors import ApiError, error_body
from ..logging import get_logger

log = get_logger("api")
_CID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
OPEN_PATHS = {"/health", "/ready", "/api/v1/health", "/api/v1/ready", "/openapi.json", "/docs", "/redoc",
              "/docs/oauth2-redirect"}


class RateLimiter:
    """Sliding 60 s window per (client, bucket). One API process; scale-out needs a shared store."""

    def __init__(self):
        self.hits: dict[tuple, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key: tuple, limit: int) -> float | None:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= limit:
                return 60 - (now - q[0])
            q.append(now)
        return None


limiter = RateLimiter()


def _client_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return "tok:" + auth[7:][:16]
    return "ip:" + (request.client.host if request.client else "unknown")


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_auth_ratelimit(request: Request, call_next):
        cid = request.headers.get("x-correlation-id", "")
        if not _CID_RE.match(cid):
            cid = str(uuid.uuid4())
        request.state.correlation_id = cid
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=cid)
        t0 = time.perf_counter()
        resp = await _guarded(request, call_next)
        resp.headers["X-Correlation-Id"] = cid
        log.info("request", method=request.method, path=request.url.path, status=resp.status_code,
                 ms=round((time.perf_counter() - t0) * 1000, 1))
        return resp

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        headers = {"Retry-After": str(exc.details.get("retry_after_s", 1))} if exc.code == "RATE_LIMITED" else None
        return JSONResponse(exc.body(), status_code=exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(error_body("VALIDATION_ERROR", "Request body or parameters are invalid.", False,
                                       {"errors": errors}), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE",
                401: "UNAUTHORIZED"}.get(exc.status_code, "INTERNAL_ERROR")
        return JSONResponse(error_body(code, str(exc.detail), False), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _crash(request: Request, exc: Exception):
        log.error("unhandled", error=f"{type(exc).__name__}: {exc}")
        return JSONResponse(error_body("INTERNAL_ERROR", "Unexpected server error.", True), status_code=500)


async def _guarded(request: Request, call_next):
    s = get_settings()
    path = request.url.path
    if path not in OPEN_PATHS:
        if s.api_token:
            auth = request.headers.get("authorization", "")
            token = auth[7:] if auth.lower().startswith("bearer ") else ""
            if not hmac.compare_digest(token.encode(), s.api_token.encode()):
                return JSONResponse(error_body("UNAUTHORIZED", "Missing or invalid bearer token.", False),
                                    status_code=401, headers={"WWW-Authenticate": "Bearer"})
        write = request.method in ("POST", "PUT", "PATCH", "DELETE")
        limit = s.rate_limit_per_min if write else s.rate_limit_per_min * 10
        wait = limiter.check((_client_key(request), "write" if write else "read"), limit)
        if wait is not None:
            return JSONResponse(error_body("RATE_LIMITED", f"Rate limit of {limit} requests/min exceeded.", True,
                                           {"retry_after_s": round(wait, 1), "limit_per_min": limit}),
                                status_code=429, headers={"Retry-After": str(max(1, int(wait)))})
    return await call_next(request)
