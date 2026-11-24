"""Settings. Loads backend/.env for local runs; real environment variables always win."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=False)


def _normalize(url: str) -> str:
    # Neon hands out driverless postgres:// URLs; we ship psycopg 3, so name the driver explicitly.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _normalize(os.environ.get("DATABASE_URL", ""))
if not DATABASE_URL.startswith("postgresql+psycopg://"):
    raise RuntimeError("DATABASE_URL must be a Postgres URL. Set it in backend/.env or the environment.")
