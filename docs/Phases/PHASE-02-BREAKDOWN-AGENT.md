# SceneCraft — Phase 2 Build Spec: Script/Shot Breakdown Agent

> Read `PHASE-01-FOUNDATIONS.md` (must be complete and passing its Definition of Done first), `04-AGENT-ARCHITECTURE.md` §2, `10-DIAGRAMS.md` §2–3, and `09-CODING-STANDARDS.md` before starting.

## Objective

Turn the raw script text already stored by Phase 1 into structured, persisted scenes and shots — automatically, the moment a script is uploaded — with a real job-status lifecycle the frontend can watch.

## Scope

**In scope:** the Breakdown Agent itself, the `scenes`/`shots` tables and migration, the `generation_jobs` table and lifecycle, the internal MCP server's first two tools, RAG-assisted chunking for long scripts, job-status polling endpoint.
**Out of scope:** frame generation, app building, anything Replit-related, the live Pub/Sub trace UI (Phase 2 can poll `GET /jobs/{id}`; the live-streaming version arrives in Phase 5).

---

## 1. New Data Model

Add to `apps/api/src/models/`: `Scene`, `Shot`, `GenerationJob` per the exact schema in `05-DATABASE-DESIGN.md` §3. Generate and review a new Alembic migration (`alembic revision --autogenerate -m "add scenes, shots, generation_jobs"`). `GenerationJob.status` is a Python `enum.Enum` (`QUEUED`, `RUNNING`, `COMPLETE`, `FAILED_NEEDS_REVIEW`) mapped via SQLAlchemy's `Enum` type — not a bare string column, so an invalid status is a type error, not a silent data-quality bug.

## 2. MCP Server — First Two Tools

Build `mcp_server/` as its own package (per `07-FOLDER-STRUCTURE.md`) exposing:

- **`write_shot_records(script_id, scenes: list[SceneInput]) -> WriteResult`** — persists the Breakdown Agent's structured output. Validates the payload against the same Pydantic schema the agent is instructed to output, rejecting (not silently coercing) anything that doesn't match.
- **`get_project_state(project_id) -> ProjectStateSnapshot`** — read-only, returns everything an agent needs (script text, existing scenes/shots, style reference) in one call, so agents never make ad hoc direct queries.

Agents talk to these tools over MCP, not by importing the repository layer directly — this is the boundary described in `03-SYSTEM-DESIGN.md` §2 and it's worth enforcing for real here, not just conceptually: the agent process should have no direct SQLAlchemy session of its own.

## 3. The Breakdown Agent (`agents/breakdown_agent/`)

**Structure:**
```
agents/breakdown_agent/
├── agent.py          # entrypoint: run(script_id) -> BreakdownResult
├── chunking.py        # script chunking + embedding for RAG
├── prompts.py          # the prompt template(s), versioned
└── schema.py           # the strict output schema (shared with mcp_server's validator)
```

**Output schema (`schema.py`)** — this is the contract every prompt must produce and every validator must check:
```python
class ShotOutput(BaseModel):
    shot_number: int
    characters: list[str]
    location: str
    time_of_day: str
    action_summary: str
    suggested_camera: str
    dialogue_snippet: str | None = None

class SceneOutput(BaseModel):
    scene_number: int
    heading: str
    time_of_day: str
    shots: list[ShotOutput]

class BreakdownOutput(BaseModel):
    scenes: list[SceneOutput]
```

**Chunking strategy (`chunking.py`):** split the script on scene-heading boundaries (`INT.`/`EXT.` lines) rather than a fixed token count — a scene should never be split mid-scene across two chunks. For scripts long enough to exceed a comfortable single-call context window, embed each chunk and store it (pgvector column on a `script_chunks` table, or Vertex AI Search) so later chunks can retrieve earlier chunks' extracted character/location names and stay consistent (e.g. don't extract "DET. RAMOS" in chunk 1 and "Detective Ramos" in chunk 3 as if they were different people).

**Prompt (`prompts.py`)** — the real, full instruction, not just the summary from `04-AGENT-ARCHITECTURE.md`:
```
You are a script supervisor's assistant. You will be given a chunk of a
screenplay, plus a list of characters and locations already identified in
earlier chunks (for consistency — reuse these names exactly if the same
entity appears again).

Extract every distinct shot implied by scene headings and action lines.
A new scene heading (INT./EXT. ... - DAY/NIGHT) always starts a new scene.
Within a scene, infer shot boundaries from clear action/camera cues in the
action lines — do not invent shots that aren't implied by the text.

Output strict JSON matching the BreakdownOutput schema. Do not include
markdown formatting, commentary, or any text outside the JSON object.
Do not invent characters, locations, or dialogue not present in the text.
If a field is genuinely unknown (e.g. no explicit time-of-day given),
use "UNSPECIFIED" rather than guessing.

Known characters so far: {known_characters}
Known locations so far: {known_locations}

Script chunk:
{chunk_text}
```

**`agent.py` flow:**
1. Call `get_project_state` (MCP) for the script text and any existing partial breakdown (supports resuming a failed job).
2. Chunk the script (`chunking.py`).
3. For each chunk, in order: call Gemini with the prompt above, parse the response against `BreakdownOutput`.
4. **On schema validation failure:** re-prompt once with the validation error appended to the prompt ("Your previous output failed validation: {error}. Fix and resend valid JSON only."). On a second failure, mark that scene `needs_review` (store it with a flag rather than dropping it) and continue with the rest of the script — one bad scene must not fail the whole job.
5. Call `write_shot_records` (MCP) to persist.
6. Update `GenerationJob.status` at each stage transition.

## 4. Orchestrator Wiring

Extend the Agent Orchestrator (introduced conceptually in `03-SYSTEM-DESIGN.md`, built for real starting now) with the Coordinator's first real responsibility: on script upload, create a `GenerationJob(job_type=INITIAL_GENERATION, status=QUEUED)`, publish it to Pub/Sub, and have a worker pick it up and invoke the Breakdown Agent. For Phase 2, the plan is just `[breakdown]` — later phases extend it to `[breakdown, frames, app_build, critic]`.

## 5. New/Changed API Surface

| Method | Path | Behavior change from Phase 1 |
|---|---|---|
| POST | `/api/v1/projects/{id}/scripts` | Now also creates a `GenerationJob` and enqueues it, in addition to Phase 1's storage behavior |
| GET | `/api/v1/jobs/{job_id}` | **New.** Returns `{status, steps: [...]}`. For Phase 2, `steps` has one entry (`breakdown`); later phases add more as each agent is built |
| GET | `/api/v1/projects/{id}` | Response now includes the scene/shot breakdown once the job completes |

## 6. Required Tests

**Golden-file tests** — the core correctness bar for this phase:
- `test_breakdown_extracts_shots_from_sample_script_1` — a short (1–2 scene) hand-written sample script with a known-correct expected output; assert the agent's output matches on scene count, shot count, and key fields (characters, locations)
- `test_breakdown_extracts_shots_from_sample_script_2` — a longer, multi-scene sample exercising the chunking path
- `test_breakdown_handles_missing_time_of_day` — a scene heading without explicit DAY/NIGHT resolves to `"UNSPECIFIED"`, not a guess

**Failure-path tests:**
- `test_breakdown_reprompts_on_invalid_json` — mock the LLM call to return invalid JSON once, then valid JSON; assert the agent retries and succeeds
- `test_breakdown_flags_scene_after_second_failure` — mock two consecutive invalid responses; assert the scene is marked `needs_review` and the job still completes rather than failing entirely

**Integration tests:**
- `test_job_status_transitions_correctly` — QUEUED → RUNNING → COMPLETE across a real (mocked-LLM) run
- `test_get_job_endpoint_returns_current_status` — API-level test of `GET /jobs/{id}`
- `test_upload_triggers_breakdown_job` — uploading a script results in a job being created and, once processed, scenes/shots appearing on the project

**MCP tool tests:**
- `test_write_shot_records_rejects_invalid_payload` — a payload that doesn't match `BreakdownOutput` is rejected, not silently coerced
- `test_get_project_state_returns_expected_shape` — snapshot shape test

## Definition of Done

- [ ] All Phase 1 checks still pass (nothing regressed)
- [ ] All tests above pass, including both golden-file scripts
- [ ] A real script upload (through the actual API, mocked LLM in CI / real Gemini call in local manual testing) produces a correct, retrievable breakdown
- [ ] `GenerationJob.status` transitions are visible via `GET /jobs/{id}` throughout a run
- [ ] The MCP server is a genuinely separate process/package boundary — agents do not import `apps/api/src/repositories/` directly
- [ ] `ruff` + `mypy --strict` clean on `agents/` and `mcp_server/` in addition to `apps/api`

## Common Pitfalls

1. **Chunking on a fixed token count instead of scene boundaries** — this splits a scene's shots across two LLM calls with no shared context, producing duplicate or contradictory shot numbers. Always chunk on `INT./EXT.` boundaries first, and only sub-split a single scene if it's pathologically long.
2. **Treating a JSON parse failure and a schema validation failure the same way** — a parse failure means the model didn't even produce JSON; a schema failure means it produced JSON that's structurally wrong. Both should trigger the re-prompt path, but log them distinctly — they usually indicate different prompt problems.
3. **Forgetting the "known characters so far" context on later chunks** — without it, character name consistency across a multi-chunk script degrades noticeably; this is the single highest-leverage fix for breakdown quality on real scripts.
4. **Letting one bad scene fail the entire job** — the `needs_review` flag-and-continue behavior is not optional polish, it's the difference between a usable partial result and a demo that produces nothing when one scene has an unusual format.

## Commit Message
`feat(phase-2): script/shot breakdown agent`
