# SceneCraft — Phase 1 Build Spec: Foundations

> Read `00-INDEX.md`, `07-FOLDER-STRUCTURE.md`, `05-DATABASE-DESIGN.md`, `06-API-DESIGN.md`, and `09-CODING-STANDARDS.md` before starting this phase. This file is the complete, implementation-ready spec for Phase 1 — everything Claude Code needs to build it in one focused session, without inventing decisions that should have been made here instead.

## Objective

Stand up the full control-plane skeleton: auth, project CRUD, and script upload (raw storage only — no AI processing yet). At the end of this phase, a user can sign up, log in, create a project, and upload a script, and every layer of the architecture (API → service → repository → DB) exists in real, tested form.

## Scope

**In scope:** repo scaffolding per `07-FOLDER-STRUCTURE.md`, auth (signup/login/JWT), project CRUD, script upload with real PDF text extraction, Alembic migrations, CI pipeline, minimal frontend (login page + dashboard with upload).
**Out of scope (later phases):** anything agent-related, anything Replit-related, observability instrumentation beyond basic logging, deployment infra.

## Prerequisites

- Python 3.12, Node 20, Postgres available locally (or SQLite for fast local dev — `DATABASE_URL` should support both transparently)
- A GCP project is **not** required yet — this phase runs entirely locally

---

## Build Order (follow this sequence — later steps depend on earlier ones)

### Step 1 — Repo scaffolding
Create the full folder tree from `07-FOLDER-STRUCTURE.md`. For Phase 1, only `apps/api`, `apps/web`, and `.github/workflows` need real content; other folders (`agents/`, `mcp_server/`, `infra/`) can exist as empty placeholders with a `.gitkeep`.

### Step 2 — Backend core layer (`apps/api/src/core/`)
Build, in this order:
1. `config.py` — a `Settings` class (Pydantic `BaseSettings`) loading from environment: `environment`, `database_url`, `jwt_secret_key`, `jwt_algorithm`, `access_token_expire_minutes`, `max_script_upload_bytes`, `max_script_pages`, `rate_limit_requests_per_minute`, `allowed_origins`. Provide a cached `get_settings()` accessor.
2. `database.py` — SQLAlchemy engine + `SessionLocal` + a `Base` declarative class + a `get_db()` FastAPI dependency yielding a request-scoped session.
3. `security.py` — password hashing and JWT. **Use `bcrypt` directly, not `passlib`** — passlib's bcrypt-backend version-detection is unmaintained and breaks against modern `bcrypt` releases (this is a real, previously-hit issue, not a hypothetical). Reject passwords over 72 bytes up front (bcrypt's hard limit) rather than letting them silently truncate. Provide `hash_password`, `verify_password`, `create_access_token(subject) -> str`, and `decode_access_token(token) -> str` (raising a `TokenError` on failure).
4. `exceptions.py` — a `DomainError` base with `code` and `status_code`, and concrete subclasses: `ValidationError` (400), `UnauthorizedError` (401), `ForbiddenError` (403), `NotFoundError` (404), `ConflictError` (409).

### Step 3 — Models (`apps/api/src/models/`)
Per `05-DATABASE-DESIGN.md`, build `User`, `Project`, and `Script` as typed SQLAlchemy 2.0 models (`Mapped[...]` style). Use UUID string primary keys generated client-side (`default=lambda: str(uuid.uuid4())`), not auto-increment integers — this matters later when projects/scripts might sync across services. Wire up the relationships (`User.projects`, `Project.scripts`) with `cascade="all, delete-orphan"` where a parent deletion should cascade. Use `TYPE_CHECKING` imports for cross-model string type hints so static analysis (`mypy`, `ruff`) resolves them cleanly instead of flagging undefined names.

### Step 4 — Schemas (`apps/api/src/schemas/`)
Pydantic v2 schemas: `auth.py` (`SignupRequest`, `LoginRequest`, `TokenResponse`, `UserResponse`), `project.py` (`ProjectCreateRequest`, `ProjectResponse`, `ProjectListResponse`), `script.py` (`ScriptResponse`), `error.py` (`ErrorDetail`, `ErrorResponse` matching the envelope in `06-API-DESIGN.md`). Cap `SignupRequest.password` at `max_length=72` to match bcrypt's limit, `min_length=8` for basic strength.

### Step 5 — Repositories (`apps/api/src/repositories/`)
One per model: `UserRepository` (`get_by_email`, `get_by_id`, `create`), `ProjectRepository` (`create`, `get_by_id`, `list_for_owner`), `ScriptRepository` (`create`). Repositories are the *only* layer that imports the ORM session directly — services must never construct a query themselves.

### Step 6 — Services (`apps/api/src/services/`)
`AuthService` — `signup` (raises `ConflictError` on duplicate email), `authenticate` (raises `UnauthorizedError` on bad credentials), `issue_token`. `ProjectService` — `create_project`, `list_projects`, `get_owned_project` (raises `NotFoundError` if missing, `ForbiddenError` if owned by someone else — **check existence before ownership, always return the more specific error**), `upload_script` (validates format, size, and non-empty content before persisting; raises `ValidationError` with a clear message for each failure mode).

### Step 7 — API dependencies (`apps/api/src/api/deps.py`)
A `get_current_user` dependency: parses `Authorization: Bearer <token>`, decodes it, loads the user, raises `UnauthorizedError` for any failure mode (missing header, malformed header, invalid/expired token, user no longer exists). Export `DbSession` and `CurrentUser` as `Annotated` type aliases so route signatures stay clean.

### Step 8 — Routes (`apps/api/src/api/v1/`)
`auth.py` (signup, login), `projects.py` (create, list, get-by-id), `scripts.py` (upload — multipart, extracts text from `.txt` or `.pdf` using `pypdf`, validates via `ProjectService.upload_script`). Aggregate into `router.py` under prefix `/api/v1`.

**PDF extraction detail:** detect PDF by content-type or `.pdf` filename suffix; wrap `PdfReader` construction in a try/except for `PdfReadError`, converting it to a `ValidationError` ("file may be corrupt") rather than letting a raw parser exception become an unhandled 500.

### Step 9 — App entrypoint (`apps/api/src/main.py`)
FastAPI app with: CORS middleware (origins from settings), a simple in-process rate-limiting middleware (per-client-IP sliding window — document explicitly that this becomes a Redis-backed limiter shared across instances in Phase 6, not a permanent design), a global exception handler mapping `DomainError` → the JSON error envelope, a `/healthz` endpoint, and the mounted `api_router`.

### Step 10 — Migrations
Initialize Alembic (`alembic.ini` + `alembic/env.py` wired to `Settings.database_url` and importing all models so `Base.metadata` is fully populated). Generate the initial migration with `alembic revision --autogenerate -m "initial schema: users, projects, scripts"` and **review the generated file by hand** before treating it as final — autogenerate is a draft. Apply it and confirm the tables exist.

### Step 11 — Tests (`apps/api/tests/`)
See the full test list below. Use an in-memory SQLite engine with `StaticPool` for test isolation (each test gets a clean schema via `Base.metadata.create_all`), and override the `get_db` dependency via `app.dependency_overrides`.

### Step 12 — Frontend skeleton (`apps/web/`)
Next.js 14 App Router, TypeScript strict, Tailwind. A typed `lib/api.ts` client wrapping `fetch` with JWT header injection and a typed `ApiError`. `app/page.tsx` — login/signup form. `app/dashboard/page.tsx` — project creation + list + script upload form, redirecting to `/` if no token is present.

### Step 13 — CI
GitHub Actions workflow with two jobs (`api`, `web`), each running lint → typecheck → test → build in that order, failing fast on the first red step.

---

## Exact API Contract for This Phase

| Method | Path | Auth | Success | Key errors |
|---|---|---|---|---|
| POST | `/api/v1/auth/signup` | No | 201, user object | 409 CONFLICT |
| POST | `/api/v1/auth/login` | No | 200, `{access_token, token_type}` | 401 UNAUTHORIZED |
| POST | `/api/v1/projects` | Yes | 201, project object | 422 (validation) |
| GET | `/api/v1/projects` | Yes | 200, `{projects: [...]}` | — |
| GET | `/api/v1/projects/{id}` | Yes | 200, project object | 404, 403 |
| POST | `/api/v1/projects/{id}/scripts` | Yes | 201, script metadata | 400, 404, 403 |

Full detail (payload shapes, error codes) is in `06-API-DESIGN.md` — this table is the Phase 1 subset.

---

## Required Tests (write all of these — this is the actual acceptance bar, not a suggestion)

**Auth**
- `test_signup_creates_user` — 201, response contains `id` and `email`, never the password/hash
- `test_signup_duplicate_email_is_rejected` — second signup with the same email returns 409 `CONFLICT`
- `test_login_success_returns_token` — 200, non-empty `access_token`, `token_type == "bearer"`
- `test_login_wrong_password_is_unauthorized` — 401 `UNAUTHORIZED`
- `test_protected_route_without_token_is_unauthorized` — any authenticated route without a header returns 401

**Projects**
- `test_create_and_list_projects` — create then list, list contains exactly the created project
- `test_get_project_not_found` — 404 `NOT_FOUND` for a nonexistent ID
- `test_cannot_access_another_users_project` — User B requesting User A's project gets 403 `FORBIDDEN`, not 404 (verifies the existence-then-ownership check order)
- `test_create_project_requires_title` — empty title returns 422

**Scripts**
- `test_upload_text_script` — 201, `source_format == "text"`, correct `project_id`
- `test_upload_empty_script_is_rejected` — whitespace-only content returns 400 `VALIDATION_ERROR`
- `test_upload_to_nonexistent_project_is_not_found` — 404
- `test_upload_requires_auth` — 401 without a token

If you add functionality beyond this list, add tests for it too — this list is the floor, not the ceiling.

---

## Definition of Done (check every box before calling Phase 1 complete)

- [ ] `ruff check` passes with zero errors
- [ ] `mypy --strict` passes with zero errors on the backend
- [ ] `tsc --noEmit` passes with zero errors on the frontend
- [ ] All 12 tests above pass
- [ ] `alembic upgrade head` runs cleanly against a fresh database and creates all three tables plus correct indexes
- [ ] `npm run build` succeeds for the frontend
- [ ] A user can, through the actual UI (not just the API), sign up, log in, create a project, and upload a script, and see it reflected in the list
- [ ] No secrets are hardcoded anywhere — `.env.example` exists, `.env` is gitignored
- [ ] CI is green on a clean clone with no local state

## Common Pitfalls (learned the hard way — don't rediscover these)

1. **`passlib` + modern `bcrypt`** — passlib's version-detection shim throws on `bcrypt>=4.1`. Use `bcrypt` directly from the start; don't add passlib as a dependency at all.
2. **Password length vs. bcrypt's 72-byte limit** — validate this at the schema layer (`max_length=72`), not just inside the hashing function, so the error surfaces as a clean 422 instead of a hashing exception.
3. **String forward-references in SQLAlchemy `relationship()`** — `Mapped["Project"]` needs a `TYPE_CHECKING`-guarded import of `Project` in the same file, or `ruff`/`mypy` will flag it as an undefined name even though it works fine at runtime.
4. **404 vs. 403 ordering** — always check "does this resource exist" before "does the caller own it." Reversing this order either leaks existence information or produces confusing error messages.
5. **Rate-limiting state in a multi-instance deployment** — the in-process limiter built in this phase is correct for local dev and a single Cloud Run instance only. Don't forget to swap it for the Redis-backed version in Phase 6 — flag it clearly in code comments now so it isn't forgotten later.

## Commit Message
`feat(phase-1): project scaffolding, auth, and script upload`
