"""Turn framework errors into the human sentences users see. Raw errors never leave the server."""

GENERIC_500 = "Something went wrong on our side. Your changes are still on this page; please try again."

LABELS = {
    "title": "Title",
    "content": "Document content",
    "base_version": "Document version",
    "email": "Email",
    "role": "Access level",
    "file": "File",
}


def humanize_validation(errors: list[dict]) -> tuple[int, str]:
    """Map a Pydantic/FastAPI validation error list to (status, sentence)."""
    error = errors[0] if errors else {}
    loc = error.get("loc", ())
    kind = error.get("type", "")
    if loc and loc[0] == "path":  # e.g. /api/documents/abc
        return 404, "We couldn't find that document."
    field = next((p for p in reversed(loc) if isinstance(p, str) and p not in {"body", "query", "header"}), "")
    label = LABELS.get(field, "That field")
    if field == "role":
        return 422, "Choose either 'Can edit' or 'View only'."
    if field == "email" and kind in {"string_too_short", "missing"}:
        return 422, "Enter the email address of the person you want to share with."
    if field == "email" and kind == "string_pattern_mismatch":
        return 422, "That doesn't look like an email address. Check it and try again."
    if field == "file" and kind == "missing":
        return 422, "Choose a file to upload."
    if kind == "missing":
        return 422, f"{label} is required."
    if kind == "string_too_long":
        limit = error.get("ctx", {}).get("max_length")
        return 422, f"{label} is too long (max {limit} characters)." if limit else f"{label} is too long."
    if kind == "string_too_short":
        return 422, f"{label} can't be empty."
    if kind.startswith("int_"):
        return 422, f"{label} must be a whole number. Please refresh the page and try again."
    return 422, "Something in that request didn't look right. Please refresh the page and try again."


def humanize_http(status: int, detail, ours: bool = True):
    """Keep our own messages; replace the framework's raw ones ("Not Found", "Missing boundary in multipart.")."""
    if status == 400 and not ours:  # Starlette's multipart parser: boundary, part size, field/file counts
        return "That upload didn't come through correctly. Please try again."
    if status == 404 and detail == "Not Found":
        return "We couldn't find what you were looking for."
    if status == 405:
        return "That action isn't available here."
    if status == 400 and detail == "There was an error parsing the body":  # e.g. absurdly nested JSON
        return "We couldn't read that request. Please refresh the page and try again."
    return detail
