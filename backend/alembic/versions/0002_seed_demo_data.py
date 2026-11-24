"""Seed demo users (Alice, Bob, Carol) and a welcome document shared with Bob (editor) and Carol (viewer).

Revision ID: 0002
Revises: 0001
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SEED_USERS = [("alice@example.com", "Alice"), ("bob@example.com", "Bob"), ("carol@example.com", "Carol")]

WELCOME_HTML = (
    "<h1>Welcome to DocShare</h1>"
    "<p>This document is owned by <strong>Alice</strong>, shared with <em>Bob</em> as an editor "
    "and with <u>Carol</u> as a viewer.</p>"
    "<h2>Try this</h2>"
    "<ol><li>Open this doc as Alice in one browser and as Bob in another.</li>"
    "<li>Edit in one window and watch the other pick up the change.</li>"
    "<li>Sign in as Carol: the editor is read-only.</li></ol>"
    "<ul><li>Formatting is stored as HTML, so it survives reloads.</li></ul>"
)

# Lightweight table stubs: migrations must not import app code, which can change later.
users = sa.table("users", sa.column("id", sa.Integer), sa.column("email", sa.String), sa.column("name", sa.String))
documents = sa.table(
    "documents",
    sa.column("id", sa.Integer), sa.column("owner_id", sa.Integer), sa.column("title", sa.String),
    sa.column("content", sa.Text), sa.column("version", sa.Integer),
    sa.column("updated_at", sa.DateTime(timezone=True)), sa.column("updated_by", sa.Integer),
)
shares = sa.table(
    "document_shares", sa.column("document_id", sa.Integer), sa.column("user_id", sa.Integer), sa.column("role", sa.String)
)


def upgrade() -> None:
    conn = op.get_bind()
    ids = {
        name: conn.execute(sa.insert(users).values(email=email, name=name).returning(users.c.id)).scalar_one()
        for email, name in SEED_USERS
    }
    doc_id = conn.execute(
        sa.insert(documents).values(
            owner_id=ids["Alice"], title="Welcome to DocShare", content=WELCOME_HTML, version=1,
            updated_at=datetime.now(timezone.utc), updated_by=ids["Alice"],
        ).returning(documents.c.id)
    ).scalar_one()
    op.bulk_insert(shares, [
        {"document_id": doc_id, "user_id": ids["Bob"], "role": "editor"},
        {"document_id": doc_id, "user_id": ids["Carol"], "role": "viewer"},
    ])


def downgrade() -> None:
    # Every account is a seeded one, so removing them removes their documents too (shares cascade).
    conn = op.get_bind()
    emails = [email for email, _ in SEED_USERS]
    seeded = sa.select(users.c.id).where(users.c.email.in_(emails))
    conn.execute(sa.delete(documents).where(sa.or_(documents.c.owner_id.in_(seeded), documents.c.updated_by.in_(seeded))))
    conn.execute(sa.delete(users).where(users.c.email.in_(emails)))
