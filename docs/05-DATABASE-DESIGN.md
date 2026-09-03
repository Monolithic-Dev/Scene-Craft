# SceneCraft — Database Design

> Read `00-INDEX.md` first for how this fits into the full documentation set. Pairs with `06-API-DESIGN.md`.

## 1. Storage Split (why two databases)

- **Cloud SQL (Postgres)** — relational, durable data with real integrity constraints: users, projects, scripts, scenes, shots, edits, job history. This is the "system of record."
- **Firestore** — fast-changing, low-latency session/agent-trace state the UI subscribes to live (job step events, agent reasoning log). This data is disposable/regenerable; it does not need relational integrity.

Don't collapse these into one store — the access patterns (transactional writes vs. high-frequency live-subscription reads) are different enough that a single database would compromise one side or the other.

## 2. ER Diagram (textual)

```
users ──< projects ──< scripts ──< scenes ──< shots ──< shot_frames
   │            │                                 │
   │            └──< generation_jobs               └──< shot_edits
   └──< sessions
```

## 3. Core Tables

### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| email | varchar(255) | unique, indexed |
| password_hash | varchar(255) | bcrypt, never store plaintext |
| created_at | timestamptz | |

### `projects`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| owner_id | UUID (FK → users.id) | indexed |
| title | varchar(255) | |
| style_reference | text | nullable — the locked Imagen style prompt for the project |
| created_at / updated_at | timestamptz | |

### `scripts`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| project_id | UUID (FK → projects.id) | indexed |
| raw_text | text | |
| source_format | varchar(20) | `text` \| `pdf` |
| uploaded_at | timestamptz | |

### `scenes`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| script_id | UUID (FK → scripts.id) | indexed |
| scene_number | integer | |
| heading | varchar(255) | e.g. "INT. FERRY - NIGHT" |
| time_of_day | varchar(50) | |
| needs_review | boolean, default false | set by the Breakdown Agent when a scene fails schema validation twice (see `PHASE-02-BREAKDOWN-AGENT.md` §3) — the scene is still persisted with whatever partial data is available, flagged rather than dropped |

### `shots`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| scene_id | UUID (FK → scenes.id) | indexed |
| shot_number | integer | |
| characters | jsonb | denormalized display list — see note below |
| location | varchar(255) | |
| time_of_day | varchar(50) | added in Phase 2 — the Breakdown Agent's `ShotOutput` schema resolves this per shot (a shot can imply a different time than its scene heading's nominal value); "UNSPECIFIED" when genuinely unknown, never guessed |
| action_summary | text | |
| suggested_camera | varchar(255) | |
| dialogue_snippet | text, nullable | added in Phase 2 — matches `ShotOutput.dialogue_snippet` from `04-AGENT-ARCHITECTURE.md` §2, omitted from the original table draft |
| needs_review | boolean, default false | added in Phase 3 — set by the Frame Agent when a shot's frame generation exhausts its retries (placeholder frame inserted) or its captioning call fails (fallback alt-text used); reuses `scenes.needs_review`'s existing convention rather than adding a second, frame-specific flag — see `PHASE-03-FRAME-GENERATION.md` §5 |

### `shot_frames`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| shot_id | UUID (FK → shots.id) | indexed |
| image_url | text | Cloud Storage signed URL |
| alt_text | text | accessibility requirement, auto-generated |
| generated_at | timestamptz | |

### `shot_edits`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| shot_id | UUID (FK → shots.id) | indexed |
| field | varchar(100) | which field changed |
| old_value / new_value | text | |
| requested_by | UUID (FK → users.id) | |
| created_at | timestamptz | |

### `generation_jobs`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| project_id | UUID (FK → projects.id) | indexed |
| job_type | enum | `initial_generation` \| `iteration` |
| status | enum | `queued` \| `running` \| `complete` \| `failed_needs_review` \| `needs_clarification` (added Phase 5 — the Iteration Agent's ambiguous-request short circuit, distinct from `failed_needs_review`: an expected, recoverable stop, not an error) |
| deployed_app_url | text | nullable until some job's App-Build stage has succeeded; reflects the most recent *successful* deployment, not just the most recent job (Phase 5: a later job stuck on `needs_clarification` must not make an already-live previs disappear) |
| error_detail | text | nullable; also carries the Iteration Agent's clarification question when `status == needs_clarification` |
| current_stage | varchar(50), nullable | which stage of the active plan is running — `breakdown`\|`frames`\|`app_build`\|`critic` for `initial_generation`, `iteration`\|`app_build`\|`critic` for `iteration` (Phase 5); lets `GET /jobs/{id}` derive per-stage step status without a separate step-tracking table. Phase 5 additionally mirrors this into Firestore (`job_traces/{job_id}`) for the live trace panel — see `PHASE-05-ITERATION-AND-TRACE-UI.md` §2. |
| frames_total / frames_completed / frames_failed | integer, nullable | added in Phase 3 — sub-progress for the `frames` stage's fan-out, reported by the Frame Agent as shots complete; see `PHASE-03-FRAME-GENERATION.md` §6 |
| created_at / completed_at | timestamptz | |

## 4. Indexes

- `shots(scene_id)`, `scenes(script_id)`, `shot_frames(shot_id)` — standard FK indexes for join performance.
- `generation_jobs(project_id, status)` — composite index for the "current job status" dashboard query, which is hit on every page load.
- `projects(owner_id)` — for the user's project-list view.

## 5. Normalization Note

Schema is normalized to 3NF, with one deliberate exception: `characters` is stored as JSONB on `shots` rather than a separate join table. This is a denormalized *display* list, not something queried by character in this version. Document this tradeoff explicitly in your own repo — if character-level analytics ever becomes a requirement (e.g. "how many shots does this character appear in across the project"), that's the trigger to normalize it into a real `characters` + `shot_characters` join table.

## 6. Migration Strategy

- Every schema change ships as an Alembic migration file — reversible (`upgrade`/`downgrade` both implemented), never a manual `ALTER TABLE` run by hand against a live database.
- Migrations run in CI against a throwaway Postgres instance before merge — a migration that doesn't apply cleanly should fail the build, not fail in production.
- Migration file naming: `{revision}_{short_description}.py`, generated via `alembic revision --autogenerate -m "description"` and then hand-reviewed — autogenerate is a draft, not a merge-ready diff.
