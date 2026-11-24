"""Request bodies. Limits here produce 422s that services/errors.py turns into human sentences."""
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

TITLE_MAX = 200
VERSION_MAX = 2**31 - 1  # Postgres INTEGER; larger values would crash the query instead of conflicting


class DocCreate(BaseModel):
    title: str | None = Field(None, max_length=TITLE_MAX)  # blank -> "Untitled document"


class DocUpdate(BaseModel):
    title: str | None = Field(None, max_length=TITLE_MAX)
    content: str  # size limit enforced in the service (413, not 422)
    base_version: int = Field(ge=1, le=VERSION_MAX)  # the version the client's edits were made on top of


class ShareIn(BaseModel):
    # No whitespace or control characters inside: a NUL byte would crash the Postgres query.
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=255,
                                            pattern=r"^[^\s\x00-\x1f\x7f]+$")]
    role: Literal["viewer", "editor"]
