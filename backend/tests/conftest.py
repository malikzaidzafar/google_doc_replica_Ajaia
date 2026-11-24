"""Test setup: a disposable LOCAL Postgres only, rebuilt from the Alembic migrations each session."""
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_URL:
    pytest.exit("Set TEST_DATABASE_URL to a local Postgres (see CLAUDE.md).", returncode=2)
if urlparse(TEST_URL).hostname not in {"localhost", "127.0.0.1"}:
    pytest.exit("Refusing to run tests against a non-local database.", returncode=2)
os.environ["DATABASE_URL"] = TEST_URL  # must be set before the app's config module is imported

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def client():
    from db import engine
    from main import app

    with engine.begin() as conn:  # start from nothing so reruns are clean
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def who(client):
    """Auth headers per seeded user: who['alice'] -> {'X-User-Id': '1'}."""
    return {u["name"].lower(): {"X-User-Id": str(u["id"])} for u in client.get("/api/users").json()}
