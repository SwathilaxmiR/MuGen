"""Integration tests use their own database so the compose worker never claims their jobs."""
import os
from urllib.parse import urlparse, urlunparse

import psycopg
import pytest

from musicengine.config import get_settings


def _test_db_url(url: str) -> str:
    p = urlparse(url)
    return urlunparse(p._replace(path=(p.path or "/music") + "_it"))


@pytest.fixture(scope="session", autouse=True)
def isolated_database():
    from tests_conftest_helpers import services_up

    if not services_up():
        yield
        return
    s = get_settings()
    base = s.database_url
    url = _test_db_url(base)
    name = urlparse(url).path.lstrip("/")
    with psycopg.connect(base, autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            c.execute(f'CREATE DATABASE "{name}"')
    old_env = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    s.database_url = url
    yield
    s.database_url = base
    if old_env is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = old_env
