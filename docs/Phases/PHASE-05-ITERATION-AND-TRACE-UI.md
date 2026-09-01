# SceneCraft — Phase 5 Build Spec: Iteration Agent & Live Agent-Trace UI

> Read `PHASE-04-APP-BUILD-AND-CRITIC.md` (must be complete and passing first), `04-AGENT-ARCHITECTURE.md` §6, `10-DIAGRAMS.md` §4 and §6, and `09-CODING-STANDARDS.md` before starting.

## Objective

Close the loop that makes SceneCraft a *tool*, not a one-shot generator: let a director type a plain-English change and watch it apply, redeploy, and re-verify — with every agent step visible live in the UI, not discovered after the fact by refreshing a page.

## Scope

**In scope:** the Iteration Agent, the natural-language edit endpoint, Firestore-backed live job-trace state, the frontend's real-time agent-trace panel (replacing Phase 2–4's polling), edit history/memory.
**Out of scope:** anything related to observability instrumentation for Grafana (Phase 6 — this phase's "live trace" is a product feature, Phase 6's tracing is an ops concern; they're related but distinct, don't conflate them).

---

## 1. Data Model Addition

`ShotEdit` per `05-DATABASE-DESIGN.md` §3 (`shot_id`, `field`, `old_value`, `new_value`, `requested_by`, `created_at`). New Alembic migration. This table is both the audit trail and the Iteration Agent's memory source — don't build a separate "memory" store when this table already captures what's needed.

## 2. Firestore Schema for Live Trace

Introduce a `job_traces/{job_id}` Firestore document (or subcollection of step events) that the Coordinator writes to at every stage transition, and that the frontend subscribes to directly (Firestore's client SDK supports live listeners — use this instead of client-side polling). Shape:
```json
{
  "job_id": "uuid",
  "status": "running",
  "steps": [
    {"agent": "iteration", "status": "complete", "detail": "Applied 1 change", "at": "..."},
    {"agent": "app_build", "status": "running", "detail": null, "at": "..."}
  ]
}
```
This is the same shape `GET /jobs/{id}` already returns from Phase 2 (Cloud SQL-backed) — Phase 5's change is *where the frontend gets it from*: a live Firestore subscription instead of a poll loop. Keep the Cloud SQL `generation_jobs` table as the durable system of record; Firestore is the fast, ephemeral, live-updating mirror. If they ever disagree, Cloud SQL wins — Firestore is a cache for the UI, not the source of truth.

## 3. The Iteration Agent (`agents/iteration_agent/`)

**Structure:**
```
agents/iteration_agent/
├── agent.py       # entrypoint: run(project_id, user_request: str) -> IterationResult
└── prompts.py       # the diff-extraction prompt
```

**Output schema:**
```python
class ShotDiff(BaseModel):
    shot_id: str
    field: str            # must be a real Shot field name
    new_value: str

class IterationOutput(BaseModel):
    diffs: list[ShotDiff]
    clarification_needed: str | None = None  # set instead of diffs if ambiguous
```

**Prompt (`prompts.py`)** — the real instruction:
```
You are interpreting a director's requested change to a previs project.

Current shots (id, scene, summary, key fields):
{shot_summaries}

Recent edit history for context:
{recent_edits}

Director's request: "{user_request}"

Identify which shot(s) this request applies to and which field(s) change.
Only use these field names: location, time_of_day, action_summary,
suggested_camera, characters.

If the request clearly maps to specific shots and fields, output a list
of diffs. If it's ambiguous (e.g. "make it darker" without saying which
scene, or a request that doesn't map to any editable field), output a
clarification_needed question instead of guessing. Never apply a change
you're not confident about.
```

**`agent.py` flow:**
1. Load recent `ShotEdit` history (last ~10 for the project) via MCP for context — this is what makes "also revert the earlier lighting change" resolvable.
2. Call Gemini with the prompt above.
3. If `clarification_needed` is set, short-circuit: write it to the job trace, set job status to a new `needs_clarification` sub-state, and stop — **do not apply a guessed change.**
4. If `diffs` is set, validate each diff's `field` against the real `Shot` model's allowed fields (defense in depth beyond the prompt instruction), apply them via the `write_shot_records` MCP tool (extend it to support partial updates, not just full scene replacement), and record each as a `ShotEdit`.
5. Determine the affected shot set and pass it to the App-Build Agent as a scoped rebuild target (see section 4).

## 4. Scoped/Incremental Rebuilds

This is where Phase 4's "read entirely from the data file" discipline pays off: the App-Build Agent's incremental path (already seamed in Phase 4 section 3) now gets used for real. `agent.py` in `app_build_agent` receives the affected shot IDs, regenerates only the `/data/project.json` file (not the app's structure/code), and pushes an update + redeploy through Replit rather than a full generation call. The Critic Agent, correspondingly, only re-verifies the affected shots, not the whole project — full re-verification on every single-field edit doesn't scale and isn't necessary.

## 5. Orchestrator Wiring

The Coordinator's plan for `job_type == iteration` is `[iteration, app_build (scoped), critic (scoped)]` — this was already specified conceptually in `04-AGENT-ARCHITECTURE.md` §1; Phase 5 is where it's actually implemented and tested end-to-end, matching `10-DIAGRAMS.md` §4 exactly, including the `clarification_needed` branch.

## 6. API Surface

| Method | Path | Change |
|---|---|---|
| POST | `/api/v1/projects/{id}/iterate` | **New.** `{request: "make scene 4 night-time"}` → 202 `{job_id}` |
| GET | `/api/v1/jobs/{job_id}` | Now can return a `needs_clarification` status with the agent's question attached |

## 7. Frontend: Live Agent-Trace Panel

Replace Phase 2–4's polling (if you built a temporary poll loop) with a Firestore client-SDK subscription on `job_traces/{job_id}`, rendering each step as it arrives — this is the panel a judge watches during the live demo, so it deserves real design attention, not a bare JSON dump. Minimum bar: each agent's name, a status icon (queued/running/complete/failed), and the `detail` text, updating without a page refresh. Add a chat-style input for the iteration request, with the `clarification_needed` case rendered as a follow-up prompt back to the user rather than a dead end.

## 8. Required Tests

**Diff extraction (mocked LLM):**
- `test_iteration_extracts_single_field_diff` — a clear request ("make scene 4 night-time") produces exactly one diff on `time_of_day`
- `test_iteration_extracts_multi_shot_diff` — a request spanning multiple shots produces multiple diffs
- `test_iteration_requests_clarification_on_ambiguous_input` — "make it darker" with no scene reference returns `clarification_needed`, not a guessed diff
- `test_iteration_rejects_invalid_field_name` — even if the LLM hallucinates a field name outside the allowed list, the validation layer catches it before it reaches the database (this is the defense-in-depth check — test it independently of the prompt)

**Memory/history:**
- `test_iteration_uses_recent_edit_history_for_context` — mock a follow-up request referencing a prior edit; assert the prompt sent to the LLM includes that history

**Scoped rebuild:**
- `test_only_affected_shots_trigger_frame_regeneration_check` — an edit to `action_summary` (which could affect the frame) is scoped to the changed shot(s) only, not the whole project
- `test_app_build_uses_incremental_path_for_iteration_jobs` — mock and assert the incremental (data-file-only) Replit call path is used, not a full regeneration

**End-to-end:**
- `test_full_iteration_loop_updates_deployed_app` — upload → generate → submit an edit → assert the redeployed app's data reflects the change, exercising the full sequence in `10-DIAGRAMS.md` §4

**Frontend:**
- `test_trace_panel_renders_live_steps` — component test asserting the panel updates as mocked Firestore snapshot events arrive
- `test_clarification_prompt_renders_as_followup` — the `needs_clarification` state shows the agent's question, not a generic error

## Definition of Done

- [ ] All Phase 1–4 checks still pass
- [ ] All tests above pass
- [ ] A real edit request, through the actual UI, visibly updates the live trace panel step by step and results in a correctly redeployed app
- [ ] An intentionally ambiguous request results in a clarification question shown to the user, not a wrong guess applied silently
- [ ] A single-field edit measurably takes less time than a full initial generation (confirms the incremental path is actually being used, not silently falling back to full rebuilds)
- [ ] Cloud SQL and Firestore trace data agree at the end of every run — no case where the UI shows "complete" while the database disagrees

## Common Pitfalls

1. **Applying a guessed change instead of asking for clarification** — this is the fastest way to erode a director's trust in the tool during a demo. The clarification path is a feature, not a fallback to be embarrassed about.
2. **Skipping the field-name validation layer because "the prompt already constrains it"** — LLM outputs are not a substitute for a validation boundary; keep both.
3. **Falling back to a full rebuild "just to be safe" on every edit** — this silently defeats the entire incremental-rebuild design from Phase 4 and will make the live demo noticeably slower than it should be. If you catch yourself doing this, go back and fix the data-file discipline instead of working around it.
4. **Building the trace panel as an afterthought** — this is the UI a judge is staring at during your 3-minute demo video. Budget real time for it.

## Commit Message
`feat(phase-5): iteration agent and live agent-trace UI`
