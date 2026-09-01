# Scene-Craft

**SceneCraft** — an agentic previs studio built for **Agentic Cinema: The Blockbuster Hackathon** (Google Cloud, Replit partner track).

A script goes in. A multi-agent system reads it, breaks it into scenes and shots, generates storyboard concept art, and autonomously builds and deploys a real, interactive previs web app — via Replit's Agent API — that a director can click through and iterate on in natural language.

Full product/technical specification lives in [`docs/`](docs/00-INDEX.md) — start there. The phase-by-phase build plan is in [`docs/08-IMPLEMENTATION-PLAN.md`](docs/08-IMPLEMENTATION-PLAN.md), with a detailed spec per phase in [`docs/Phases/`](docs/Phases/).

## Status

**Phase 1 (Foundations) is complete.** Auth, project CRUD, and script upload — everything else in `docs/Phases/` is planned but not yet built.

| Phase | Status |
|---|---|
| 1 — Foundations | ✅ Done |
| 2 — Script Breakdown Agent | Not started |
| 3 — Storyboard Frame Generation | Not started |
| 4 — App-Build & Critic Agents (Replit) | Not started |
| 5 — Iteration Loop & Trace UI | Not started |
| 6 — Observability, Security, Deployment | Not started |
| 7 — Demo & Submission | Not started |

## Repository layout

```
apps/
  api/          FastAPI control-plane backend (auth, projects, scripts)
  web/          Next.js frontend
agents/         (Phase 2+) per-agent implementations + orchestrator
mcp_server/     (Phase 2+) internal MCP server for agent tool access
infra/          (Phase 6) Terraform + Docker infra
docs/           PRD, system design, agent architecture, phase-by-phase plan
```

See [`docs/07-FOLDER-STRUCTURE.md`](docs/07-FOLDER-STRUCTURE.md) for the rationale behind this layout.

## Running locally

### Backend

```bash
cd apps/api
pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
uvicorn src.main:app --reload
```

API docs: `http://localhost:8000/docs`.

### Frontend

```bash
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev
```

Visit `http://localhost:3000`.

### Tests / checks

```bash
cd apps/api && ruff check . && mypy --strict src && pytest -v
cd apps/web && npm run typecheck && npm run build
```

CI (`.github/workflows/ci.yml`) runs the same checks — lint, type-check, test, build — on every pull request.

## What's implemented (Phase 1)

- Email/password signup and login, JWT-based auth
- Project creation and listing, scoped per-user (ownership checked before existence is ever revealed)
- Script upload (`.txt` or `.pdf`), with real PDF text extraction and validation
- Consistent JSON error envelope across all endpoints
- Per-instance rate limiting (documented as temporary — becomes the Redis-backed limiter in Phase 6)
- Alembic migrations against the real schema

## License

MIT — see [`LICENSE`](LICENSE).
