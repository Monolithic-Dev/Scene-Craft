# SceneCraft — Phase 4 Build Spec: App-Build & Critic Agents (Replit Integration)

> Read `PHASE-03-FRAME-GENERATION.md` (must be complete and passing first), `04-AGENT-ARCHITECTURE.md` §4–5, `10-DIAGRAMS.md` §1–3, and `09-CODING-STANDARDS.md` before starting. **This is the phase judges will scrutinize hardest for partner-integration depth — treat it as the centerpiece, not a checkbox.**

## Objective

Take a project's complete breakdown + frames and turn them into a real, live, navigable previs web app via Replit's Agent API — then verify, automatically, that the deployed app actually reflects what was intended before telling the user it's done.

## Scope

**In scope:** the App-Build Agent, the Critic/Evaluator Agent, the Replit Agent API integration (generation + deployment), the spec-translation layer, the verification/retry loop.
**Out of scope:** natural-language iteration (Phase 5 — this phase only handles the *initial* build), the live UI trace panel (still polling-based until Phase 5).

---

## 1. Why This Phase Is the Judging Centerpiece

Re-read the hackathon's judging criteria from `01-PRD.md`: **Quality of the Idea** explicitly rewards "creative, non-obvious use of ... the Partner services." The entire premise of SceneCraft's differentiation (see `01-PRD.md` §6, market gap) rests on Replit's Agent API being the literal mechanism that produces the deliverable — not a database, not a dashboard, not an API called once and forgotten. Every design decision in this phase should be checked against: *does this make the Replit integration deeper, or just present?*

## 2. Data Model Addition

`GenerationJob` gains `deployed_app_url` (already in the Phase 1 schema — now actually populated) and `error_detail`. No new tables needed this phase.

## 3. The App-Build Agent (`agents/app_build_agent/`)

**Structure:**
```
agents/app_build_agent/
├── agent.py            # entrypoint: run(project_id, previous_spec=None) -> BuildResult
├── spec_builder.py       # translates ProjectState -> a Replit Agent build spec
├── replit_client.py       # thin wrapper around the Replit Agent API
└── prompts.py              # the spec prompt sent to Replit's agent
```

**`spec_builder.py`** — the translation layer. Input: the full `ProjectState` (scenes, shots, frame URLs, alt-text). Output: a structured JSON data file (the previs app's content source) **plus** the natural-language build instruction sent to Replit. Keep these two things separate — the data is deterministic and directly serializable from the database; only the *instruction* needs to be an LLM-authored prompt. Don't have an LLM re-derive the data from scratch each time; that's both wasteful and a source of drift.

**Build instruction (`prompts.py`)** — the real spec sent to Replit's agent:
```
Build a Next.js web app with the following pages/components:

1. A scene navigator sidebar listing every scene by heading, in order.
2. Selecting a scene shows its shots as a vertical list. Each shot displays:
   - the storyboard frame image (URL provided in the data file)
   - the action summary
   - the suggested camera direction
   - the character list for that shot
3. A "shot list" export button that downloads the current project's
   shots as CSV.
4. Clean, minimal styling — dark background, high-contrast text,
   no unnecessary chrome. This is a working tool for a film crew,
   not a marketing site.

Data source: attached JSON file at /data/project.json (schema below).
Do not hardcode any scene/shot content — read entirely from the data file.

{json_schema}
```

**Why "do not hardcode... read entirely from the data file" matters:** this is what makes the Iteration Agent's incremental redeploys (Phase 5) actually work — if Replit's agent bakes content into the app's code instead of reading from a data file, every edit becomes a full regeneration instead of a data update, which is slower and riskier. Get this right now; it's much harder to retrofit later.

**`replit_client.py`** — wraps two calls: `generate(spec) -> GenerationHandle` and `deploy(handle) -> DeployedApp {url, build_log}`. Both are genuinely long-running; call them from within the async Cloud Run worker (per `03-SYSTEM-DESIGN.md`), never in the synchronous request path.

**Incremental builds:** `agent.py` accepts an optional `previous_spec`. If present and the diff from the Iteration Agent (Phase 5) only touches data (not structure), skip re-sending the full build instruction and instead push an updated `/data/project.json` through Replit's update mechanism, then redeploy. This is a Phase 5 concern to *use*, but the seam for it belongs here, in Phase 4's design, not bolted on later.

## 4. The Critic / Evaluator Agent (`agents/critic_agent/`)

**Structure:**
```
agents/critic_agent/
├── agent.py           # entrypoint: run(project_id, deployed_url) -> Verdict
├── fetcher.py           # headless fetch/screenshot of the deployed app
└── comparator.py          # structural comparison against expected ProjectState
```

**`agent.py` flow:**
1. Fetch the deployed app's rendered content (`fetcher.py` — a headless browser fetch is enough; a full screenshot pipeline is a nice-to-have, not required for Phase 4's bar).
2. Extract the shot count and shot identifiers actually present in the rendered DOM/content.
3. Compare against the expected shot list from `ProjectState` (`comparator.py`).
4. Return a `Verdict`: `{passed: bool, missing_shots: list[str], mismatched_shots: list[str], notes: str}`.

**On failure:** hand the verdict back to the App-Build Agent as corrective context ("Shot 7 is missing from the deployed app — the data file lists it but it's not rendered. Check the scene navigator's iteration logic.") and trigger exactly one retry. If the retry also fails, the Coordinator marks the job `FAILED_NEEDS_REVIEW` with the Critic's notes attached — **never silently mark a broken deployment as complete.** This is the single most important behavior in this phase: shipping a broken app to the user is worse than an honest failure state.

## 5. Orchestrator Wiring

Extend the Coordinator's plan for `initial_generation` to its full form: `[breakdown, frames, app_build, critic]`. Wire the Critic's bounded retry loop back to `app_build` per the state diagram in `10-DIAGRAMS.md` §2 — implement that diagram's transitions exactly, including the `NeedsReview` terminal state.

## 6. Extended API Surface

| Method | Path | Change |
|---|---|---|
| GET | `/api/v1/jobs/{job_id}` | `steps` now includes `app_build` and `critic`; on success, response includes `deployed_app_url` |
| GET | `/api/v1/projects/{id}` | Response includes `deployed_app_url` (nullable until the job completes) |

## 7. Required Tests

**Spec translation (pure unit tests):**
- `test_spec_builder_produces_valid_json_data_file` — given a known `ProjectState`, assert the output JSON matches the schema Replit's agent is instructed to expect
- `test_spec_builder_excludes_flagged_shots_or_marks_them` — decide and test the behavior for shots flagged `needs_review` from Phase 2/3 (recommendation: include them with a visible "under review" marker rather than silently dropping them)

**App-Build Agent (mocked Replit API):**
- `test_app_build_calls_replit_with_correct_spec` — assert the build instruction sent contains the "read entirely from the data file" constraint and the correct JSON schema
- `test_app_build_retries_on_deploy_failure` — mock one failure then a success; assert exactly one retry with the error appended
- `test_app_build_escalates_after_max_retries` — mock persistent failure; assert `FAILED_NEEDS_REVIEW` with the Replit error captured in `error_detail`

**Critic Agent (mocked fetch):**
- `test_critic_passes_on_matching_content` — mocked rendered content matches expected shots exactly → `passed: True`
- `test_critic_detects_missing_shot` — mocked rendered content missing one shot → `passed: False`, `missing_shots` populated correctly
- `test_critic_triggers_exactly_one_retry_on_failure` — integration test confirming the retry-then-escalate behavior, not infinite retries
- `test_critic_failure_after_retry_marks_needs_review` — job ends in `FAILED_NEEDS_REVIEW`, not silently `COMPLETE`

**End-to-end (mocked LLM/Imagen/Replit):**
- `test_full_initial_generation_produces_deployed_url` — script upload through to a `deployed_app_url` on the project, exercising the full `[breakdown, frames, app_build, critic]` chain from `10-DIAGRAMS.md` §3

## Definition of Done

- [ ] All Phase 1–3 checks still pass
- [ ] All tests above pass
- [ ] Against a real Replit sandbox account (manual verification, not just mocked CI), a real project produces a genuinely deployed, navigable app matching the spec in section 3
- [ ] Deliberately breaking one shot's data (manual test) causes the Critic Agent to catch it and trigger the retry path — observe this happen, don't just trust the test suite
- [ ] A job that can't be fixed after retry ends in `FAILED_NEEDS_REVIEW` with a genuinely useful `error_detail`, not a generic "something went wrong"
- [ ] The generated app reads all content from the data file — confirm by inspecting Replit's generated code, not just by checking the final render

## Common Pitfalls

1. **Letting Replit's agent hardcode content into the generated app's source** — catches up with you immediately in Phase 5 when every "iteration" becomes a full rebuild instead of a fast data update. Enforce the data-file constraint in the build instruction from day one of this phase.
2. **Marking a job complete as soon as `deploy()` returns a URL** — a URL existing is not the same as the app being correct. The Critic Agent's pass is what should gate `COMPLETE`, not the deploy call succeeding.
3. **Unbounded retries between Critic and App-Build** — without an explicit retry counter, a systematically broken spec can loop forever, burning API budget and never surfacing the actual problem to a human. One bounded retry, then escalate — no exceptions.
4. **Treating this as "just another API call"** — of every agent in the system, this one is your primary differentiator in the judging criteria. Spend the extra time making the build instruction genuinely good (clear, complete, unambiguous) rather than treating it as boilerplate.

## Commit Message
`feat(phase-4): app-build and critic agents with Replit integration`
