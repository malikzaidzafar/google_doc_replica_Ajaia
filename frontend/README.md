# DocShare frontend

Next.js 16 (App Router) + TypeScript + Tailwind + TipTap. See the root `README.md`, `ARCHITECTURE.md` and `CLAUDE.md`.

```bash
npm install
BACKEND_URL=http://127.0.0.1:8000 npm run dev   # /api/* is proxied to FastAPI
npx tsc --noEmit && npm run lint && npm run build
```
