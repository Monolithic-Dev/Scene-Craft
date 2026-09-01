# SceneCraft — API Design

> Read `00-INDEX.md` first for how this fits into the full documentation set. Pairs with `05-DATABASE-DESIGN.md`.

All endpoints are under `/api/v1`, use JWT bearer auth (except signup/login), exchange JSON (except file upload, which is multipart), and are rate-limited per user (token bucket, 60 req/min default).

## 1. Auth

### `POST /api/v1/auth/signup`
**Request:** `{ "email": "priya@studio.com", "password": "at-least-8-chars" }`
**Response `201`:** `{ "id": "uuid", "email": "priya@studio.com" }`
**Errors:** `409 CONFLICT` if the email is already registered.

### `POST /api/v1/auth/login`
**Request:** `{ "email": "...", "password": "..." }`
**Response `200`:** `{ "access_token": "...", "token_type": "bearer" }`
**Errors:** `401 UNAUTHORIZED` on bad credentials.

## 2. Projects

### `POST /api/v1/projects`
**Auth required.** **Request:** `{ "title": "Midnight Ferry", "style_reference": "neo-noir, high contrast" }`
**Response `201`:** the created project object.
**Errors:** `422` on validation failure (empty title, etc).

### `GET /api/v1/projects`
**Auth required.** Returns the current user's projects only — never another user's.
**Response `200`:** `{ "projects": [ {...}, {...} ] }`

### `GET /api/v1/projects/{project_id}`
**Auth required.**
**Response `200`:** the project object.
**Errors:** `404 NOT_FOUND` if it doesn't exist; `403 FORBIDDEN` if it exists but belongs to another user — **never leak existence via a 404-vs-403 timing or message difference; always check ownership before returning either.**

## 3. Scripts

### `POST /api/v1/projects/{project_id}/scripts`
**Auth required.** Multipart file upload (`.txt` or `.pdf`, 10MB / 50-page limit).
**Response `201`:** the created script record (metadata only — not the raw text, to keep the payload light).
**Errors:** `400 VALIDATION_ERROR` (empty file, unsupported format, over size limit), `404` (project doesn't exist), `403` (project belongs to someone else). This endpoint triggers an `initial_generation` job asynchronously — it does not block on agent completion.

## 4. Jobs

### `GET /api/v1/jobs/{job_id}`
**Auth required.**
**Response `200`:** `{ "status": "running", "steps": [ {"agent": "breakdown", "status": "complete", "at": "..."}, ... ] }`
This is the endpoint (or its Firestore-subscription equivalent) the agent-trace UI panel polls or subscribes to.

## 5. Iteration

### `POST /api/v1/projects/{project_id}/iterate`
**Auth required.** **Request:** `{ "request": "make scene 4 night-time" }`
**Response `202`:** `{ "job_id": "uuid" }` — triggers an `iteration` job.

## 6. Export

### `GET /api/v1/projects/{project_id}/export`
**Auth required.** Returns a shot-list CSV or PDF (query param `?format=csv|pdf`).

---

## 7. Error Format (consistent across every endpoint)

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Script content is empty", "field": null } }
```

## 8. Standard Error Codes

| Code | HTTP Status | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Malformed or out-of-bounds input |
| `UNAUTHORIZED` | 401 | Missing/invalid/expired token |
| `FORBIDDEN` | 403 | Valid token, but not allowed to access this resource |
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `CONFLICT` | 409 | Duplicate resource (e.g. email already registered) |
| `RATE_LIMITED` | 429 | Too many requests |
| `AGENT_FAILURE` | 502 | A downstream agent job failed after exhausting retries |

## 9. Validation Rules

- Pydantic schemas validate every request body — reject before touching business logic, not after.
- File uploads: MIME-type allowlist (`text/plain`, `application/pdf`), 10MB max, 50-page max for PDFs.
- Rate limiting enforced at the API Gateway layer via Redis token buckets, before business logic runs — a rate-limited request should never reach the database.

## 10. Authentication Details

- JWT, `HS256`, subject claim = user ID, expiry = 60 minutes by default (configurable).
- Every protected route resolves `Authorization: Bearer <token>` → user via a shared dependency — implement this once, reuse everywhere, never duplicate the decode logic per route.
- On expiry, the client re-authenticates via `/auth/login` — there is no refresh-token flow in this version; document that as a known Should-have for the post-hackathon roadmap if you add one.
- **No password-reset/account-recovery endpoint in this version either** — same reasoning as the refresh-token gap above (see `01-PRD.md` §7). A user who forgets their password has no self-service recovery path until this is built. Flag this explicitly in any judge-facing docs rather than letting it be discovered.
- `jwt_secret_key` must never resolve to its insecure placeholder default outside `environment=development` — the app should refuse to start rather than run with a guessable secret (see `PHASE-01-FOUNDATIONS.md` Common Pitfalls).
