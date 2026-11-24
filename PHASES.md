# Build phases

Time budget: about 4 hours in total. Each phase ends with a check we actually run. If time runs out, stop after the last finished phase and record what's missing in SUBMISSION.md.

Status key: `[ ]` not started · `[~]` in progress · `[x]` done and verified

---

## Phase 0: Setup (~15 min)
- [x] Approve and install packages
  - **backend:** `fastapi uvicorn sqlalchemy psycopg[binary] alembic python-dotenv python-multipart mammoth markdown nh3 pytest httpx`
  - **frontend:** created with `create-next-app` (TypeScript, Tailwind, App Router), plus `@tiptap/react @tiptap/pm @tiptap/starter-kit`
- [ ] Neon: create a `dev` branch; its URL goes in `backend/.env` (done by the user)
- [x] Local test Postgres: `docker run -d --name docshare-test-pg -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:16`
- [x] `backend/.venv`, plus `requirements.txt` pinned with exact versions
- [x] `.gitignore` covering `.env*`, `.venv`, `node_modules`, `.next`
- [x] `git init`

**Done when:** `uvicorn main:app` and `next dev` both start.

## Phase 1: Backend core (~45 min)
- [x] Schema (users, documents, document_shares) in SQLAlchemy Core metadata
- [x] Alembic setup; migration 1 creates the tables, migration 2 seeds the data (Alice, Bob, Carol, plus one shared welcome doc)
- [x] Settings load `DATABASE_URL` from `backend/.env` (python-dotenv) for both the app and Alembic
- [x] Simulated auth dependency (`X-User-Id`)
- [x] `load_doc` access check: 404 with no access, 403 when the role is too low
- [x] Document routes: list (owned and shared), create, get, update with version check (409), delete
- [x] HTML sanitizing on write
- [x] Global exception handler: log the stack trace, return a generic 500
- [x] `ON DELETE CASCADE` from shares to documents in migration 1
- [x] Empty/whitespace title → "Untitled document"; content capped at 1 MB

**Done when:**
- `alembic upgrade head` then `alembic downgrade base` both succeed against the local test Postgres;
- pytest passes for:
  - access rules: a stranger gets 404, a viewer's save gets 403, an editor's delete gets 403;
  - the 409 on a stale save, with the first save's content kept;
  - sanitizing;
  - deleting a doc removes its shares.

## Phase 2: Sharing and import (~30 min)
- [x] Share by email with a role, change a role, unshare (owner only)
- [x] Share edge cases: unknown email, yourself, sharing twice (updates the role), email trimmed and lowercased
- [x] Import `.txt`, `.md` and `.docx` into a new document, with type, size, encoding and corrupt-file errors
- [x] Zip-bomb guard: reject a `.docx` whose total uncompressed size is over 20 MB

**Done when:**
- pytest passes for the sharing flow, the share edge cases, markdown import, and bad-file rejection (wrong type, empty, oversized, corrupt `.docx`, zip bomb);
- a real `.docx` imports correctly by hand.

## Phase 3: Frontend core (~60 min)
- [~] Sign-in screen listing the seeded users
- [~] Home page: "My documents" and "Shared with me" (owner and role badge), New, Import, Delete
- [~] Editor page: TipTap, toolbar (bold, italic, underline, text style H1–H3, bulleted and numbered lists, undo/redo), inline title, autosave with status
- [~] Viewers get a read-only editor
- [~] `lib/api.ts` maps statuses to behaviour (401 sign-in, 403 read-only, 404 not found, 409 conflict, 4xx inline, network/5xx retry)
- [~] `error.tsx` boundary; friendly page for a bad or unknown doc id
- [~] Browser-side size/type check before upload; Import disabled while uploading; note about images/tables

**Done when:**
- in a browser, create → format → reload → formatting is still there;
- rename persists, and import opens the new doc;
- `/docs/abc` shows the not-found page.

## Phase 4: Collaboration behaviour (~30 min)
- [~] Polling every 4 s; apply remote changes when there are no local edits
- [~] Conflict banner on 409: "Load their version" / "Keep mine"
- [~] Presence ("Bob is here")
- [~] Share dialog: add, change role, remove
- [~] One save at a time, with an edit counter; a stale poll never overwrites newer local content
- [~] Access removed / downgraded / doc deleted mid-edit → banner, text kept on screen, autosave stopped
- [~] Offline: "Offline, retrying" with growing delays; warn before closing the tab with unsaved edits
- [~] `localStorage` backup of unsaved content, with a "Restore unsaved changes?" prompt
- [~] "Waking up the server…" retry on first load

**Done when:** with two browsers (Alice and Bob):
- edits appear on the other side within ~4 s;
- typing in both at once shows the banner, and no text is lost;
- Alice removing Bob's access, or making him a viewer, while he types shows his banner, and his text stays;
- turning the network off in DevTools while typing shows "Offline, retrying", and the edits save once it's back on.

(Phase 4 is now ~60 min. If time is short, cut the `localStorage` backup first.)

## Phase 5: Deploy (~30 min)
- [x] Neon database created and migrated to `0002 (head)` on 2026-11-24 (by the user; the URL goes into Render's environment settings, never into the repo or chat)
- [ ] API on Render (`DATABASE_URL`); start command `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`. This is the first migration against production, so confirm with the user first.
- [ ] Frontend on Vercel (`BACKEND_URL`)

**Done when:** the full two-user flow works on the live URLs.

## Phase 6: Submission (~30 min)
- [ ] README.md: local setup, test command, seeded accounts, live URL
- [ ] AI_WORKFLOW.md: tools used, where AI sped things up, what was changed or rejected, how it was verified
- [ ] SUBMISSION.md: everything included; what works, what's incomplete, what comes next
- [ ] Screenshots; VIDEO_URL.txt with the walkthrough link
- [ ] Google Drive folder with the source, excluding `.env`, `node_modules`, `.venv` and `.next`

---

## Current state
- Attack tests (2026-11-24): backend 216 passed (incl. 152 security + 52 race/import in their own DBs), frontend 51 passed; 19 real bugs found and fixed. No schema changes (alembic check clean), so Neon needs no new migration.
- Phases 1–2: verified (`pytest` 12 passed; alembic upgrade/downgrade/upgrade clean).
- Phases 3–4: built; tsc, lint and build pass, and the API works through the Next.js proxy. **Browser and two-user checks still to do.**

<!-- older notes below -->
Some Phase 1–3 code was written before these plans existed: `backend/db.py`, `backend/main.py`, `backend/test_api.py`, `backend/requirements.txt`, `frontend/package.json`, `frontend/next.config.mjs`, `frontend/lib/api.js`, `frontend/app/layout.js`, `frontend/app/page.js`. **None of it has been installed or run.** It counts as `[~]` until Phase 0 is done and its checks pass. The editor page, Toolbar, SharePanel and CSS have not been written.

It also doesn't follow the CLAUDE.md layout yet:
- the backend has its logic inside `main.py` and needs splitting into `routers/` and `services/`;
- the backend defaults to SQLite and uses `create_all`; both get replaced by Postgres and Alembic;
- the frontend files are plain JS and need rewriting in TypeScript with Tailwind.
