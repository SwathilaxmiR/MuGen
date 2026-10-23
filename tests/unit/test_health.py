from fastapi.testclient import TestClient

from musicengine.api.main import app


def test_health_needs_no_keys():
    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    assert c.get("/api/v1/health").status_code == 200


def test_ready_reports_each_check():
    r = TestClient(app).get("/ready")
    assert r.status_code in (200, 503)
    assert {"database", "s3_bucket", "ffmpeg"} <= set(r.json()["checks"])
