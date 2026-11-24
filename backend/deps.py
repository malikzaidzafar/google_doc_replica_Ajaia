"""Request dependencies: one DB transaction per request, and the signed-in (simulated) user."""
from typing import Annotated

from fastapi import Depends, Header, Path
from pydantic import BeforeValidator
from sqlalchemy.engine import Connection

from db import engine
from services import access


def _canonical_id(raw):
    """Path ids must be plain ASCII digits: "1.0", " 1", "+1" would otherwise alias real documents."""
    if isinstance(raw, str) and not (raw.isascii() and raw.isdigit()):
        raise ValueError("not an id")
    return raw


# Ids beyond Postgres INTEGER would crash the query ("integer out of range"); reject them as a 404 instead.
IdParam = Annotated[int, Path(ge=1, le=access.MAX_ID), BeforeValidator(_canonical_id)]


def get_conn():
    """Committed on success, rolled back on any exception (including HTTPException)."""
    with engine.begin() as conn:
        yield conn


# scope="function": commit/rollback runs when the route returns, BEFORE the response is sent,
# so a failed commit can never be reported to the client as a successful save.
Conn = Annotated[Connection, Depends(get_conn, scope="function")]


def current_user(conn: Conn, x_user_id: Annotated[str | None, Header()] = None) -> dict:
    return access.user_from_header(conn, x_user_id)


CurrentUser = Annotated[dict, Depends(current_user)]
