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


__all__ = ["connect", "conn_ctx", "migrate", "ping", "Jsonb"]
