"""Who is calling, and what they may do with a document. The single place access is decided."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.engine import Connection

from db import documents, shares, users

RANK = {"viewer": 1, "editor": 2, "owner": 3}
MAX_ID = 2**31 - 1  # Postgres INTEGER; larger values crash the query instead of simply not matching

NOT_FOUND = "We couldn't find that document. It may have been deleted, or it hasn't been shared with you."
FORBIDDEN = {
    "editor": "You can view this document but not edit it. Ask the owner for edit access.",
    "owner": "Only the document's owner can do that.",
}
SIGNED_OUT = "Please sign in to continue."
STALE_SIGN_IN = "We couldn't find your account. Please sign in again."


def list_users(conn: Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(select(users).order_by(users.c.id)).mappings()]


def user_from_header(conn: Connection, raw_id: str | None) -> dict:
    """Simulated auth: X-User-Id holds a seeded user's id."""
    if not raw_id:
        raise HTTPException(401, SIGNED_OUT)
    # Plain ASCII digits only: int() would also accept "+1", "0_1" and other aliases of a real id.
    if not (raw_id.isascii() and raw_id.isdigit() and int(raw_id) <= MAX_ID):
        raise HTTPException(401, STALE_SIGN_IN)
    user = conn.execute(select(users).where(users.c.id == int(raw_id))).mappings().first()
    if user is None:
        raise HTTPException(401, STALE_SIGN_IN)
    return dict(user)


def role_for(conn: Connection, doc: dict, user_id: int) -> str | None:
    if doc["owner_id"] == user_id:
        return "owner"
    return conn.execute(
        select(shares.c.role).where(shares.c.document_id == doc["id"], shares.c.user_id == user_id)
    ).scalar()


def load_doc(conn: Connection, doc_id: int, user: dict, need: str = "viewer") -> tuple[dict, str]:
    """Return (document, caller's role) or raise.

    No access at all -> 404, so document ids can't be probed. Too little access -> 403.
    Writes (editor/owner) lock the document row until the transaction ends, so a concurrent delete either
    waits for this write or has already happened (then this sees no row -> 404) instead of crashing it mid-way.
    """
    query = select(documents).where(documents.c.id == doc_id)
    doc = conn.execute(query if need == "viewer" else query.with_for_update()).mappings().first()
    role = role_for(conn, dict(doc), user["id"]) if doc else None
    if role is None:
        raise HTTPException(404, NOT_FOUND)
    if RANK[role] < RANK[need]:
        raise HTTPException(403, FORBIDDEN[need])
    return dict(doc), role
