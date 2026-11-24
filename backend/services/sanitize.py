"""HTML allowlist. Every stored document body passes through here: it is rendered in other users' browsers."""
import re

import nh3
from fastapi import HTTPException

# Exactly what the editor can represent. Everything else (script, style, img, iframe, on* handlers,
# javascript: links) is stripped.
ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s", "a", "code", "pre", "blockquote", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li",
}
# "*": set() clears nh3's default generic attributes ("title", "lang" on every tag), beyond our allowlist.
ALLOWED_ATTRIBUTES = {"*": set(), "a": {"href"}, "ol": {"start"}}

# The HTML parser behind nh3 is quadratic in nesting depth: 80 KB of "<ul><li>" took ~17 s, so one
# 1 MB save could block a worker for many minutes. Real documents nest a few dozen levels at most.
MAX_DEPTH = 100
TOO_DEEP = ("This content has too many levels of nesting (for example, lists inside lists inside lists). "
            "Please simplify it and try again.")
_TAG = re.compile(r"<(/?)([A-Za-z][^\s/<>]*)[^<>]*>")  # [^<>] keeps the scan linear on unclosed "<"
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def too_deep(raw_html: str) -> bool:
    """Conservative depth estimate: a close tag only counts if it matches the innermost open tag, so stray
    or mismatched closers (which the HTML parser ignores) can't hide nesting.
    ponytail: over-counts sloppy-but-valid HTML (e.g. unclosed <p>/<li>); fine for editor and importer output,
    which is always well-formed. Upgrade path: a real tokenizer with HTML's implied-end-tag rules."""
    stack: list[str] = []
    for match in _TAG.finditer(raw_html):
        name = match.group(2).lower()
        if match.group(1):
            if stack and stack[-1] == name:
                stack.pop()
        elif name not in _VOID:
            stack.append(name)
            if len(stack) > MAX_DEPTH:
                return True
    return False


def sanitize(raw_html: str) -> str:
    if too_deep(raw_html):
        raise HTTPException(400, TOO_DEEP)
    return nh3.clean(raw_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
