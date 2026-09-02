# SceneCraft — System Design

> Read `00-INDEX.md` first for how this fits into the full documentation set. Pairs with `02-TECH-STACK.md`, `04-AGENT-ARCHITECTURE.md`, and `05-DATABASE-DESIGN.md`.

## 1. High-Level Architecture

```
                         ┌─────────────────────────┐
                         │        Next.js UI        │
                         │  (upload, agent trace,   │
                         │   previs preview, chat)  │
                         └────────────┬─────────────┘
                                      │ HTTPS/JWT
                         ┌────────────▼─────────────┐
                         │   API Gateway (Cloud Run) │
                         │   FastAPI · Auth · Rate   │
                         │        Limiting           │
                         └───┬───────────────────┬───┘
                              │                   │
                 ┌────────────▼───┐     ┌─────────▼────────┐
                 │  Project Service │     │  Agent Orchestr. │
                 │ (Cloud SQL/     │     │  Service (ADK/    │
                 │  Firestore)     │     │  LangGraph)       │
                 └─────────────────┘     └───┬───────┬───────┘
                                              │       │
                          ┌───────────────────┘       └───────────────┐
                          │                                            │
                 ┌────────▼─────────┐                       ┌──────────▼─────────┐
                 │  Script/Shot      │                       │  Storyboard Frame   │
                 │  Breakdown Agent  │                       │  Generation Agent   │
                 │  (Gemini)         │                       │  (Imagen)           │
                 └────────┬──────────┘                       └──────────┬──────────┘
                          │                                             │
                          └───────────────┬─────────────────────────────┘
                                          │
                               ┌──────────▼───────────┐
                               │  App-Build Agent      │
                               │  (Gemini-driven,       │
                               │  constrained codegen)  │
                               └──────────┬────────────┘
                                          │
                               ┌──────────▼───────────┐
                               │  Critic/Evaluator     │
                               │  Agent (QA pass on    │
                               │  generated content)    │
                               └──────────┬────────────┘
                                          │
                            SceneCraft's own /previs route,
                          served from SceneCraft itself on Replit
                                 (replit.app/replit.dev URL)

  Cross-cutting: Pub/Sub (job events) · Cloud Storage (scripts, frames) · BigQuery (history)
  Cloud Monitoring/Logging + Grafana dashboards · Secret Manager · Cloud Run for all services
```

## 2. Component Breakdown

### API Gateway (FastAPI on Cloud Run)
Auth (JWT via Firebase Auth or custom OAuth), request validation (Pydantic), rate limiting (per-user token bucket in Redis), routing to the Project Service and Agent Orchestrator. This is the only component the frontend talks to directly.

### Project Service
CRUD for projects, scripts, and generation history. Cloud SQL holds relational data (users, projects, billing-adjacent data later); Firestore holds fast-changing session/agent-trace state the UI subscribes to — split deliberately so the UI's live-updating panel never waits on a relational query.

### Agent Orchestrator Service
The core of the system. Built on Google's ADK, using a LangGraph-defined state graph for transitions between agents. Publishes job state to Pub/Sub so the UI's agent-trace panel updates in real time without polling.

### Agents
See `04-AGENT-ARCHITECTURE.md` for the full per-agent breakdown (Planner/Coordinator, Script/Shot Breakdown, Storyboard Frame Generation, App-Build, Critic/Evaluator, Iteration).

### MCP Layer
The Agent Orchestrator exposes an internal MCP server wrapping project-data access (read shot list, read/write shot metadata). Agents interact with project state through this well-defined tool protocol rather than direct DB access — this is both a security boundary (agents can't run arbitrary queries) and the literal MCP-server component the hackathon rubric is looking for.

### RAG
The Script/Shot Breakdown Agent runs a lightweight retrieval pass over the script — chunked, embedded, stored in a pgvector-enabled Cloud SQL table or Vertex AI Search — so scripts longer than comfortable context-window size still get consistent, cross-referenced shot extraction (character/location naming stays stable across chunks).

### Memory
Per-project conversation/edit history stored in Firestore, giving the Iteration Agent context on prior edits (e.g. "also revert the lighting change from earlier") without needing a full re-upload each time.

### Async Workers
Frame generation and app-build/deploy are long-running operations. They run as Cloud Run jobs triggered by Pub/Sub messages from the orchestrator, with Celery/Redis managing retry and backoff — never in the synchronous request path.

## 3. Observability

Every agent hop emits an OpenTelemetry span (agent name, tool called, latency, token usage). Traces flow into Cloud Monitoring and are visualized in Grafana dashboards, including a judge-facing "agent activity" panel that doubles as both product UX and observability — a deliberate double-purpose design choice, not two separate features.

## 4. Deployment & CI/CD

GitHub Actions runs lint/type-check/unit+integration tests on every PR, builds Docker images, pushes to Artifact Registry, and deploys to Cloud Run via a Terraform-managed pipeline with separate dev/staging/prod environments. No manual `gcloud deploy` in the critical path.

## 5. Security

- Secret Manager for all keys (Gemini, DB credentials). Replit needs no runtime key from SceneCraft — see `04-AGENT-ARCHITECTURE.md` §4 and `Phases/PHASE-04-APP-BUILD-AND-CRITIC.md` §0/§5.
- IAM least-privilege service accounts per Cloud Run service — the Agent Orchestrator's service account cannot, for example, directly modify Cloud SQL; it goes through the Project Service's API.
- Input validation on every script upload (file-type/size limits) as prompt-injection surface reduction.
- Gemini safety settings configured per the hackathon's guardrail resources.

## 6. Disaster Recovery & Cost Optimization

- Cloud SQL automated backups + point-in-time recovery.
- Cloud Storage lifecycle rules move older generated frames to cheaper storage tiers.
- Cloud Run workers scale to zero during idle periods to control cost — this matters for a hackathon budget as much as a production one.

## 7. Data Flow Walkthrough (concrete example)

1. Director uploads a script via the Next.js UI → API Gateway → Project Service persists the raw script, emits `initial_generation` job → Pub/Sub.
2. Agent Orchestrator picks up the job, invokes the Planner, which sequences: Breakdown → Frames → App-Build → Critic.
3. Breakdown Agent parses the script (with RAG-assisted chunk retrieval for long scripts) into structured scenes/shots via the MCP write-tool.
4. Frame Generation Agent fans out one Imagen call per shot in parallel, writing image URLs back via MCP.
5. App-Build Agent serializes the full project state into a deterministic data file and generates a small, schema-validated styling/customization JSON via a bounded Gemini call; SceneCraft's own `/projects/{id}/previs` route renders both against a fixed, pre-tested app shell.
6. Critic Agent compares the generated data file against the expected shot structure; on mismatch, it triggers one bounded corrective retry through the App-Build Agent.
7. UI's agent-trace panel has been streaming every one of these steps live via Pub/Sub → Firestore-backed subscription the whole time.
8. Director later submits "make scene 4 night-time" → Iteration Agent parses the diff → App-Build Agent redeploys incrementally → Critic re-verifies just the affected shots.
