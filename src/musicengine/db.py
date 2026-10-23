"""PostgreSQL access: jobs table doubles as the queue (claimed with FOR UPDATE SKIP LOCKED)."""
from contextlib import contextmanager
from importlib import resources

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import get_settings

_MIGRATION_LOCK = 72_431_001  # arbitrary advisory-lock id so api+worker don't migrate concurrently


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or get_settings().database_url, row_factory=dict_row, autocommit=True)


@contextmanager
def conn_ctx(url: str | None = None):
    c = connect(url)
    try:
        yield c
    finally:
        c.close()


def migrate(conn: psycopg.Connection) -> None:
    sql = resources.files("musicengine").joinpath("migrations.sql").read_text()
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK,))
        conn.execute(sql)


def ping(conn: psycopg.Connection) -> bool:
    return conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1


# ---------------------------------------------------------------- jobs
TERMINAL = ("succeeded", "failed")


def insert_job(conn, *, job_id: str, request: dict, request_hash: str, kind: str = "generate",
               parent_job_id: str | None = None, correlation_id: str | None = None,
               callback_url: str | None = None) -> None:
    conn.execute(
        """INSERT INTO jobs (id, request, request_hash, kind, parent_job_id, correlation_id, callback_url)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (job_id, Jsonb(request), request_hash, kind, parent_job_id, correlation_id, callback_url))


def get_job(conn, job_id: str) -> dict | None:
    return conn.execute("SELECT * FROM jobs WHERE id = %s", (job_id,)).fetchone()


def queue_depth(conn) -> int:
    return conn.execute("SELECT count(*) AS n FROM jobs WHERE status IN ('queued', 'running')").fetchone()["n"]


def claim_job(conn, worker_id: str) -> dict | None:
    """Atomically take the oldest queued job. Concurrent workers never get the same row."""
    with conn.transaction():
        row = conn.execute(
            """SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at
               FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not row:
            return None
        return conn.execute(
            """UPDATE jobs SET status = 'running', attempts = attempts + 1, locked_by = %s,
                      heartbeat_at = now(), started_at = coalesce(started_at, now()), progress = 1
               WHERE id = %s RETURNING *""", (worker_id, row["id"])).fetchone()


def heartbeat(conn, job_id: str, worker_id: str) -> None:
    conn.execute("UPDATE jobs SET heartbeat_at = now() WHERE id = %s AND locked_by = %s AND status = 'running'",
                 (job_id, worker_id))


def set_progress(conn, job_id: str, progress: int) -> None:
    conn.execute("UPDATE jobs SET progress = greatest(progress, %s), heartbeat_at = now() "
                 "WHERE id = %s AND status = 'running'", (int(progress), job_id))


def finish(conn, job_id: str, *, status: str, result: dict | None = None, error: dict | None = None,
           warnings: list | None = None) -> None:
    conn.execute(
        """UPDATE jobs SET status = %s, progress = CASE WHEN %s = 'succeeded' THEN 100 ELSE progress END,
                  finished_at = now(), result = %s, error = %s, warnings = %s, locked_by = NULL
           WHERE id = %s""",
        (status, status, Jsonb(result) if result is not None else None,
         Jsonb(error) if error is not None else None, Jsonb(warnings or []), job_id))


def requeue(conn, job_id: str, error: dict | None = None) -> None:
    conn.execute("UPDATE jobs SET status = 'queued', locked_by = NULL, progress = 0, error = %s WHERE id = %s",
                 (Jsonb(error) if error else None, job_id))


def requeue_stale(conn, stale_s: int, max_attempts: int) -> tuple[list, list]:
    """Running jobs whose worker stopped heart-beating: back to the queue, or failed after max attempts."""
    with conn.transaction():
        requeued = conn.execute(
            """UPDATE jobs SET status = 'queued', locked_by = NULL, progress = 0
               WHERE status = 'running' AND heartbeat_at < now() - make_interval(secs => %s)
                 AND attempts < %s RETURNING id""", (stale_s, max_attempts)).fetchall()
        failed = conn.execute(
            """UPDATE jobs SET status = 'failed', finished_at = now(), locked_by = NULL,
                      error = %s
               WHERE status = 'running' AND heartbeat_at < now() - make_interval(secs => %s)
                 AND attempts >= %s RETURNING id, callback_url""",
            (Jsonb({"code": "INTERNAL_ERROR", "message": "Worker stopped responding; max attempts reached.",
                    "retryable": True, "details": {}}), stale_s, max_attempts)).fetchall()
    return [r["id"] for r in requeued], failed


# ---------------------------------------------------------------- idempotency
def create_job_idempotent(conn, *, key: str | None, route: str, request_hash: str, job_id: str,
                          **job_fields) -> tuple[str, bool]:
    """Insert the job and claim (key, route) in one transaction. Returns (job_id, created).
    A concurrent identical request blocks on the primary key until the first commits, then sees the
    conflict. Same key + same body -> the existing job; same key + different body -> KeyReused."""
    if not key:
        insert_job(conn, job_id=job_id, request_hash=request_hash, **job_fields)
        return job_id, True
    try:
        with conn.transaction():
            insert_job(conn, job_id=job_id, request_hash=request_hash, **job_fields)
            row = conn.execute(
                """INSERT INTO idempotency (key, route, request_hash, job_id) VALUES (%s, %s, %s, %s)
                   ON CONFLICT (key, route) DO NOTHING RETURNING job_id""",
                (key, route, request_hash, job_id)).fetchone()
            if row is None:
                raise _Conflict  # rolls back the job insert
        return job_id, True
    except _Conflict:
        existing = conn.execute("SELECT * FROM idempotency WHERE key = %s AND route = %s", (key, route)).fetchone()
        if existing["request_hash"] != request_hash:
            raise KeyReused(str(existing["job_id"])) from None
        return str(existing["job_id"]), False


class _Conflict(Exception):
    pass


class KeyReused(Exception):
    pass


# ---------------------------------------------------------------- uploads
def insert_upload(conn, upload_id: str, s3_key: str, filename: str | None, size: int) -> None:
    conn.execute("INSERT INTO uploads (id, s3_key, filename, size_bytes) VALUES (%s, %s, %s, %s)",
                 (upload_id, s3_key, filename, size))


def get_upload(conn, upload_id: str) -> dict | None:
    return conn.execute("SELECT * FROM uploads WHERE id = %s", (upload_id,)).fetchone()


__all__ = ["connect", "conn_ctx", "migrate", "ping", "Jsonb"]
