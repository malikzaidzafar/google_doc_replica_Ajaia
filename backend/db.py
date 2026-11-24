"""Schema (SQLAlchemy Core metadata) and the engine.

The schema itself is created by Alembic migrations (alembic/versions); this metadata mirrors them
and feeds `alembic revision --autogenerate`.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)  # Neon drops idle connections; reconnect quietly

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String(255), unique=True, nullable=False),
    Column("name", String(100), nullable=False),
)

documents = Table(
    "documents",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("owner_id", Integer, ForeignKey("users.id"), nullable=False, index=True),
    Column("title", String(200), nullable=False),
    Column("content", Text, nullable=False),  # sanitized HTML from the TipTap editor
    Column("version", Integer, nullable=False),  # bumped on every save; drives conflict detection
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("updated_by", Integer, ForeignKey("users.id"), nullable=False),
)

shares = Table(
    "document_shares",
    metadata,
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True),
    Column("role", String(10), nullable=False),
    CheckConstraint("role IN ('viewer', 'editor')", name="ck_document_shares_role"),
)


def now() -> datetime:
    return datetime.now(timezone.utc)
