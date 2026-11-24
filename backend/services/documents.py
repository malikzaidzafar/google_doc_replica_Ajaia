"""Document CRUD, including the version-checked save that prevents lost writes."""
import unicodedata
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection

from db import documents, now, shares, users
from services import presence
from services.access import load_doc
from services.sanitize import sanitize
from services.sharing import share_list

MAX_CONTENT_CHARS = 1_000_000
DEFAULT_TITLE = "Untitled document"


# Bidirectional overrides let "invoice‮gpj.exe" display as "invoiceexe.jpg".
_BIDI_CONTROLS = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮⁦⁧⁨⁩"))


def clean_title(title: str | None) -> str:
    """One line of visible text: control characters (NUL crashes Postgres) and bidi overrides removed,
    whitespace runs collapsed, and invisible-only titles (e.g. zero-width spaces) replaced by the default."""
    kept = (" " if ch.isspace() else ch for ch in (title or "") if ch.isspace() or unicodedata.category(ch) != "Cc")
    text = " ".join("".join(kept).translate(_BIDI_CONTROLS).split())
    return text if any(unicodedata.category(ch) != "Cf" for ch in text) else DEFAULT_TITLE


def iso(dt: datetime) -> str:
    return (dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def doc_out(conn: Connection, doc: dict, role: str, active_ids: list[int] = ()) -> dict:
    ids = {doc["owner_id"], doc["updated_by"], *active_ids}
    names = dict(conn.execute(select(users.c.id, users.c.name).where(users.c.id.in_(ids))).all())
    return {
        "id": doc["id"],
        "title": doc["title"],
        "content": doc["content"],
        "version": doc["version"],
        "updated_at": iso(doc["updated_at"]),
        "updated_by": names.get(doc["updated_by"]),
        "owner": {"id": doc["owner_id"], "name": names.get(doc["owner_id"])},
        "role": role,
        "shares": share_list(conn, doc["id"]),
        "active_users": sorted(names[i] for i in active_ids if i in names),
    }


def list_for_user(conn: Connection, user: dict) -> dict:
    owned = conn.execute(
        select(documents.c.id, documents.c.title, documents.c.updated_at)
        .where(documents.c.owner_id == user["id"])
        .order_by(documents.c.updated_at.desc())
    ).mappings()
    shared = conn.execute(
        select(documents.c.id, documents.c.title, documents.c.updated_at, shares.c.role,
               users.c.name.label("owner_name"))
        .select_from(documents)
        .join(shares, shares.c.document_id == documents.c.id)
        .join(users, users.c.id == documents.c.owner_id)
        .where(shares.c.user_id == user["id"])
        .order_by(documents.c.updated_at.desc())
    ).mappings()
    return {
        "owned": [{**r, "updated_at": iso(r["updated_at"])} for r in owned],
        "shared": [{**r, "updated_at": iso(r["updated_at"])} for r in shared],
    }


def insert_doc(conn: Connection, owner_id: int, title: str | None, content: str) -> int:
    return conn.execute(
        insert(documents).values(
            owner_id=owner_id, title=clean_title(title), content=content,
            version=1, updated_at=now(), updated_by=owner_id,
        ).returning(documents.c.id)
    ).scalar_one()


def create(conn: Connection, user: dict, title: str | None) -> int:
    return insert_doc(conn, user["id"], title, "<p></p>")


def get(conn: Connection, doc_id: int, user: dict) -> dict:
    """Also the polling endpoint, so it records presence."""
    doc, role = load_doc(conn, doc_id, user)
    return doc_out(conn, doc, role, presence.touch(doc_id, user["id"]))


def save(conn: Connection, doc_id: int, user: dict, title: str | None, content: str, base_version: int) -> int:
    load_doc(conn, doc_id, user, need="editor")
    if len(content) > MAX_CONTENT_CHARS:
        raise HTTPException(413, "This document is too large to save (max 1 MB). Try splitting it into smaller documents.")
    # Optimistic concurrency: the version in the WHERE makes check-and-write one atomic statement.
    result = conn.execute(
        update(documents)
        .where(documents.c.id == doc_id, documents.c.version == base_version)
        .values(title=clean_title(title), content=sanitize(content), version=documents.c.version + 1,
                updated_at=now(), updated_by=user["id"])
    )
    if result.rowcount == 0:
        latest = doc_out(conn, *load_doc(conn, doc_id, user))
        raise HTTPException(409, {
            "message": f"{latest['updated_by']} saved a newer version while you were editing.",
            "document": latest,
        })
    return base_version + 1


def remove(conn: Connection, doc_id: int, user: dict) -> None:
    load_doc(conn, doc_id, user, need="owner")
    conn.execute(delete(documents).where(documents.c.id == doc_id))  # shares go via ON DELETE CASCADE
