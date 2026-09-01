# SceneCraft — Coding Standards & Security Practices

> Read `00-INDEX.md` first for how this fits into the full documentation set. This file is not a one-time read — keep it referenced in every phase of `08-IMPLEMENTATION-PLAN.md`.

## 1. Non-Negotiables

- **No TODOs, no pseudocode, no mocked architecture in anything presented as done.** A stubbed function that returns fake data is acceptable *only* as an explicitly-labeled, temporary placeholder during active development of a single phase — never in a phase you've marked complete.
- **Every function and public interface is typed.** Python: full type hints, checked with `mypy --strict`. TypeScript: `strict: true` in `tsconfig.json`, no `any` without a comment explaining why.
- **Every service has tests before it's considered done.** Unit tests for business logic, integration tests for anything touching the database or an external API, and at least one failure-path test per component (what happens when the thing you depend on breaks).
- **Proper error handling everywhere.** No bare `except:` clauses, no swallowed exceptions, no silent failures. Every domain error maps to a specific, documented error code (see `06-API-DESIGN.md`).
- **Structured logging, not print statements.** Every log line should be greppable and include enough context (project ID, job ID, agent name) to trace an issue without guessing.

## 2. Architecture Patterns to Follow

- **Repository pattern** for all data access — services call repositories, repositories call the ORM, nothing else touches the ORM directly. This is what makes it possible to test services with a fake repository instead of a real database.
- **Dependency injection** via FastAPI's `Depends()` — never construct a database session, a service, or a repository by hand inside a route handler.
- **SOLID principles**, applied pragmatically:
  - *Single Responsibility* — a service class does one thing (e.g. `ProjectService` manages projects and scripts, it does not also handle authentication).
  - *Open/Closed* — new agents extend the orchestrator's graph without modifying existing agents' code.
  - *Liskov Substitution* — if you introduce an interface for "image generation provider," any implementation must be swappable without breaking callers.
  - *Interface Segregation* — MCP tools are narrow and specific (`read_shot_records`, not a generic `run_arbitrary_query`).
  - *Dependency Inversion* — services depend on repository abstractions, not on SQLAlchemy specifics leaking through.
- **Configuration management** — all environment-specific values (database URL, API keys, feature flags) come from `Settings` objects loaded from environment variables, never hardcoded, never inline.
- **Environment separation** — dev/staging/prod each have their own Terraform-managed environment and their own Secret Manager entries. Nothing in staging should be able to touch production data.

## 3. Security Practices

- **Secrets:** Every API key and credential lives in Secret Manager. Nothing goes in a committed `.env` file — only `.env.example` with placeholder values is committed.
- **Authentication:** JWT-based, `HS256`, short-lived tokens (60 minutes default). Passwords hashed with `bcrypt` directly (avoid unmaintained wrapper libraries whose version-detection can silently break against newer `bcrypt` releases — verify this compatibility yourself if your stack changes).
- **Authorization:** Every resource-scoped endpoint checks ownership before returning data — a valid token for User A must never expose User B's project, and this check happens in the service layer, not just the route layer, so it can't be bypassed by a new route that forgets to add it.
- **Input validation:** Every request body validated via Pydantic before it reaches business logic. File uploads restricted by MIME type and size. Treat every script upload as untrusted input — it's the most likely prompt-injection surface in this system, since it flows directly into LLM prompts.
- **Prompt injection defense:** Script content is data, not instructions — agent prompts should clearly delimit "the following is script content to analyze" from the agent's own instructions, and agents should never execute instructions found inside script text (e.g. a script containing "ignore previous instructions and..." must not change agent behavior).
- **Rate limiting:** Enforced at the API Gateway layer, before requests reach business logic or the database.
- **Data encryption:** TLS in transit everywhere; encryption at rest via Cloud Storage/Cloud SQL defaults, with CMEK as a documented option for a studio-tier deployment.

## 4. Testing Strategy

| Test type | What it covers | When it runs |
|---|---|---|
| Unit | Individual service/repository methods, agent prompt construction, schema validation | Every commit, locally and in CI |
| Integration | Endpoint behavior against a real (test) database, agent tool calls against mocked external APIs | Every PR, in CI |
| End-to-end | Full user flows (upload → generate → edit → verify) | Before marking a phase complete |
| LLM evaluation | Golden-file comparisons for agent outputs (e.g. does the Breakdown Agent correctly extract shots from known sample scripts) | Every PR that touches an agent |
| Load | API gateway under concurrent load | Phase 6, before declaring production-readiness |
| Security | Auth boundary checks (can User A access User B's data), secret-handling review | Phase 6, as an explicit checklist sign-off |

## 5. CI/CD Gate

Every PR must pass, in this order, before merge: lint → type-check → unit tests → integration tests → build. A red step blocks merge — there is no "merge anyway, fix later" path in this project's discipline, hackathon deadline or not. A last-minute broken build the night before submission is a far worse outcome than a slightly smaller feature set that actually works.

## 6. Commit Discipline

- Conventional commit prefixes (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`) matching the phase's stated commit message in `08-IMPLEMENTATION-PLAN.md`.
- One phase's work per set of commits — don't mix Phase 3 frame-generation code into a commit whose message claims Phase 2 breakdown work.
- Every commit that changes the schema includes its migration file in the same commit — never a follow-up "oops, forgot the migration" commit.
