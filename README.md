# Scene-Craft

**SceneCraft** — an agentic previs studio built for **Agentic Cinema: The Blockbuster Hackathon** (Google Cloud, Replit partner track).

A script goes in. A multi-agent system reads it, breaks it into scenes and shots, generates storyboard concept art, and autonomously builds a real, interactive previs web app — its own capability, verified by a Critic Agent, served from SceneCraft itself and hosted on Replit per the partner track's actual requirement (see `docs/Phases/PHASE-04-APP-BUILD-AND-CRITIC.md` §0) — that a director can click through and iterate on in natural language.

Full product/technical specification lives in [`docs/`](docs/00-INDEX.md) — start there. The phase-by-phase build plan is in [`docs/08-IMPLEMENTATION-PLAN.md`](docs/08-IMPLEMENTATION-PLAN.md), with a detailed spec per phase in [`docs/Phases/`](docs/Phases/).

## Status

**Phases 1-5 are complete and verified live end to end** — real script upload, breakdown, frame generation, self-hosted previs generation with Critic verification, and natural-language iteration with a live Firestore-backed trace panel, all exercised against real Gemini/Vertex AI and a real browser, no mocks. Known operational constraint worth flagging before any live demo: the `GEMINI_API_KEY`'s free tier caps `gemini-2.5-flash` at both 5 requests/minute *and* a 20-requests/day quota — a single day of active development/demo rehearsal can exhaust it (the app handles this correctly, as an honest `failed_needs_review`/`needs_clarification` state, but it's worth having a fallback key or upgraded quota before judging).

**Phase 6's code and infrastructure-as-code are complete** (OpenTelemetry tracing, Redis-backed rate limiting, Pub/Sub job dispatch, structured logging, full Terraform for the production architecture, CI/CD deploy pipeline) but **not yet applied to a live environment** — `terraform plan` against the real GCP project is clean (72 resources, no errors), but `terraform apply` is a deliberate, separate step held off until closer to Phase 7 demo prep to avoid weeks of idle Cloud SQL/Memorystore billing. See `infra/README.md` for the full rationale, cost estimate, and what's needed to actually deploy.

| Phase | Status |
|---|---|
| 1 — Foundations | ✅ Done |
| 2 — Script Breakdown Agent | ✅ Done |
| 3 — Storyboard Frame Generation | ✅ Done |
| 4 — App-Build & Critic Agents | ✅ Done |
| 5 — Iteration Loop & Trace UI | ✅ Done |
| 6 — Observability, Security, Deployment | Code + Terraform done, not yet deployed |
| 7 — Demo & Submission | Not started |

## Repository layout

```
apps/
  api/            FastAPI control-plane backend (auth, projects, scripts, jobs)
  web/            Next.js frontend
agents/           Agent orchestrator + per-agent implementations (breakdown, frame, app_build, critic, iteration — all live)
mcp_server/       Internal MCP server exposing project-state tools to agents
infra/            firestore/ (live), terraform/ (full IaC, validated but not yet applied — see infra/README.md), grafana/ (dashboard JSON)
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

Live agent-trace panel (Phase 5+) additionally needs a GCP project with the Firestore API enabled and a Native-mode database created (`gcloud services enable firestore.googleapis.com`, `gcloud firestore databases create --type=firestore-native`, then deploy `infra/firestore/firestore.rules` with `firebase deploy --only firestore:rules`), and:

```
# In apps/api/.env:
GOOGLE_CLOUD_PROJECT=your-project-id
```

Without it, `GET /jobs/{id}` still works from Cloud SQL alone — the frontend just falls back to polling instead of a live push.

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
cp .env.example .env.local
npm run dev
```

Visit `http://localhost:3000`. The live trace panel needs the `NEXT_PUBLIC_FIREBASE_*` values too (get them with `firebase apps:sdkconfig WEB <app-id> --project <gcp-project-id>` — not secret, see `lib/firebase.ts`); without them the page falls back to polling `GET /jobs/{id}` instead of subscribing to Firestore directly. **Use `http://localhost:3000`, not `http://127.0.0.1:3000`** — Next.js 16's dev server blocks cross-origin dev-resource requests by default, which silently breaks client-side hydration under `127.0.0.1`.

### Tests / checks

```bash
cd apps/api    && ruff check . && mypy --strict src && pytest -v
cd mcp_server  && ruff check . && mypy --strict src && pytest -v
cd agents      && ruff check . && mypy --strict orchestrator breakdown_agent frame_agent app_build_agent critic_agent iteration_agent shared && pytest -v
cd apps/web    && npm run typecheck && npm run build
cd infra/terraform && terraform fmt -check -recursive && terraform init -backend=false && terraform validate
```

CI (`.github/workflows/ci.yml`) runs the same checks — lint, type-check, test, dependency audit, build, `terraform fmt`/`validate` — on every pull request, one job per package. `.github/workflows/deploy.yml` additionally runs a `terraform plan` against the real project on every push to `main` once `GCP_WORKLOAD_IDENTITY_PROVIDER`/`GCP_SERVICE_ACCOUNT` repo secrets are configured (see `infra/README.md`), and applies to staging/production on the same trigger.

## What's implemented

**Phase 1** — Email/password signup and login (JWT), project creation and listing (ownership checked before existence is ever revealed), script upload (`.txt`/`.pdf`) with real PDF extraction, consistent JSON error envelope, per-instance rate limiting (documented as temporary — becomes Redis-backed in Phase 6), Alembic migrations.

**Phase 2** — Script upload now creates a `GenerationJob` and (if `agents` is configured) triggers a real breakdown run: the script is chunked on scene boundaries, each chunk sent to Gemini with a schema-constrained prompt, validated, retried once on failure, and persisted via `mcp_server`'s tools. A scene that fails validation twice is flagged `needs_review` and the job still completes — one bad scene never blocks the rest. `GET /api/v1/jobs/{id}` and `GET /api/v1/projects/{id}` expose job status and the resulting breakdown.

**Phase 3** — After breakdown completes, the Coordinator fans out one concurrent worker per shot (`asyncio.gather`, real concurrency via `asyncio.to_thread` around the blocking image-generation/captioning calls — not a serial loop). Each worker generates a frame using the project's locked style reference (via `gemini-2.5-flash-image` on Vertex AI — the dedicated Imagen API stayed inaccessible for this project even with billing and the Vertex AI API enabled, see `docs/Phases/PHASE-03-FRAME-GENERATION.md`), captions it via Gemini multimodal, and writes the result through a new `write_frame_record` MCP tool. A shot's frame generation and its captioning are independent failure modes: a persistent generation failure (3 retries, exponential backoff) inserts a placeholder and flags the shot; a captioning-only failure keeps the real image and just falls back on alt-text. `GET /api/v1/jobs/{id}` reports live `{"completed", "total", "failed"}` sub-progress for the `frames` step. Frames are written to a local-dev stand-in for Cloud Storage (`agents/.local_storage/`, swapped for real GCS in Phase 6). **Verified live end to end** — real script → real breakdown → real generated frames → real captions, all persisted through the actual API, no mocks.

**Phase 4** — The App-Build Agent generates the project's previs content itself rather than wrapping a Replit API (there is no such API for a normal account — see `docs/Phases/PHASE-04-APP-BUILD-AND-CRITIC.md` §0 for the full correction): a deterministic data layer read live from scenes/shots/frames, plus a single bounded, schema-validated Gemini call for presentation-only values (`accent_color`, `tone_note`) — never structure or content. The Critic Agent independently re-verifies shot-frame coverage and the customization schema before a job is marked complete, with one bounded retry on failure. The result renders at `apps/web`'s own `/projects/{id}/previs` route (scene navigator, shot cards, CSV export) — no separate deployment per project, since the page always reads live from the same tables. **Verified live end to end**, including through a real browser via Playwright.

**Phase 5** — The Iteration Agent turns a director's free-text request into structured shot-field diffs (Gemini, schema-constrained), using the last 10 `ShotEdit` rows as memory for follow-up requests. An ambiguous request (e.g. "make it darker" with nothing to disambiguate against) gets a `needs_clarification` status and a real clarification question back — never a guessed change. A clear request is applied via a new `write_shot_edit` MCP tool (field-name validated against an allowlist independently of the prompt) and triggers a *scoped* App-Build/Critic pass — since Phase 4's design has no per-shot data file to regenerate, this skips the Gemini customization call entirely and only re-verifies the affected shot(s), making a single-field edit measurably faster than a full initial generation (live-measured: ~20s vs. ~90s). `generation_jobs` is mirrored into Firestore (`job_traces/{job_id}`) on every stage transition; the frontend subscribes directly via the Firebase Web SDK for a real push-based live trace panel (falls back to polling if Firestore isn't configured). Firestore access is a deliberate capability-URL tradeoff — public read scoped to exactly `job_traces/{jobId}` (an unguessable UUID never exposed except to the owning user), writes blocked for every client — see `infra/firestore/firestore.rules`. **Verified live end to end**, including through a real browser: a genuine live-push trace update, a completed edit, and a real ambiguous-request clarification, all against live Gemini — plus a real bug caught and fixed via that browser check (a later job that never reaches App-Build no longer hides an already-live previs link).

**Phase 6** — OpenTelemetry spans wrap every agent invocation (`agent.<name>.run`, with `project_id`/`job_id`/`agent_name`/`status`/`duration_ms`), exported to Grafana Cloud when configured, else created locally with no export (never a hard dependency). The Phase 1 in-process rate limiter is replaced with a Redis-backed distributed one (fixed-window counter via atomic `INCR`, keyed by authenticated user id rather than IP), **live-verified against a real local Redis** — including finding and fixing a genuine redis-py 8.x RESP3 handshake incompatibility along the way. `agent_runner.py` gains a Pub/Sub publish path alongside its existing local subprocess spawn, activated by `PUBSUB_TOPIC`; the orchestrator gained a Cloud Run push-receiver entrypoint (`agents/orchestrator/pubsub_receiver.py`) alongside its existing CLI one. Structured JSON logging replaces plain-text logs. `infra/terraform/` provisions the full production architecture (3 Cloud Run services, Cloud SQL, Memorystore, Pub/Sub, Cloud Storage, Secret Manager, Artifact Registry, least-privilege IAM, optional Grafana Cloud dashboards) — `terraform plan` against the real GCP project produces a clean 72-resource plan, including a real bug (`for_each` over apply-time-unknown values) caught only by `plan`, not `validate`. The security review checklist (`docs/Phases/PHASE-06-SECURITY-REVIEW.md`) includes a live prompt-injection spot check against real Gemini and a captured structured-log line proving no secrets leak. **Not yet deployed** — see `infra/README.md` for why `terraform apply` is a deliberate, separately-triggered step.

## License

MIT — see [`LICENSE`](LICENSE).
