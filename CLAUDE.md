# CLAUDE.md

DocShare: a take-home Google-Docs-style editor (FastAPI + Next.js + TipTap). Read `ARCHITECTURE.md` for the design and `PHASES.md` for the plan and current status.

## Layout
```
backend/                 FastAPI
  main.py                  app setup + router registration only
  config.py                loads backend/.env (python-dotenv), exposes DATABASE_URL
  db.py                    SQLAlchemy Core schema (metadata) + engine
  alembic/versions/        migrations: 0001 schema, 0002 demo seed data
  deps.py                  request dependencies: DB connection, current user
  schemas.py               Pydantic request/response models
  routers/                 HTTP layer: documents, shares, imports, users
  services/                all business logic
    access.py                load_doc(): the single access check
    documents.py             list/create/get/update (version check)/delete
    sharing.py               share, change role, unshare
    importer.py              file → HTML conversion and validation
    sanitize.py              HTML allowlist
    presence.py              who has a doc open
  tests/test_api.py        pytest API tests

frontend/                Next.js App Router + TypeScript + Tailwind
  app/                     pages: compose components, no logic
  components/              UI pieces (Toolbar, SharePanel, ConflictBanner, DocList, SignIn, …)
  hooks/                   stateful logic (useDocSync: autosave/polling/conflicts, useDocuments, …)
  lib/api.ts               fetch wrapper; sends X-User-Id
  lib/types.ts             shared API types
```

## Commands
```bash
# backend (from backend/)
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
alembic upgrade head                      # against DATABASE_URL from backend/.env (Neon dev branch)
uvicorn main:app --reload --port 8000
alembic revision --autogenerate -m "..."  # after changing db.py metadata; review the generated file

# tests: disposable local Postgres only
docker run -d --name docshare-test-pg -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:16
TEST_DATABASE_URL=postgresql://postgres:test@localhost:5433/postgres pytest -q

# frontend (from frontend/)
npm install
npm run dev                               # http://localhost:3000, proxies /api to BACKEND_URL (default http://127.0.0.1:8000)
npx tsc --noEmit                          # type check
```

## Backend rules
- **Routes stay thin.** A route handler only:
  - parses the request (Pydantic schema plus deps)
  - calls one service function
  - returns its result

  No SQL, no access checks and no branching on business rules in `routers/`.
- **All logic lives in `services/`:** queries, access decisions, version checks, sanitizing, import conversion.
- **Services don't know about the web framework,** with one exception: they raise `HTTPException` for 400/403/404/409/413.
- **All document access goes through `services/access.py:load_doc()`.** Never query `documents` for a user without it.
- **Every content write goes through `sanitize()`.** Stored HTML is shown in other users' browsers.
- **Saves must keep the version check** (`WHERE version = base_version`, with a 409 on mismatch). Never fall back to last-write-wins.

## Error messages
- **Raw backend errors never reach the user.** That includes stack traces, SQL/driver errors, exception class names, Pydantic validation dumps, `Request failed (500)` and the like.
- **Backend:**
  - Expected failures raise `HTTPException` with a short, human sentence that says what happened and what to do (e.g. "That file is larger than 2 MB. Try a smaller file.").
  - Unexpected exceptions are caught by one global handler. It logs the full traceback server-side and returns a generic message: "Something went wrong on our side. Your changes are still on this page; please try again."
  - 422 validation errors are rewritten into human messages ("Title can't be empty"), never returned raw.
- **Frontend:**
  - `lib/api.ts` is the only place that turns responses into user-facing text.
  - Network failures read "Can't reach the server. Check your connection; we'll keep retrying."
  - Anything without a usable `detail` falls back to a friendly generic message. Never show a status code, `statusText` or `error.message` from `fetch`/JS directly.
- **Tone:** plain language, no blame, no jargon (avoid "invalid", "unauthorized", "exception"), and say what to do next.

## Database rules
- **Postgres only.** No SQLite fallback anywhere.
- **Every schema change is an Alembic migration.**
  - Never call `metadata.create_all()` in app code.
  - Never edit a migration that has already been applied; add a new one.
- **Migrations must be reversible:** every revision has a working `downgrade()`.
- **Tests run only against `TEST_DATABASE_URL`.** The test setup asserts that its host is `localhost` or `127.0.0.1` and aborts otherwise.
- **Never run `alembic upgrade`/`downgrade`, seed scripts or tests against Neon** (dev or production branch) without the user's explicit OK for that specific run.

## Frontend rules
- **Next.js App Router, TypeScript (`strict`) and Tailwind CSS.** No plain `.js`/`.jsx` files, and no separate CSS files beyond Tailwind's `globals.css`.
- **No frontend file over 100 lines.** When a file grows past that, split it: logic goes into a hook in `hooks/`, UI into smaller components.
- **Pages only compose.** Stateful logic (fetching, autosave, polling, conflict handling) lives in hooks; components mostly render props.
- **Type every API response** in `lib/types.ts`. No `any`.
- **All requests go through `lib/api.ts`.**
- **Accessibility:** buttons get labels, toggles use `aria-pressed`, errors use `role="alert"`, and dialogs use the native `<dialog>`.

## General rules
- **Never read, print or edit `backend/.env` or any `.env*` file**, and never handle the Neon/production `DATABASE_URL`. The user sets it in the hosting dashboard.
- **Ask before installing packages or changing the stack**, and before starting work outside the current phase in `PHASES.md`.
- **Update `PHASES.md` checkboxes only after the phase's "Done when" check has actually been run.**
- Keep the scope cuts listed in `ARCHITECTURE.md` unless the user changes them.
