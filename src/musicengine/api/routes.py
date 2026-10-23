"""HTTP routes under /api/v1."""
import json
import uuid
from contextlib import contextmanager

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer

from .. import db
from ..composer.registry import STEM_REGISTRY
from ..config import get_settings
from ..errors import ApiError
from ..schemas import (ErrorResponse, JobAccepted, JobStatus, MusicRequest, RegenerateRequest, UploadResponse,
                       job_status_payload)
from ..storage import get_storage
from . import idempotency

bearer = HTTPBearer(auto_error=False, description="API_TOKEN (auth is off when API_TOKEN is empty)")
router = APIRouter(prefix="/api/v1", dependencies=[Depends(bearer)])
ERRORS = {code: {"model": ErrorResponse} for code in (401, 404, 409, 413, 422, 429, 503)}
_pool = None


def set_pool(pool) -> None:
    global _pool
    _pool = pool


@contextmanager
def conn():
    if _pool is None:
        with db.conn_ctx() as c:
            yield c
    else:
        with _pool.connection() as c:
            yield c


def _uuid(job_id: str) -> str:
    try:
        return str(uuid.UUID(job_id))
    except ValueError:
        raise ApiError("JOB_NOT_FOUND", f"No job {job_id!r}.") from None


def _accepted(job_id: str, request: Request) -> JSONResponse:
    url = f"/api/v1/jobs/{job_id}"
    body = JobAccepted(job_id=job_id, status="queued", status_url=url).model_dump()
    with conn() as c:
        row = db.get_job(c, job_id)
    body["status"] = row["status"]
    return JSONResponse(body, status_code=202, headers={"Location": url})


def _check_queue(c) -> None:
    s = get_settings()
    depth = db.queue_depth(c)
    if depth >= s.max_queue:
        raise ApiError("QUEUE_FULL", "Too many queued jobs; retry shortly.", {"queued": depth, "max": s.max_queue})


@router.post("/music/jobs", status_code=202, response_model=JobAccepted, responses=ERRORS, tags=["jobs"],
             summary="Create a music generation job")
def create_job(body: MusicRequest, request: Request,
               idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
               _cid: str | None = Header(None, alias="X-Correlation-Id")):
    key = idempotency.validate_key(idempotency_key)
    data = body.model_dump(mode="json")
    h = idempotency.request_hash(data)
    route = "POST /api/v1/music/jobs"
    with conn() as c:
        if found := idempotency.existing_job(c, key, route, h):
            return _accepted(found, request)
        if body.narration_url and body.narration_url.startswith("upload://"):
            up = body.narration_url.removeprefix("upload://")
            try:
                ok = db.get_upload(c, str(uuid.UUID(up)))
            except ValueError:
                ok = None
            if not ok:
                raise ApiError("VALIDATION_ERROR", f"Unknown upload {body.narration_url!r}.",
                               {"field": "narration_url"})
        _check_queue(c)
        job_id, _ = idempotency.create(c, key, route, h, str(uuid.uuid4()), request=data, kind="generate",
                                       correlation_id=request.state.correlation_id, callback_url=body.callback_url)
    return _accepted(job_id, request)


@router.post("/music/jobs/{job_id}/regenerate", status_code=202, response_model=JobAccepted, responses=ERRORS,
             tags=["jobs"], summary="Regenerate one stem of a finished job (other stems stay byte-identical)")
def regenerate(job_id: str, body: RegenerateRequest, request: Request,
               idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    key = idempotency.validate_key(idempotency_key)
    parent_id = _uuid(job_id)
    if body.stem not in STEM_REGISTRY:
        raise ApiError("STEM_NOT_FOUND", f"Unknown stem {body.stem!r}.", {"stems": list(STEM_REGISTRY)})
    if body.callback_url and not body.callback_url.startswith(("http://", "https://")):
        raise ApiError("VALIDATION_ERROR", "callback_url must be http(s).")
    data = {"parent_job_id": parent_id, **body.model_dump(mode="json")}
    h = idempotency.request_hash(data)
    route = f"POST /api/v1/music/jobs/{parent_id}/regenerate"
    with conn() as c:
        if found := idempotency.existing_job(c, key, route, h):
            return _accepted(found, request)
        parent = db.get_job(c, parent_id)
        if not parent:
            raise ApiError("JOB_NOT_FOUND", f"No job {job_id!r}.")
        if parent["status"] != "succeeded":
            raise ApiError("PARENT_JOB_NOT_READY", f"Parent job is {parent['status']}; wait until it succeeds.",
                           {"status": parent["status"]})
        if body.stem not in (parent["result"] or {}).get("stems", {}):
            raise ApiError("STEM_NOT_FOUND", f"Parent has no stem {body.stem!r}.")
        _check_queue(c)
        new_id, _ = idempotency.create(c, key, route, h, str(uuid.uuid4()), request=data, kind="regenerate",
                                       parent_job_id=parent_id, correlation_id=request.state.correlation_id,
                                       callback_url=body.callback_url)
    return _accepted(new_id, request)


@router.get("/jobs/{job_id}", response_model=JobStatus, responses=ERRORS, tags=["jobs"], summary="Job status")
def get_job(job_id: str):
    jid = _uuid(job_id)
    with conn() as c:
        row = db.get_job(c, jid)
    if not row:
        raise ApiError("JOB_NOT_FOUND", f"No job {job_id!r}.")
    return job_status_payload(row, get_storage().presign)


@router.get("/jobs/{job_id}/manifest", responses=ERRORS, tags=["jobs"],
            summary="music_manifest.json of a succeeded job (same-origin copy of the presigned file)")
def get_manifest(job_id: str):
    jid = _uuid(job_id)
    with conn() as c:
        row = db.get_job(c, jid)
    if not row:
        raise ApiError("JOB_NOT_FOUND", f"No job {job_id!r}.")
    if row["status"] != "succeeded" or not row.get("result"):
        raise ApiError("PARENT_JOB_NOT_READY", f"Job is {row['status']}; the manifest exists once it succeeds.",
                       {"status": row["status"]})
    return JSONResponse(json.loads(get_storage().get_bytes(row["result"]["manifest"])))


@router.post("/uploads", status_code=201, response_model=UploadResponse, responses=ERRORS, tags=["uploads"],
             summary="Upload narration audio; use the returned upload:// URL as narration_url")
def upload(file: UploadFile = File(...)):
    s = get_settings()
    limit = s.max_narration_mb * 1024 * 1024
    upload_id = str(uuid.uuid4())
    key = f"uploads/{upload_id}"
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise ApiError("PAYLOAD_TOO_LARGE", f"Upload exceeds {s.max_narration_mb} MB.")
    if not data:
        raise ApiError("VALIDATION_ERROR", "Empty upload.")
    get_storage().put_bytes(key, data, file.content_type or "application/octet-stream")
    with conn() as c:
        db.insert_upload(c, upload_id, key, file.filename, len(data))
    return JSONResponse(UploadResponse(url=f"upload://{upload_id}", size_bytes=len(data)).model_dump(),
                        status_code=201)

