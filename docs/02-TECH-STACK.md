# SceneCraft — Tech Stack

> Read `00-INDEX.md` first for how this fits into the full documentation set.

Every choice below is justified — nothing is included "because it's popular." If you swap something out, keep the same justification discipline.

## Frontend

| Technology | Version | Why |
|---|---|---|
| Next.js | 14.x (App Router) | Server components reduce client bundle size; App Router is the current idiomatic pattern; Vercel/Google Cloud both deploy it cleanly via Cloud Run's container support |
| TypeScript | 5.x | Non-negotiable for a "production-grade" submission — catches an entire class of runtime errors before a judge ever sees them |
| Tailwind CSS | 3.x | Fast, consistent styling without a design-system detour the hackathon timeline can't afford |
| shadcn/ui | latest | Accessible, unstyled-by-default component primitives — avoids the generic-template look while staying fast to build with |
| React Query | 5.x | Handles the async agent-job polling/streaming state (job status, agent trace) far more robustly than hand-rolled `useEffect` chains |

## Backend

| Technology | Version | Why |
|---|---|---|
| FastAPI | 0.115.x | Async-native, typed, auto-generates OpenAPI docs — directly supports the judging criterion on technological implementation |
| Python | 3.12 | Current stable; needed for the newest `typing` ergonomics used throughout the codebase |
| uv | latest | Fast, reproducible dependency management — signals real engineering hygiene over `pip freeze` chaos |
| Pydantic | v2 | Request/response validation and settings management in one library, used consistently end-to-end |
| SQLAlchemy | 2.0 (typed ORM) | The 2.0 typed-mapping style catches schema mistakes at the type-checker level, not at runtime |
| Alembic | latest | Every schema change is a reversible, reviewable migration file — never manual `ALTER TABLE` in prod |
| Postgres | 15+ (Cloud SQL) | Relational integrity for users/projects/scripts; pgvector extension available if embedding storage needs to move in-database later |
| Redis (Cloud Memorystore) | 7.x | Rate-limiting token buckets and Celery broker |
| Celery | latest | Retry/backoff semantics for long-running agent jobs are well-trodden ground here — don't reinvent it |
| Docker | latest | Consistent build artifact from a laptop to Cloud Run |

## AI / Agents

| Technology | Why |
|---|---|
| Gemini 2.x (multimodal) | Long-context script parsing, video/image understanding, structured JSON extraction — all from one model family |
| Vertex AI Agent Builder / ADK | The hackathon's own recommended agent-hosting path; using it directly (rather than a bespoke wrapper) is exactly what "native GCP" judging rewards |
| LangGraph | Explicit state-graph orchestration across agents — makes the multi-agent structure visible and debuggable, not an implicit prompt chain |
| Imagen | Storyboard concept-frame generation |
| Gemini TTS | Optional multi-speaker scene read-aloud (Should-have feature) |

## Partner Integration

| Technology | Why |
|---|---|
| Replit Agent API | The literal mechanism that generates and deploys the previs web app — this is the deep, structurally-necessary partner integration the judging criteria explicitly reward over a superficial API call |

## Observability

| Technology | Why |
|---|---|
| OpenTelemetry | Vendor-neutral instrumentation standard — traces every agent hop (tool called, latency, token usage) |
| Grafana | Dashboards + alerting on top of the OTel data; also doubles as the judge-facing "agent activity" visualization |

## Deployment & Infrastructure

| Technology | Why |
|---|---|
| Cloud Run | Serverless containers, scale-to-zero for cost control, native fit for both the API and the async agent workers |
| GitHub Actions | CI: lint, type-check, test, build — gating every merge |
| Artifact Registry | Docker image storage, wired directly into the Cloud Run deploy step |
| Terraform | Infrastructure-as-code for Cloud Run services, Cloud SQL, Pub/Sub topics, IAM — reproducible environments, not console click-ops |
| Secret Manager | Every API key and credential — zero secrets in code or env files |
| Cloud Storage | Script files, generated storyboard frames |
| Pub/Sub | Async job events between the API, the agent orchestrator, and the workers |
| BigQuery | Analytical/history data (generation history, KPIs) at scale |
| Firestore | Low-latency project/session state the frontend subscribes to for live agent-trace updates |

## Explicitly not used (and why)

- **Kubernetes/GKE** — Cloud Run gives the same container-based deployment model with far less operational overhead for a project of this scope; reach for GKE only if you outgrow Cloud Run's concurrency/model limits.
- **A custom low-code/app-generation layer** — this is precisely what Replit's Agent API already does well; building your own would dilute the partner integration instead of deepening it.
- **A second LLM provider alongside Gemini** — the hackathon explicitly rewards Gemini/Google Cloud depth; splitting model usage adds complexity without adding judging credit.
