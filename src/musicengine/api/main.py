"""FastAPI app factory. No audio work happens in this process."""
import os
import shutil

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .. import db
from ..config import get_settings
from ..logging import configure, get_logger
from ..storage import get_storage

log = get_logger("api")


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
    if s.renderer == "fluidsynth" or s.renderer_fallback == "fluidsynth":
        checks["soundfont"] = "ok" if os.path.isfile(s.soundfont_path) else "fail: missing"
        checks["fluidsynth"] = "ok" if shutil.which(s.fluidsynth_bin) else "fail: missing"
    checks["ffmpeg"] = "ok" if shutil.which(s.ffmpeg_bin) else "fail: missing"
    return all(v == "ok" for v in checks.values()), checks


def create_app() -> FastAPI:
    s = get_settings()
    configure(s.log_level)
    app = FastAPI(title="IncuBrix Music Engine", version="1.0.0",
                  description="AI background music with real stems, exact length and loudness QA.")

    @app.on_event("startup")
    def _startup():
        try:
            with db.conn_ctx() as c:
                db.migrate(c)
        except Exception as e:  # noqa: BLE001 - /ready reports it
            log.error("migrate_failed", error=str(e))

    def health():
        return {"status": "ok"}

    def ready():
        ok, checks = readiness()
        return JSONResponse({"status": "ready" if ok else "not_ready", "checks": checks},
                            status_code=200 if ok else 503)

    for prefix in ("", "/api/v1"):
        app.add_api_route(f"{prefix}/health", health, methods=["GET"], tags=["ops"],
                          include_in_schema=prefix == "")
        app.add_api_route(f"{prefix}/ready", ready, methods=["GET"], tags=["ops"],
                          include_in_schema=prefix == "")
    return app


app = create_app()
