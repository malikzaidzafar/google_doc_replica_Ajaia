"""Who has a document open right now (fed by the client's 4 s poll)."""
import time

# ponytail: presence lives in process memory, so it only works with a single API instance.
# Move it to a table (or Redis) before running more than one instance.
_SEEN: dict[int, dict[int, float]] = {}
WINDOW_SECONDS = 15


def touch(doc_id: int, user_id: int) -> list[int]:
    """Record that user_id has doc_id open; return the other users seen within the window."""
    seen = _SEEN.setdefault(doc_id, {})
    t = time.monotonic()
    seen[user_id] = t
    return [uid for uid, ts in seen.items() if uid != user_id and t - ts < WINDOW_SECONDS]
