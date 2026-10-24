"""Queue + worker against real postgres and S3 (compose services or scripts/dev_services.sh)."""
import http.server
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid

import pytest

from musicengine import db
from musicengine.storage import Storage
from musicengine.worker import callbacks

pytestmark = pytest.mark.integration
REQ = {"prompt": "upbeat corporate background", "duration_s": 6, "seed": 1,
       "output": {"sample_rate": 48000, "target_lufs": -16, "formats": ["wav"]}}


def new_job(conn, request=None, **kw):
    jid = str(uuid.uuid4())
    db.insert_job(conn, job_id=jid, request=request or REQ, request_hash=uuid.uuid4().hex,
                  correlation_id=kw.pop("correlation_id", f"corr-{jid[:6]}"), **kw)
    return jid


def start_worker(env_extra=None, log_path=None):
    env = {**os.environ, "WORKER_CONCURRENCY": "1", "POLL_INTERVAL_S": "0.2", **(env_extra or {})}
    out = open(log_path, "w") if log_path else subprocess.DEVNULL
    return subprocess.Popen([sys.executable, "-m", "musicengine.worker.loop"], env=env, stdout=out,
                            stderr=subprocess.STDOUT, start_new_session=True)


def stop(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(10)


def wait_status(conn, jid, statuses, timeout=180, seen=None):
    t0 = time.time()
    while time.time() - t0 < timeout:
        row = db.get_job(conn, jid)
        if seen is not None:
            seen.append(row["progress"])
        if row["status"] in statuses:
            return row
        time.sleep(0.25)
    raise AssertionError(f"job {jid} stuck in {row['status']} ({row['progress']}%)")


@pytest.fixture
def conn():
    with db.conn_ctx() as c:
        db.migrate(c)
        c.execute("UPDATE jobs SET status='failed' WHERE status IN ('queued','running')")  # isolate tests
        yield c


def test_lifecycle_progress_and_correlation_id(conn, tmp_path):
    log = tmp_path / "worker.log"
    jid = new_job(conn, correlation_id="corr-lifecycle-1")
    w = start_worker(log_path=log)
    try:
        progress = []
        row = wait_status(conn, jid, {"succeeded", "failed"}, seen=progress)
    finally:
        stop(w)
    assert row["status"] == "succeeded", row["error"]
    assert progress == sorted(progress) and row["progress"] == 100
    assert set(row["result"]["stems"]) == {"drums", "bass", "harmony", "melody"}
    keys = Storage().list_keys(f"jobs/{jid}/")
    assert f"jobs/{jid}/music_manifest.json" in keys and f"jobs/{jid}/stems/melody.wav" in keys
    lines = [json.loads(line) for line in log.read_text().splitlines() if line.startswith("{")]
    mine = [entry for entry in lines if entry.get("job_id") == jid]
    assert mine and all(entry["correlation_id"] == "corr-lifecycle-1" for entry in mine)
    assert {"timestamp", "level", "event"} <= set(mine[0])


def test_two_jobs_claimed_independently(conn):
    jobs = [new_job(conn) for _ in range(3)]
    claims = []

    def claim():
        with db.conn_ctx() as c:
            claims.append(db.claim_job(c, f"t-{threading.get_ident()}"))

    ts = [threading.Thread(target=claim) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    ids = [str(c["id"]) for c in claims if c]
    assert sorted(ids) == sorted(jobs) and len(set(ids)) == 3


def test_killed_worker_job_is_requeued_and_completes(conn):
    jid = new_job(conn, request={**REQ, "duration_s": 120})
    env = {"HEARTBEAT_STALE_S": "3", "MAX_ATTEMPTS": "3"}
    w = start_worker(env)
    try:
        t0 = time.time()
        while db.get_job(conn, jid)["status"] != "running" and time.time() - t0 < 60:
            time.sleep(0.2)
        time.sleep(1.0)
    finally:
        stop(w)  # SIGKILL worker + its job child mid-job
    assert db.get_job(conn, jid)["status"] == "running"
    w2 = start_worker(env)
    try:
        row = wait_status(conn, jid, {"succeeded", "failed"}, timeout=300)
    finally:
        stop(w2)
    assert row["status"] == "succeeded" and row["attempts"] == 2


def test_job_timeout_enforced(conn):
    jid = new_job(conn, request={**REQ, "duration_s": 200})
    w = start_worker({"JOB_TIMEOUT_S": "2", "MAX_ATTEMPTS": "1"})
    try:
        row = wait_status(conn, jid, {"succeeded", "failed"}, timeout=60)
    finally:
        stop(w)
    assert row["status"] == "failed" and row["error"]["code"] == "JOB_TIMEOUT" and row["error"]["retryable"]


class _Receiver(http.server.BaseHTTPRequestHandler):
    got: list = []
    fail_first = 0

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        _Receiver.got.append((body, self.headers.get("X-IncuBrix-Signature")))
        if _Receiver.fail_first > 0:
            _Receiver.fail_first -= 1
            self.send_response(500)
        else:
            self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


def test_signed_callback_with_retry(conn):
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Receiver)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _Receiver.got, _Receiver.fail_first = [], 1
    url = f"http://127.0.0.1:{srv.server_port}/hook"
    jid = new_job(conn, callback_url=url)
    w = start_worker({"ALLOW_PRIVATE_URLS": "true", "CALLBACK_SECRET": "s3cret"})
    try:
        wait_status(conn, jid, {"succeeded", "failed"})
        t0 = time.time()
        while len(_Receiver.got) < 2 and time.time() - t0 < 20:
            time.sleep(0.2)
    finally:
        stop(w)
        srv.shutdown()
    assert len(_Receiver.got) == 2  # first attempt got a 500, retry succeeded
    body, sig = _Receiver.got[-1]
    assert callbacks.verify(body, sig, "s3cret")
    assert not callbacks.verify(body, sig, "wrong")
    payload = json.loads(body)
    assert payload["job_id"] == jid and payload["status"] == "succeeded"


def test_callback_to_private_ip_blocked_by_default():
    assert callbacks.send("http://127.0.0.1:9/x", {"job_id": "x"}) is False


def test_children_exit_when_supervisor_is_killed(conn):
    """SIGKILL only the supervisor (not its process group): worker and job processes must exit on their own."""
    jid = new_job(conn, request={**REQ, "duration_s": 120})
    w = subprocess.Popen([sys.executable, "-m", "musicengine.worker.loop"],
                         env={**os.environ, "WORKER_CONCURRENCY": "2", "POLL_INTERVAL_S": "0.2"},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        t0 = time.time()
        while db.get_job(conn, jid)["status"] != "running" and time.time() - t0 < 60:
            time.sleep(0.2)
        children = subprocess.run(["pgrep", "-g", str(w.pid)], capture_output=True, text=True).stdout.split()
        assert len(children) >= 3  # supervisor + workers (+ job)
        os.kill(w.pid, signal.SIGKILL)
        w.wait(5)
        t0 = time.time()
        alive = children
        while time.time() - t0 < 15:
            alive = subprocess.run(["pgrep", "-g", str(w.pid)], capture_output=True, text=True).stdout.split()
            if not alive:
                break
            time.sleep(0.3)
        assert not alive, f"orphaned worker processes still running: {alive}"
    finally:
        stop(w)
