"""Worker: WORKER_CONCURRENCY processes claim jobs (SKIP LOCKED) and run each in a child process that
can be killed on JOB_TIMEOUT_S. The parent heart-beats; a dead worker's jobs are re-queued as stale."""
import multiprocessing as mp
import os
import shutil
import signal
import socket
import tempfile
import time
import traceback

import structlog

from .. import db
from ..config import get_settings
from ..errors import JobError
from ..logging import configure, get_logger
from ..schemas import MusicRequest, job_status_payload
from ..storage import Storage
from . import callbacks
from .pipeline import run_generate, run_regenerate

log = get_logger("worker")
CONTENT_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".json": "application/json", ".npz": "application/octet-stream"}
TRANSIENT = {"JOB_TIMEOUT", "STORAGE_ERROR", "INTERNAL_ERROR"}


def _ctype(name: str) -> str:
    return CONTENT_TYPES.get(os.path.splitext(name)[1], "application/octet-stream")


def _orphaned(parent_pid: int) -> bool:
    """True when the process that started us is gone (we were re-parented). Outside Docker a SIGKILLed
    supervisor does not take its children with it, so every child checks this itself."""
    return os.getppid() != parent_pid


def execute_job(job_id: str, parent_pid: int | None = None) -> None:
    """Child process: run one job end to end and write its terminal state (or leave it for the parent)."""
    s = get_settings()
    parent_pid = parent_pid or os.getppid()
    configure(s.log_level)
    with db.conn_ctx() as conn:
        job = db.get_job(conn, job_id)
        structlog.contextvars.bind_contextvars(job_id=job_id, correlation_id=job["correlation_id"])
        storage = Storage(s)
        work = tempfile.mkdtemp(prefix=f"job_{job_id[:8]}_")
        last = [0.0]

        def progress(p: int, msg: str):
            if _orphaned(parent_pid):  # our worker died: stop, the stale-heartbeat sweep re-queues the job
                log.error("job_orphaned_exit", progress=p)
                os._exit(3)
            now = time.monotonic()
            if now - last[0] > 0.5 or p >= 95:
                db.set_progress(conn, job_id, min(p, 95))
                last[0] = now
                log.info("progress", progress=p, stage=msg)

        try:
            log.info("job_started", kind=job["kind"], attempt=job["attempts"])
            prefix = f"jobs/{job_id}/"
            if job["kind"] == "regenerate":
                out, reused = _regenerate(job, work, storage, progress, s)
            else:
                req = MusicRequest.model_validate(job["request"])
                out, reused = run_generate(job_id, req, work, s, progress), []
            t0 = time.perf_counter()
            try:
                keys = {}
                for name, path in out["files"].items():
                    storage.put_file(prefix + name, path, _ctype(name))
                    keys[name] = prefix + name
                for name in reused:  # byte-identical copies of the parent's untouched stems
                    src = f"jobs/{job['parent_job_id']}/stems/{name}.wav"
                    storage.copy(src, prefix + f"stems/{name}.wav")
                    keys[f"stems/{name}.wav"] = prefix + f"stems/{name}.wav"
                m = out["manifest"]
                m["timings_s"]["upload"] = round(time.perf_counter() - t0, 4)
                m["timings_s"]["total"] = round(m["timings_s"]["total"] + m["timings_s"]["upload"], 4)
                storage.put_bytes(prefix + "music_manifest.json", _json(m), "application/json")
            except Exception as e:  # noqa: BLE001
                raise JobError("STORAGE_ERROR", f"Upload failed: {type(e).__name__}: {e}") from e
            result = {"mix_wav": keys["mix.wav"], "mix_mp3": keys.get("mix.mp3"),
                      "stems": {k.split("/")[1][:-4]: v for k, v in keys.items() if k.startswith("stems/")},
                      "mix_ducked": keys.get("mix_ducked.wav"), "manifest": prefix + "music_manifest.json"}
            db.finish(conn, job_id, status="succeeded", result=result, warnings=out["warnings"])
            log.info("job_succeeded", total_s=m["timings_s"]["total"], warnings=[w["code"] for w in out["warnings"]])
        except JobError as e:
            _fail(conn, job, e.body(), s)
        except Exception as e:  # noqa: BLE001 - anything unexpected is INTERNAL_ERROR
            log.error("job_crashed", error=str(e), tb=traceback.format_exc()[-2000:])
            _fail(conn, job, JobError("INTERNAL_ERROR", f"{type(e).__name__}: {e}").body(), s)
        finally:
            shutil.rmtree(work, ignore_errors=True)


def _json(m: dict) -> bytes:
    import json

    return json.dumps(m, indent=2).encode()


def _regenerate(job, work, storage: Storage, progress, s):
    import json

    parent_id = str(job["parent_job_id"])
    pdir = os.path.join(work, "parent")
    os.makedirs(os.path.join(pdir, "stems"), exist_ok=True)
    pm = json.loads(storage.get_bytes(f"jobs/{parent_id}/music_manifest.json"))
    for name in ["plan.json", "master.npz"] + [f"stems/{e['name']}.wav" for e in pm["stems"]]:
        storage.get_file(f"jobs/{parent_id}/{name}", os.path.join(pdir, name))
    req = job["request"]
    out = run_regenerate(str(job["id"]), pm, pdir, req["stem"], req.get("seed"), os.path.join(work, "out"), s, progress)
    out["files"]["master.npz"] = os.path.join(pdir, "master.npz")  # same limiter state as the parent
    return out, out["reused_stems"]


def _fail(conn, job, error: dict, s) -> None:
    job_id = str(job["id"])
    if error["code"] in TRANSIENT and job["attempts"] < s.max_attempts:
        log.warning("job_requeued", error=error["code"], attempt=job["attempts"])
        db.requeue(conn, job_id, error)
        return
    db.finish(conn, job_id, status="failed", error=error, warnings=job.get("warnings") or [])
    log.error("job_failed", code=error["code"], message=error["message"][:300])


def notify(job_id: str, storage: Storage) -> None:
    s = get_settings()
    with db.conn_ctx() as conn:
        row = db.get_job(conn, job_id)
    if row and row["callback_url"] and row["status"] in db.TERMINAL:
        payload = job_status_payload(row, storage.presign)
        payload["correlation_id"] = row["correlation_id"]
        callbacks.send(row["callback_url"], payload, s)


def run_with_timeout(job: dict, worker_id: str, storage: Storage) -> None:
    s = get_settings()
    job_id = str(job["id"])
    ctx = mp.get_context("spawn")
    p = ctx.Process(target=execute_job, args=(job_id, os.getpid()), name=f"job-{job_id[:8]}")
    p.start()
    deadline = time.monotonic() + s.job_timeout_s
    with db.conn_ctx() as conn:
        while p.is_alive():
            p.join(timeout=2.0)
            db.heartbeat(conn, job_id, worker_id)
            if time.monotonic() > deadline and p.is_alive():
                p.kill()
                p.join()
                log.error("job_timeout", job_id=job_id, timeout_s=s.job_timeout_s)
                row = db.get_job(conn, job_id)
                _fail(conn, row, JobError("JOB_TIMEOUT", f"Job exceeded JOB_TIMEOUT_S={s.job_timeout_s}s.").body(), s)
        row = db.get_job(conn, job_id)
        if row["status"] == "running":  # child died without writing a state (OOM, segfault)
            _fail(conn, row, JobError("INTERNAL_ERROR", f"Job process exited with code {p.exitcode}.").body(), s)
    notify(job_id, storage)


def worker_process(index: int, parent_pid: int | None = None) -> None:
    s = get_settings()
    parent_pid = parent_pid or os.getppid()
    configure(s.log_level)
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{index}"
    structlog.contextvars.bind_contextvars(worker_id=worker_id)
    storage = Storage(s)
    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    log.info("worker_started", concurrency_index=index)
    last_sweep = 0.0
    while not stop["flag"]:
        if _orphaned(parent_pid):
            log.error("worker_orphaned_exit")
            return
        try:
            with db.conn_ctx() as conn:
                if time.monotonic() - last_sweep > 10:
                    requeued, failed = db.requeue_stale(conn, s.heartbeat_stale_s, s.max_attempts)
                    if requeued or failed:
                        log.warning("stale_jobs", requeued=[str(x) for x in requeued],
                                    failed=[str(r["id"]) for r in failed])
                    for r in failed:
                        notify(str(r["id"]), storage)
                    last_sweep = time.monotonic()
                job = db.claim_job(conn, worker_id)
            if job is None:
                time.sleep(s.poll_interval_s)
                continue
            structlog.contextvars.bind_contextvars(job_id=str(job["id"]), correlation_id=job["correlation_id"])
            log.info("job_claimed")
            run_with_timeout(job, worker_id, storage)
            structlog.contextvars.unbind_contextvars("job_id", "correlation_id")
        except Exception as e:  # noqa: BLE001 - keep the worker alive (DB restarts etc.)
            log.error("worker_loop_error", error=str(e))
            time.sleep(2)


def main() -> None:
    s = get_settings()
    configure(s.log_level)
    with db.conn_ctx() as conn:
        db.migrate(conn)
    n = max(1, s.worker_concurrency)
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=worker_process, args=(i, os.getpid()), name=f"worker-{i}") for i in range(n)]
    for p in procs:
        p.start()

    def _term(*_):
        for p in procs:
            p.terminate()

    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    for p in procs:
        p.join()


if __name__ == "__main__":
    main()
