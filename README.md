# Scene-Craft

**SceneCraft** — an agentic previs studio built for **Agentic Cinema: The Blockbuster Hackathon** (Google Cloud, Replit partner track).

A script goes in. A multi-agent system reads it, breaks it into scenes and shots, generates storyboard concept art, and autonomously builds a real, interactive previs web app — its own capability, verified by a Critic Agent, served from SceneCraft itself and hosted on Replit per the partner track's actual requirement (see `docs/Phases/PHASE-04-APP-BUILD-AND-CRITIC.md` §0) — that a director can click through and iterate on in natural language.

Full product/technical specification lives in [`docs/`](docs/00-INDEX.md) — start there. The phase-by-phase build plan is in [`docs/08-IMPLEMENTATION-PLAN.md`](docs/08-IMPLEMENTATION-PLAN.md), with a detailed spec per phase in [`docs/Phases/`](docs/Phases/).

## Status

**Phase 3 (Storyboard Frame Generation) is complete and verified live end to end** — real script upload, real breakdown, real generated frames (via `gemini-2.5-flash-image` on Vertex AI, not the dedicated Imagen API — see `docs/Phases/PHASE-03-FRAME-GENERATION.md`), real captioning, all persisted through the actual API. Known operational constraint worth flagging before any live demo: the `GEMINI_API_KEY`'s free tier caps `gemini-2.5-flash` at 5 requests/minute, and breakdown plus concurrent per-shot captioning can burn through that fast on anything but a small script.

| Phase | Status |
|---|---|
| 1 — Foundations | ✅ Done |
| 2 — Script Breakdown Agent | ✅ Done |
| 3 — Storyboard Frame Generation | ✅ Done |
| 4 — App-Build & Critic Agents | Not started |
| 5 — Iteration Loop & Trace UI | Not started |
| 6 — Observability, Security, Deployment | Not started |
| 7 — Demo & Submission | Not started |

## Repository layout

```
apps/
  api/            FastAPI control-plane backend (auth, projects, scripts, jobs)
  web/            Next.js frontend
agents/           Agent orchestrator + per-agent implementations (breakdown_agent, frame_agent live; app_build/critic/iteration are Phase 4+)
mcp_server/       Internal MCP server exposing project-state tools to agents
infra/            (Phase 6) Terraform + Docker infra
docs/             PRD, system design, agent architecture, phase-by-phase plan
```

See [`docs/07-FOLDER-STRUCTURE.md`](docs/07-FOLDER-STRUCTURE.md) for the rationale behind this layout.

## Architecture note: three independent Python packages

`apps/api`, `mcp_server`, and `agents` each have their own `pyproject.toml` and their own virtualenv — they're separate deployable units (per `03-SYSTEM-DESIGN.md`), not one monolith. In particular:

- **`agents` never talks to the database.** It calls `mcp_server` over the real MCP protocol (stdio), which in turn calls `apps/api`'s `/internal/v1/*` endpoints over HTTP (guarded by a shared-secret header). This is the literal MCP-server boundary the hackathon rubric asks for, not just a design diagram.
- **`apps/api` triggers agent runs as a subprocess**, not an in-process call — `agents/` has its own dependencies (`mcp`, `google-genai`) that must not be installed into `apps/api`'s venv. This is the local-dev stand-in for the Pub/Sub + Cloud Run job Phase 6 provisions.

## Running locally

### Database

```bash
docker compose up -d postgres
```

Brings up a local Postgres matching Cloud SQL's behavior more closely than the SQLite fallback. SQLite still works out of the box for fast iteration — see `apps/api/.env.example`.

### 1. Backend (control plane)

```bash
cd apps/api
pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
uvicorn src.main:app --reload
```

API docs: `http://localhost:8000/docs`.

### 2. MCP server (Phase 2+)

```bash
cd mcp_server
pip install -e ".[dev]"
cp .env.example .env   # INTERNAL_SERVICE_KEY must match apps/api's .env exactly
```

No standalone process to run — `agents` spawns this over stdio on demand.

### 3. Agents (Phase 2+)

```bash
cd agents
pip install -e ".[dev]"
cp .env.example .env
# Set GEMINI_API_KEY (from https://aistudio.google.com/apikey) — this alone
# is enough for breakdown (Phase 2) and captioning.
# Set MCP_SERVER_PYTHON_EXECUTABLE to mcp_server/.venv's interpreter
```

Frame generation (Phase 3) additionally needs a **Vertex AI-enabled GCP project** — image generation only works in Vertex AI mode, not under a plain Gemini Developer API key (0 quota on the free tier):

```bash
# In agents/.env, once you have a GCP project with billing + the Vertex AI
# API (aiplatform.googleapis.com) enabled, and are logged in via
# `gcloud auth application-default login`:
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

Uses `gemini-2.5-flash-image` rather than the dedicated Imagen `generate_images()` API — the latter stayed inaccessible (404) for a real test project even with billing and the Vertex AI API both enabled, since Model Garden gates generative-media models individually; `gemini-2.5-flash-image` worked immediately. See `docs/Phases/PHASE-03-FRAME-GENERATION.md`'s model note.

Without `GOOGLE_CLOUD_PROJECT` set, breakdown still runs fine — frame generation just isn't reachable yet (`ImagenNotConfiguredError`, caught per-shot, never blocks the rest of the pipeline in a way that leaves the job stuck).

Then point `apps/api/.env` at this venv so uploads actually trigger a run:

```
AGENTS_PYTHON_EXECUTABLE=<repo>/agents/.venv/Scripts/python.exe   # Windows
AGENTS_WORKING_DIR=<repo>/agents
```

Without this, script uploads still create a job — it just stays `queued` (see `apps/api/src/core/agent_runner.py`).

### 4. Frontend

```bash
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev
```

Visit `http://localhost:3000`.

### Tests / checks

```bash
cd apps/api    && ruff check . && mypy --strict src && pytest -v
cd mcp_server  && ruff check . && mypy --strict src && pytest -v
cd agents      && ruff check . && mypy --strict orchestrator breakdown_agent frame_agent shared && pytest -v
cd apps/web    && npm run typecheck && npm run build
```

CI (`.github/workflows/ci.yml`) runs the same checks — lint, type-check, test, dependency audit, build — on every pull request, one job per package.

## What's implemented

**Phase 1** — Email/password signup and login (JWT), project creation and listing (ownership checked before existence is ever revealed), script upload (`.txt`/`.pdf`) with real PDF extraction, consistent JSON error envelope, per-instance rate limiting (documented as temporary — becomes Redis-backed in Phase 6), Alembic migrations.

**Phase 2** — Script upload now creates a `GenerationJob` and (if `agents` is configured) triggers a real breakdown run: the script is chunked on scene boundaries, each chunk sent to Gemini with a schema-constrained prompt, validated, retried once on failure, and persisted via `mcp_server`'s tools. A scene that fails validation twice is flagged `needs_review` and the job still completes — one bad scene never blocks the rest. `GET /api/v1/jobs/{id}` and `GET /api/v1/projects/{id}` expose job status and the resulting breakdown.

**Phase 3** — After breakdown completes, the Coordinator fans out one concurrent worker per shot (`asyncio.gather`, real concurrency via `asyncio.to_thread` around the blocking image-generation/captioning calls — not a serial loop). Each worker generates a frame using the project's locked style reference (via `gemini-2.5-flash-image` on Vertex AI — the dedicated Imagen API stayed inaccessible for this project even with billing and the Vertex AI API enabled, see `docs/Phases/PHASE-03-FRAME-GENERATION.md`), captions it via Gemini multimodal, and writes the result through a new `write_frame_record` MCP tool. A shot's frame generation and its captioning are independent failure modes: a persistent generation failure (3 retries, exponential backoff) inserts a placeholder and flags the shot; a captioning-only failure keeps the real image and just falls back on alt-text. `GET /api/v1/jobs/{id}` reports live `{"completed", "total", "failed"}` sub-progress for the `frames` step. Frames are written to a local-dev stand-in for Cloud Storage (`agents/.local_storage/`, swapped for real GCS in Phase 6). **Verified live end to end** — real script → real breakdown → real generated frames → real captions, all persisted through the actual API, no mocks.

## License

MIT — see [`LICENSE`](LICENSE).
