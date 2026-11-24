"""Turn an uploaded .txt / .md / .docx file into a new document owned by the uploader."""
import html
import io
import re
import zipfile
from pathlib import Path
from typing import BinaryIO

import mammoth
import markdown
from fastapi import HTTPException
from sqlalchemy.engine import Connection

from services.documents import MAX_CONTENT_CHARS, insert_doc
from services.sanitize import MAX_DEPTH, sanitize, too_deep

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_UNZIPPED_BYTES = 20 * 1024 * 1024  # zip-bomb guard for .docx
# ponytail: mammoth is pure Python (~0.06 ms per XML tag), so a 5 KB .docx of tiny paragraphs can take
# 25 s+ while holding a worker and a DB connection. Counting tags caps that at a few seconds.
# Upgrade path: convert in a worker process with a hard timeout.
MAX_DOCX_TAGS = 60_000
# nh3 slows down sharply with nesting depth and markdown hits RecursionError on deep lists; the tag-depth
# check itself lives in services/sanitize.py (shared with every save).
MAX_NESTING = MAX_DEPTH
# python-markdown is quadratic in the number of blocks (50k paragraphs ~10 s, 2 MB of blank lines ~minutes).
# Collapsing blank-line runs and capping lines keeps the worst case around 2 s.
MAX_MD_LINES = 20_000
_BLANK_RUNS = re.compile(r"\n(?:[ \t]*\n)+")
UPLOAD_TYPES = {".txt", ".md", ".docx"}
NOT_A_DOCX = "That doesn't look like a Word (.docx) file. Try saving it again from Word or Google Docs."
TOO_NESTED = "That file is nested too deeply (lists or quotes inside each other) to import."
TOO_BIG_CONVERTED = "That file is too large to import as one document (max 1 MB of text). Try splitting it into smaller files."

# Control characters (incl. NUL, which Postgres rejects) and bidi overrides that can disguise a title.
_UNSAFE_TITLE_CHARS = re.compile("[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]")


def import_file(conn: Connection, user: dict, filename: str | None, stream: BinaryIO) -> int:
    name = Path(filename or "")
    ext = name.suffix.lower()
    if ext not in UPLOAD_TYPES:
        raise HTTPException(400, "We can only import .txt, .md and .docx files.")
    data = stream.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That file is larger than 2 MB. Try a smaller file.")
    if not data.strip():
        raise HTTPException(400, "That file is empty, so there's nothing to import.")
    content = to_html(ext, data)
    if len(content) > MAX_CONTENT_CHARS:  # otherwise the doc would import but could never be saved again
        raise HTTPException(413, TOO_BIG_CONVERTED)
    title = _UNSAFE_TITLE_CHARS.sub("", name.stem).strip()[:200] or "Imported document"
    return insert_doc(conn, user["id"], title, content)


def to_html(ext: str, data: bytes) -> str:
    if ext == ".docx":
        return _sanitize_shallow(_docx_to_html(data))
    try:
        text = data.decode("utf-8-sig").replace("\x00", "")
    except UnicodeDecodeError:
        raise HTTPException(400, "We couldn't read that text file. Save it as UTF-8 and try again.")
    if ext == ".md":
        text = _BLANK_RUNS.sub("\n\n", text)  # also collapses blank lines inside code blocks; acceptable
        if text.count("\n") > MAX_MD_LINES:
            raise HTTPException(400, "That Markdown file is too long to import at once (max 20,000 lines). Try splitting it.")
        if _line_nesting(text) > MAX_NESTING or too_deep(text):
            raise HTTPException(400, TOO_NESTED)
        try:
            return _sanitize_shallow(markdown.markdown(text, extensions=["sane_lists"]))
        except RecursionError:
            raise HTTPException(400, TOO_NESTED)
    return "".join(f"<p>{html.escape(line)}</p>" for line in text.splitlines()) or "<p></p>"


def _sanitize_shallow(raw_html: str) -> str:
    """sanitize() also rejects over-deep HTML; checking first gives the import-specific message."""
    if too_deep(raw_html):
        raise HTTPException(400, TOO_NESTED)
    return sanitize(raw_html)


def _line_nesting(text: str) -> int:
    """Deepest markdown nesting from line prefixes: '>' quote markers plus indentation (2 columns per level)."""
    deepest = 0
    for line in text.splitlines():
        prefix = re.match(r"[ \t>]*", line).group().expandtabs(4)
        deepest = max(deepest, prefix.count(">") + len(prefix.replace(">", "")) // 2)
    return deepest


def _docx_to_html(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            parts = archive.infolist()
            if sum(info.file_size for info in parts) > MAX_UNZIPPED_BYTES:
                raise HTTPException(400, "That Word file expands to more than 20 MB, which is too large to import.")
            # zipfile stops at each entry's declared size, so a header that lies about it can't inflate further.
            tags = sum(archive.read(p).count(b"<") for p in parts if p.filename.endswith((".xml", ".rels")))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, OSError, ValueError, NotImplementedError):
        raise HTTPException(400, NOT_A_DOCX)
    if tags > MAX_DOCX_TAGS:
        raise HTTPException(400, "That Word file has too much content to import at once. Try splitting it into smaller files.")
    try:
        # mammoth drops underline by default; map it so it survives the import.
        return mammoth.convert_to_html(io.BytesIO(data), style_map="u => u").value
    except Exception:  # mammoth raises assorted zip/xml/key errors for malformed documents
        raise HTTPException(400, NOT_A_DOCX)
