"""FastAPI app factory. No audio work happens in this process."""
import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .. import db
from ..config import get_settings
from ..logging import configure, get_logger
from ..storage import get_storage
from . import middleware, routes

log = get_logger("api")
DESCRIPTION = """AI background music with real stems, exact length and loudness QA.

Create a job with `POST /api/v1/music/jobs` (202 + `status_url`), poll `GET /api/v1/jobs/{job_id}` or pass
`callback_url` (signed with `X-IncuBrix-Signature: sha256=<HMAC-SHA256(body, CALLBACK_SECRET)>`).
All errors are JSON: `{"error": {"code", "message", "retryable", "details"}}`."""


def readiness() -> tuple[bool, dict]:
    s = get_settings()
    checks: dict[str, str] = {}
    try:
        with db.conn_ctx() as c:
            db.ping(c)
        checks["database"] = "ok"
    except Exception as e:  # noqa: BLE001 - report any failure as not ready
        checks["database"] = f"fail: {type(e).__name__}"
    try:
        get_storage().bucket_ok()
        checks["s3_bucket"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["s3_bucket"] = f"fail: {type(e).__name__}"
    if "fluidsynth" in (s.renderer, s.renderer_fallback):
        checks["soundfont"] = "ok" if os.path.isfile(s.soundfont_path) else "fail: missing"
        checks["fluidsynth"] = "ok" if shutil.which(s.fluidsynth_bin) else "fail: missing"
    checks["ffmpeg"] = "ok" if shutil.which(s.ffmpeg_bin) else "fail: missing"
    return all(v == "ok" for v in checks.values()), checks


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    pool = None
    try:
        with db.conn_ctx() as c:
            db.migrate(c)
        pool = ConnectionPool(s.database_url, min_size=1, max_size=10, open=True,
                              kwargs={"row_factory": dict_row, "autocommit": True})
        routes.set_pool(pool)
    except Exception as e:  # noqa: BLE001 - /ready reports it; routes fall back to direct connections
        log.error("startup_db_failed", error=str(e))
    yield
    routes.set_pool(None)
    if pool:
        pool.close()


def create_app() -> FastAPI:
    s = get_settings()
    configure(s.log_level)
    app = FastAPI(title="IncuBrix Music Engine", version="1.0.0", description=DESCRIPTION, lifespan=lifespan)
    middleware.install(app)

    def health():
        return {"status": "ok"}

    def ready():
        ok, checks = readiness()
        return JSONResponse({"status": "ready" if ok else "not_ready", "checks": checks},
                            status_code=200 if ok else 503)

    for prefix in ("", "/api/v1"):
        app.add_api_route(f"{prefix}/health", health, methods=["GET"], tags=["ops"], include_in_schema=not prefix,
                          summary="Liveness")
        app.add_api_route(f"{prefix}/ready", ready, methods=["GET"], tags=["ops"], include_in_schema=not prefix,
                          summary="Readiness: database, bucket, SoundFont, fluidsynth, ffmpeg")
    app.include_router(routes.router)
    return app


app = create_app()
