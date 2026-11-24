# Architecture: DocShare

A small Google-Docs-style editor: create and edit rich-text documents, import files, and share documents with other users. It was built in a 4–6 hour timebox, so the scope is cut on purpose. See "What we cut, and why" below.

## Shape

```
Browser ── Next.js (Vercel) ── /api/* rewrite ──▶ FastAPI (Render) ──▶ Postgres (Neon)
           TipTap editor                         access checks,
           autosave + polling                    sanitizing, import
```

- **One origin for the browser.** Next.js forwards `/api/*` to FastAPI, so there's no CORS setup and the API URL is a single setting (`BACKEND_URL`).
- **Postgres in every environment.** Dev and production can't drift apart in database behaviour.

| Environment | Database | Where its URL lives |
|---|---|---|
| Production | Neon `main` branch | Render settings |
| Local development | Neon `dev` branch | `backend/.env`, never committed |
| Tests | Disposable Postgres in Docker on localhost | The tests refuse any non-local host |

- **Schema changes only go through Alembic migrations.**

## Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind | Standard React setup; rewrites handle the API proxy; types catch API mismatches |
| Editor | TipTap v3 (ProseMirror) | Its StarterKit covers bold, italic, underline, headings, lists and undo; a mature, well-understood editor |
| API | FastAPI + Pydantic | Request validation comes from type hints; the test client makes API tests short |
| Database | Postgres (Neon) + psycopg 3 | Free, persistent, with branches for dev and production |
| DB access | SQLAlchemy Core | Explicit queries without the overhead of an ORM; its metadata feeds Alembic |
| Migrations | Alembic | Versioned, repeatable schema changes; deploys run `alembic upgrade head` |
| Import | mammoth (.docx), markdown (.md) | Both convert to HTML, the format we already store |
| Sanitizing | nh3 | Allowlist HTML sanitizer, run on every write |

## Code organisation

- **Backend:** routers are thin HTTP adapters (validate → call one service → return). All business logic lives in `services/`: access checks, version-checked saves, sharing, import and sanitizing. Rules can then be tested and reviewed in one place.
- **Frontend:** pages only compose components. Stateful logic (autosave, polling, conflict handling) lives in hooks. No file is longer than 100 lines, so each one has a single job.

## Data model

```
users            id, email (unique), name
documents        id, owner_id → users, title, content (HTML), version, updated_at, updated_by → users
document_shares  (document_id, user_id) PK, role: "viewer" | "editor"
```

- **Ownership:** each document has exactly one owner, stored as `documents.owner_id`. Sharing never transfers it.
- **Content:** stored as sanitized HTML from `editor.getHTML()`. All formatting survives a reload, and imported files convert straight into the same format.
- **`version`:** an integer that goes up on every save. Conflict detection relies on it (see below).

## Auth (simulated)

- **Seeded accounts:** Alice, Bob and Carol. The sign-in screen lets you pick one, with no password.
- **How requests identify you:** the client keeps the chosen user id and sends it as `X-User-Id`.
- **Limit:** this is not real authentication, and the README says so. With more time it becomes session cookies with real login; nothing else in the API would change, because every route gets the user from one dependency.

## Access control

Every document route goes through one function, `load_doc(doc_id, user, need)`. It returns the caller's role, ranked `viewer < editor < owner`.

| Situation | Response |
|---|---|
| No access to the document | **404**: we don't reveal that the document exists |
| Role too low for the action | **403** |
| Viewer | Can read; editor is read-only |
| Editor | Can read, edit and rename |
| Owner | Can also share, change roles, unshare and delete |

The home page lists **My documents** and **Shared with me** separately. Shared entries show the owner's name and your role.

## Editing and saving

- **Autosave:** about 1 s after the last keystroke, with a status line showing "Saving…", "All changes saved", "Unsaved changes" or "Conflict".
- **Title:** edited inline and saved through the same path as the content.
- **Leaving the page:** the app warns before you close a tab with unsaved changes. The "back" button saves before navigating.

## Two people editing at once

We use **optimistic concurrency**, with no live merging:

1. **Every save carries the version it was based on**, as `base_version`.
2. **The server checks and writes in one atomic statement:** `UPDATE … SET version = version + 1 WHERE id = ? AND version = ?`.
   - **No row updated** means someone else saved first. The server answers **409** with the latest document.
   - **On a 409, the client keeps the user's edits on screen** and shows a banner: *"Bob saved a newer version while you were editing."* The choices are **Load their version** or **Keep mine (overwrite)**. Nothing is lost silently.
3. **Polling:** while a doc is open, the client polls every 4 s. If the server is ahead and the user has no unsaved edits, the client quietly loads the new version. In practice, a conflict needs two people typing within the same few seconds.
4. **Presence:** the same poll records who has the doc open, so the header shows "Bob is here".

**Why not real-time merging (Yjs/CRDT over websockets)?** It's the right end state, but it changes storage, needs a websocket service, and is 2–3× the work. Optimistic concurrency gives correct behaviour, with no lost writes, inside the timebox. It's first on the "next" list.

## File import

- **Supported files:** `.txt`, `.md` and `.docx`, up to 2 MB. Each import creates a new document owned by the uploader.
- **Conversion:**
  - `.docx` → HTML via mammoth, with underline mapped so it survives.
  - `.md` → HTML via markdown.
  - `.txt` → one escaped paragraph per line.
- **Errors:** an unsupported type, an empty file, a non-UTF-8 text file, a corrupt `.docx` or an oversized file each get a clear 400/413 message.
- **UI:** the supported types and the size limit appear next to the Import button.

## Validation and security

- **HTML:** every write is sanitized with an allowlist covering only the tags the editor can show. Scripts, event handlers, `javascript:` links and images are stripped. This matters because a shared document is rendered in someone else's browser.
- **Input limits:** Pydantic validates every body. Titles are 1–200 characters after trimming, content is capped at 1 MB, and roles are an enum.
- **Transactions:** each request runs in one database transaction, which rolls back on any error.
- **Secrets:** `DATABASE_URL` lives only in the hosting provider's environment settings. It is never committed.

## Edge cases and error handling

**Rule underneath all of this: a user's typing is never replaced because of an error.** Server content only replaces local content when the user has no unsaved edits, or when they click "Load their version".

### Error contract
- **Backend:**
  - Services raise errors with plain-language messages, and every error response has the same shape (`{"detail": ...}`).
  - One global handler catches unexpected exceptions. It logs the stack trace and returns a generic 500, so nothing internal leaks.
  - Each request runs in one transaction.
- **Frontend:**
  - Every request goes through `lib/api.ts`, which turns any failure into an `ApiError(status, message)`.
  - Each status has one meaning across the app:

    | Status | UI behaviour |
    |---|---|
    | 401 | Back to sign-in |
    | 403 | Editor becomes read-only, with a banner; unsaved text stays visible |
    | 404 | "Not found / access removed" |
    | 409 | Conflict banner |
    | 400 / 413 / 422 | Inline message |
    | network error / 5xx | Retry with growing delays, status shows "Offline, retrying" |

  - A Next.js `error.tsx` boundary catches rendering crashes.

### Collaboration
| Case | Behaviour | Status |
|---|---|---|
| Two people edit at once | 409 → banner with "Load theirs" / "Keep mine" (see above) | Handled |
| Rename by one user while another edits the content | Both bump `version`, so the editor gets a conflict even though different fields changed; "Keep mine" resolves it | Known limit |
| Access removed while editing | Next save/poll → 404 → "Your access was removed"; text stays on screen read-only and copyable; autosave stops | Handled |
| Downgraded from editor to viewer while editing | Save → 403 → editor turns read-only with a banner; unsaved text stays visible | Handled |
| Document deleted while others have it open | Same as access removed: "This document was deleted" | Handled |
| Same user in two tabs | Treated like two users; the version check protects them | Handled |
| Typing while a save is in flight | At most one save at a time; an edit counter makes sure newer edits are saved next | Handled |
| Poll response arrives after our own save | Server content is applied only if its version is newer than ours | Handled |

### Network and hosting
| Case | Behaviour | Status |
|---|---|---|
| Connection drops while editing | "Offline, retrying" with growing delays; warns before closing the tab with unsaved edits | Handled |
| Browser crash / tab killed with unsaved edits | Unsaved content is mirrored to `localStorage`; on reopen: "Restore unsaved changes?" | Handled |
| API asleep on Render free tier (30–60 s cold start) | First load shows "Waking up the server…" and retries | Handled |
| Neon closes idle connections | `pool_pre_ping` reconnects | Handled |
| Migration fails during deploy | The start command fails; Render keeps the previous version live | Known behaviour |

### Sharing
| Case | Behaviour |
|---|---|
| Unknown email | 400 "No account uses …" |
| Sharing with yourself | 400 "You already own this document" |
| Sharing with someone twice | Updates their role; the share table's primary key prevents duplicates |
| Email with spaces or capitals | Trimmed and lowercased before lookup |
| Non-owner tries to share, change roles or delete | 403 (404 if they have no access at all) |
| Ownership transfer, "remove from my list" | Cut |

### File import
| Case | Behaviour |
|---|---|
| Unsupported type, empty file, non-UTF-8 text | 400 with a specific message |
| Over 2 MB | 413; also checked in the browser before uploading |
| Renamed or corrupt `.docx` (e.g. a PDF) | Converter fails → 400 "Not a valid Word document" |
| Zip bomb (small `.docx` that expands hugely) | Total uncompressed size is checked before converting; over 20 MB → 400 |
| `.docx` with images or tables | Images dropped, tables flattened to text; noted next to the Import button |
| Script or HTML injection inside `.md` | Stripped by the sanitizer |
| Double-clicking Import | Button disabled while an upload is in flight |

### Content and data
| Case | Behaviour |
|---|---|
| Content over 1 MB | 413/422 with a message; text stays in the editor |
| Empty or whitespace title | Saved as "Untitled document" |
| Pasting from Word or Google Docs | The editor schema drops formatting it doesn't support; the server sanitizes again |
| Bad or unknown doc id in the URL (`/docs/abc`) | Friendly "not found" page |
| Deleting a document | Shares are removed by `ON DELETE CASCADE` in the same transaction |
| Two saves racing in Postgres | The version-checked `UPDATE` holds a row lock; the loser matches 0 rows → 409 |

## Deployment

| Piece | Host | Notes |
|---|---|---|
| Frontend | Vercel (free) | Env: `BACKEND_URL` |
| API | Render (free web service) | Env: `DATABASE_URL`. It sleeps when idle, so the first request takes ~30–60 s |
| Database | Neon Postgres (free) | Persistent, so reviewers' documents survive the API sleeping |

Each deploy runs Render's start command, `alembic upgrade head && uvicorn …`:
- **Migration 1** creates the tables.
- **Migration 2** seeds the demo users and the shared welcome document.

The API never creates tables itself.

## What we cut, and why

| Cut | Reason |
|---|---|
| Real-time co-editing (CRDT) | Biggest risk to the timebox; optimistic concurrency already prevents lost writes |
| Real authentication | Not needed to demonstrate the sharing logic; isolated behind one dependency |
| Comments, suggestions, version history | Stretch items; depth in the core flows first |
| Images and tables in documents | Outside the required formatting set; stripped by the sanitizer |

## Next 2–4 hours

1. Live co-editing with Yjs (via `pycrdt`) over websockets, replacing polling.
2. Real login with session cookies.
3. Version history: keep the previous `content` row on every save. This builds on the version column we already have.
4. Export to Markdown/PDF.
