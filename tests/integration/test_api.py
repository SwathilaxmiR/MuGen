"""API contract tests against real postgres + S3 (no worker needed)."""
import io
import threading
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from musicengine import db
from musicengine.api.main import app
from musicengine.api.middleware import limiter
from musicengine.cli import openapi_yaml
from musicengine.config import get_settings

pytestmark = pytest.mark.integration
BODY = {"prompt": "calm cinematic piano that builds", "duration_s": 12}


@pytest.fixture
def client(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "api_token", "")
    monkeypatch.setattr(s, "rate_limit_per_min", 10_000)
    monkeypatch.setattr(s, "max_queue", 10_000)
    limiter.hits.clear()
    with TestClient(app) as c:
        yield c


def err(r, code, status):
    assert r.status_code == status, r.text
    e = r.json()["error"]
    assert e["code"] == code and isinstance(e["retryable"], bool) and "message" in e
    return e


@pytest.mark.parametrize("body", [
    {"duration_s": 10},
    {"prompt": "x", "duration_s": 4.9},
    {"prompt": "x", "duration_s": 300.5},
    {"prompt": "x", "duration_s": 10, "key": "H major"},
    {"prompt": "x", "duration_s": 10, "output": {"sample_rate": 22050}},
    {"prompt": "x", "duration_s": 10, "output": {"target_lufs": -5}},
    {"prompt": "x", "duration_s": 10, "tempo_bpm": 20},
    {"prompt": "x", "duration_s": 10, "sections": [{"start_s": -1, "mood": "calm"}]},
    {"prompt": "x", "duration_s": 10, "narration_url": "file:///etc/passwd"},
    {"prompt": "x", "duration_s": 10, "unknown_field": 1},
])
def test_validation_errors_are_json(client, body):
    e = err(client.post("/api/v1/music/jobs", json=body), "VALIDATION_ERROR", 422)
    assert e["details"]["errors"]


def test_malformed_json(client):
    r = client.post("/api/v1/music/jobs", content=b"{not json", headers={"Content-Type": "application/json"})
    err(r, "VALIDATION_ERROR", 422)


def test_accepts_and_reports_status(client):
    r = client.post("/api/v1/music/jobs", json={**BODY, "key": "F# minor", "tempo_bpm": 96, "loopable": False,
                                                "seed": 3, "output": {"formats": ["wav", "mp3"]}},
                    headers={"X-Correlation-Id": "corr-abc"})
    assert r.status_code == 202 and r.headers["X-Correlation-Id"] == "corr-abc"
    j = r.json()
    assert j["status"] == "queued" and j["status_url"] == f"/api/v1/jobs/{j['job_id']}"
    s = client.get(j["status_url"]).json()
    assert s["status"] == "queued" and s["progress"] == 0 and s["result"] is None
    with db.conn_ctx() as c:
        assert db.get_job(c, j["job_id"])["correlation_id"] == "corr-abc"


def test_not_found_variants(client):
    err(client.get(f"/api/v1/jobs/{uuid.uuid4()}"), "JOB_NOT_FOUND", 404)
    err(client.get("/api/v1/jobs/not-a-uuid"), "JOB_NOT_FOUND", 404)
    err(client.get("/api/v1/nope"), "NOT_FOUND", 404)
    err(client.delete("/api/v1/music/jobs"), "METHOD_NOT_ALLOWED", 405)


def test_auth(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_token", "t0ken")
    err(client.post("/api/v1/music/jobs", json=BODY), "UNAUTHORIZED", 401)
    err(client.post("/api/v1/music/jobs", json=BODY, headers={"Authorization": "Bearer wrong"}), "UNAUTHORIZED", 401)
    assert client.post("/api/v1/music/jobs", json=BODY, headers={"Authorization": "Bearer t0ken"}).status_code == 202
    assert client.get("/health").status_code == 200  # ops endpoints stay open


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_min", 3)
    codes = [client.post("/api/v1/music/jobs", json=BODY).status_code for _ in range(4)]
    assert codes == [202, 202, 202, 429]
    r = client.post("/api/v1/music/jobs", json=BODY)
    e = err(r, "RATE_LIMITED", 429)
    assert e["retryable"] and int(r.headers["Retry-After"]) >= 1


def test_queue_full(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_queue", 0)
    e = err(client.post("/api/v1/music/jobs", json=BODY), "QUEUE_FULL", 503)
    assert e["retryable"]


def test_idempotency_same_body_same_job(client):
    key = f"k-{uuid.uuid4()}"
    a = client.post("/api/v1/music/jobs", json=BODY, headers={"Idempotency-Key": key}).json()
    b = client.post("/api/v1/music/jobs", json=BODY, headers={"Idempotency-Key": key}).json()
    assert a["job_id"] == b["job_id"]
    e = err(client.post("/api/v1/music/jobs", json={**BODY, "duration_s": 13}, headers={"Idempotency-Key": key}),
            "IDEMPOTENCY_KEY_REUSED", 409)
    assert e["details"]["job_id"] == a["job_id"]


def test_idempotency_parallel_identical_requests_make_one_job(client):
    key = f"par-{uuid.uuid4()}"
    body = {**BODY, "prompt": f"parallel {key}"}
    ids, errors = [], []

    def go():
        try:
            ids.append(client.post("/api/v1/music/jobs", json=body, headers={"Idempotency-Key": key}).json()["job_id"])
        except Exception as e:  # pragma: no cover - surfaced below
            errors.append(e)

    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and len(set(ids)) == 1 and len(ids) == 8
    with db.conn_ctx() as c:
        n = c.execute("SELECT count(*) AS n FROM jobs WHERE request->>'prompt' = %s", (body["prompt"],)).fetchone()["n"]
    assert n == 1


def test_regenerate_errors(client):
    err(client.post(f"/api/v1/music/jobs/{uuid.uuid4()}/regenerate", json={"stem": "drums"}), "JOB_NOT_FOUND", 404)
    job = client.post("/api/v1/music/jobs", json=BODY).json()["job_id"]
    err(client.post(f"/api/v1/music/jobs/{job}/regenerate", json={"stem": "drums"}), "PARENT_JOB_NOT_READY", 409)
    err(client.post(f"/api/v1/music/jobs/{job}/regenerate", json={"stem": "vocals"}), "STEM_NOT_FOUND", 422)


def test_upload_roundtrip(client):
    r = client.post("/api/v1/uploads", files={"file": ("n.wav", io.BytesIO(b"RIFF" + b"\0" * 100), "audio/wav")})
    assert r.status_code == 201
    url = r.json()["url"]
    assert url.startswith("upload://")
    assert client.post("/api/v1/music/jobs", json={**BODY, "narration_url": url}).status_code == 202
    err(client.post("/api/v1/music/jobs", json={**BODY, "narration_url": f"upload://{uuid.uuid4()}"}),
        "VALIDATION_ERROR", 422)


def test_upload_too_large(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_narration_mb", 0)
    r = client.post("/api/v1/uploads", files={"file": ("n.wav", io.BytesIO(b"abc"), "audio/wav")})
    err(r, "PAYLOAD_TOO_LARGE", 413)


def test_ready_ok(client):
    r = client.get("/ready")
    assert r.status_code == 200, r.json()


def test_openapi_file_matches_app():
    committed = (Path(__file__).resolve().parents[2] / "openapi.yaml").read_text()
    assert committed == openapi_yaml(), "run `make openapi` and commit openapi.yaml"


def test_manifest_not_ready_and_unknown(client):
    job = client.post("/api/v1/music/jobs", json=BODY).json()["job_id"]
    err(client.get(f"/api/v1/jobs/{job}/manifest"), "PARENT_JOB_NOT_READY", 409)
    err(client.get(f"/api/v1/jobs/{uuid.uuid4()}/manifest"), "JOB_NOT_FOUND", 404)
