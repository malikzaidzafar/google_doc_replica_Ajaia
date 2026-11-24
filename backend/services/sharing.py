"""Granting, changing and removing access to a document (owner only)."""
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from db import shares, users
from services.access import load_doc


def share_list(conn: Connection, doc_id: int) -> list[dict]:
    rows = conn.execute(
        select(users.c.id.label("user_id"), users.c.name, users.c.email, shares.c.role)
        .select_from(shares)
        .join(users, users.c.id == shares.c.user_id)
        .where(shares.c.document_id == doc_id)
        .order_by(users.c.name)
    ).mappings()
    return [dict(r) for r in rows]


def share(conn: Connection, doc_id: int, user: dict, email: str, role: str) -> list[dict]:
    """Grant access, or change the role of someone who already has it. `email` arrives trimmed + lowercased."""
    load_doc(conn, doc_id, user, need="owner")
    target = conn.execute(select(users.c.id).where(users.c.email == email)).scalar()
    if target is None:
        raise HTTPException(400, f"There's no account for {email}. Check the address and try again.")
    if target == user["id"]:
        raise HTTPException(400, "You already own this document, so there's no need to share it with yourself.")
    # Upsert: select-then-insert raced on double-clicks (duplicate key -> 500).
    conn.execute(
        pg_insert(shares).values(document_id=doc_id, user_id=target, role=role)
        .on_conflict_do_update(index_elements=[shares.c.document_id, shares.c.user_id], set_={"role": role})
    )
    return share_list(conn, doc_id)


def unshare(conn: Connection, doc_id: int, user: dict, target_id: int) -> list[dict]:
    load_doc(conn, doc_id, user, need="owner")
    conn.execute(delete(shares).where(shares.c.document_id == doc_id, shares.c.user_id == target_id))
    return share_list(conn, doc_id)
