# DocShare

A lightweight collaborative document editor inspired by Google Docs. Create and format documents, import `.txt` / `.md` / `.docx` files, share with other users as **editor** or **viewer**, and edit the same document at the same time without losing anyone's work.

- **Live app:** _(add Vercel URL)_
- **Walkthrough video:** https://www.loom.com/share/0b8fa644ce6a45ecabaf061f7370b2dc
- **Design and trade-offs:** [ARCHITECTURE.md](ARCHITECTURE.md) · **AI usage:** [AI_WORKFLOW.md](AI_WORKFLOW.md) · **Submission summary:** [SUBMISSION.md](SUBMISSION.md)

## Demo accounts

There are no passwords. The sign-in screen lets you pick a seeded user. To try sharing, use two browsers (or one normal and one private window).

| User | Email | Access to "Welcome to DocShare" |
|---|---|---|
| Alice | alice@example.com | Owner |
| Bob | bob@example.com | Can edit |
| Carol | carol@example.com | View only |

## Features

- **Documents:** create, rename inline, edit, delete (owner only), with autosave and a live save status.
- **Formatting:** bold, italic, underline, Normal / Heading 1–3, bulleted and numbered lists, undo/redo.
- **File import:** `.txt`, `.md` or `.docx` up to 2 MB, imported as a new editable document. Images and tables in `.docx` files are not imported.
- **Sharing:** the owner shares by email as *Can edit* or *View only*, and can change roles or remove access. The home page separates **My documents** from **Shared with me**.
- **Concurrent editing:**
  - every save carries a version number, and a stale save gets a 409 and a "Load their version / Keep mine" banner instead of overwriting;
  - the open document polls every 4 s, picking up others' changes and showing who is there;
  - unsaved edits are backed up in the browser.
- **Persistence:** Postgres (Neon in production) with Alembic migrations. Content is stored as sanitized HTML.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS v4, TipTap v3 |
| Backend | FastAPI, Pydantic, SQLAlchemy Core, psycopg 3 |
| Database | PostgreSQL (Neon in production), Alembic migrations |
| Import | mammoth (`.docx`), Python-Markdown (`.md`); sanitized with nh3 |
| Hosting | One Vercel project: `/api/*` → FastAPI service, everything else → Next.js ([vercel.json](vercel.json)) |

## Repository layout

```
backend/
  main.py              app setup, routers, error handlers
  config.py            loads DATABASE_URL (from env or backend/.env)
  db.py                schema (SQLAlchemy Core) + engine
  deps.py, schemas.py  request dependencies and Pydantic models
  routers/             thin HTTP layer
  services/            all business logic (access checks, saves, sharing, import, sanitizing)
  alembic/versions/    0001 schema, 0002 demo seed data
  tests/               API, security and concurrency/import test suites
frontend/
  app/                 pages (compose components only)
  components/          UI (components/ui = design-system primitives)
  hooks/               autosave, polling, conflict handling, sessions
  lib/                 API client (the only place error text is produced), types, drafts
  tests/               Node test-runner suites for the save logic and error handling
vercel.json            deployment routing
```

## Run locally

**Prerequisites:** Python 3.12, Node.js 22, and a Postgres database. The quickest database is Docker; a Neon branch also works.

### 1. Database

```bash
docker run -d --name docshare-pg -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:16
```

### 2. Backend (terminal 1)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
echo 'DATABASE_URL=postgresql://postgres:test@localhost:5433/postgres' > .env   # never commit .env
.venv/bin/alembic upgrade head        # creates tables and seeds Alice, Bob, Carol + the welcome doc
.venv/bin/uvicorn main:app --reload --port 8000
```

Check it: `curl http://127.0.0.1:8000/api/users` should list the three users.

### 3. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev                           # http://localhost:3000
```

The frontend proxies `/api/*` to `BACKEND_URL`, which defaults to `http://127.0.0.1:8000`. The browser only talks to one origin, so no CORS setup is needed.

## Tests

The backend tests **drop and recreate the schema** of the database they're given, and refuse to run against anything that isn't localhost. Give them their own database:

```bash
docker exec docshare-pg psql -U postgres -c "CREATE DATABASE docshare_test"

cd backend
TEST_DATABASE_URL=postgresql://postgres:test@localhost:5433/docshare_test .venv/bin/pytest -q
# 216 passed: core API (12), adversarial security (152), real-concurrency + hostile-file imports (52)

cd ../frontend
npm test                               # 51 passed: save state machine, error humanizing, drafts, upload checks
npx tsc --noEmit && npm run lint && npm run build
```

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | backend (`backend/.env` locally, Vercel project settings in production) | Postgres connection string. `postgres://` and `postgresql://` URLs are both accepted |
| `TEST_DATABASE_URL` | when running the tests | A **local** Postgres database that the tests may wipe |
| `BACKEND_URL` | frontend, local dev only | Where `/api/*` is proxied (default `http://127.0.0.1:8000`). Not needed on Vercel, where `vercel.json` routes `/api/*` |

## Deployment (Vercel)

1. Import the GitHub repo in Vercel with Root Directory `./` and Application Preset **Services**. Vercel reads [vercel.json](vercel.json).
2. Add the environment variable `DATABASE_URL` (the Neon connection string).
3. Deploy. `/api/*` is served by FastAPI and everything else by Next.js, on one domain.
4. **Migrations** don't run on deploy. Run them from your machine against the production database before deploying code that needs a schema change:
   ```bash
   cd backend && DATABASE_URL='<neon-connection-string>' .venv/bin/alembic upgrade head
   ```

## Known limitations

- **Simulated sign-in only.** The client sends the selected user's id in an `X-User-Id` header. It isn't real authentication, and it's isolated so real sessions can replace it.
- **Conflicts aren't merged.** Simultaneous edits give a conflict choice rather than a character-level merge; live co-editing (Yjs) is the next step.
- **Presence can miss someone.** "X is here" lives in server memory, so on serverless with several instances it can occasionally miss a user.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design, the edge-case table and the scope cuts.
