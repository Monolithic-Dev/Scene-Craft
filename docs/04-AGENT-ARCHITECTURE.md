# SceneCraft — AI Agent Architecture

> Read `00-INDEX.md` first for how this fits into the full documentation set. Pairs with `03-SYSTEM-DESIGN.md`.

Orchestration model: a **LangGraph state graph** hosted inside a single Agent Orchestrator service (deployed via Vertex AI Agent Engine / ADK), with each agent below as a distinct node. State is a shared `ProjectState` object threaded through the graph; every agent reads what it needs and writes back its own slice — no agent reaches into another agent's working memory directly.

---

## 1. Planner / Coordinator Agent

- **Responsibilities:** Entry point for every job. Decides which downstream agents to invoke and in what order (full generation vs. incremental iteration), sets the job's execution plan, owns retry/escalation policy.
- **Input:** Job type (`initial_generation` | `iteration`), project ID, raw request payload.
- **Output:** An ordered execution plan (list of agent nodes to invoke) written to `ProjectState.plan`.
- **Tools:** `get_project_state` (MCP), `enqueue_job` (Pub/Sub publisher).
- **Prompt (core instructions, summarized):** "You are the coordinator for a previs-generation pipeline. Given the job type and current project state, decide the minimal correct sequence of agents needed. For `initial_generation`, always run breakdown → frames → app-build → critic. For `iteration`, run iteration-agent → app-build → critic only, skipping breakdown/frames unless the diff touches shot metadata that invalidates existing frames."
- **Memory:** Reads project history (Firestore) to detect duplicate/redundant runs.
- **Failure handling:** If a downstream agent fails twice, the Coordinator halts the plan, marks the job `failed_needs_review`, and surfaces the failure reason to the UI rather than silently retrying indefinitely.
- **Communication protocol:** Publishes/subscribes via Pub/Sub topics (`scenecraft.job.step`) so the UI's agent-trace panel gets real-time step events.

## 2. Script/Shot Breakdown Agent

- **Responsibilities:** Convert raw script text into structured scenes/shots.
- **Input:** Script text (chunked if long), style/genre metadata.
- **Output:** JSON: `scenes[] { scene_id, heading, shots[] { shot_id, characters[], location, time_of_day, action_summary, suggested_camera, dialogue_snippet } }`.
- **Tools:** `chunk_and_embed_script` (RAG retrieval helper), `write_shot_records` (MCP).
- **Prompt (summarized):** "You are a script supervisor's assistant. Read the following script chunk and any retrieved context from earlier chunks. Extract every distinct shot implied by scene headings and action lines. Output strict JSON matching the given schema. Do not invent characters or locations not present in the text."
- **Memory:** Retrieves prior chunks' extracted entities (characters/locations) via RAG so naming stays consistent across a long script.
- **Failure handling:** JSON-schema validation on output; on validation failure, one automatic re-prompt with the validation error appended; on a second failure, flag the scene for manual review rather than guessing.
- **Communication protocol:** Returns structured output directly to the Coordinator via the shared state object; no direct agent-to-agent calls.

## 3. Storyboard Frame Generation Agent

- **Responsibilities:** Produce one Imagen concept frame per shot, visually consistent across the project.
- **Input:** Shot record + project-level style-reference prompt (locked at project creation).
- **Output:** Image URL (Cloud Storage) per shot, plus an auto-generated alt-text caption (accessibility requirement).
- **Tools:** `generate_image` (Imagen), `caption_image` (Gemini multimodal), `store_asset` (Cloud Storage).
- **Prompt (summarized):** "Generate a storyboard-style concept frame for this shot: {action_summary}, camera: {suggested_camera}, location: {location}, time: {time_of_day}. Maintain this visual style throughout: {project_style_reference}."
- **Memory:** None beyond the project style-reference (kept in project config, not per-call memory).
- **Failure handling:** Retries on generation API errors (exponential backoff, max 3); on persistent failure, inserts a placeholder frame and flags the shot rather than blocking the whole job.
- **Communication protocol:** Runs as a fan-out of parallel async worker jobs (one per shot), coordinated via Pub/Sub, rejoined by the Coordinator once all shots report complete or failed.

## 4. App-Build Agent

> Note: no public "Replit Agent API" exists for a normal account, and the hackathon's actual Replit requirement is a build-process + hosting-target requirement about the SceneCraft submission itself, not a per-project runtime API call — see `Phases/PHASE-04-APP-BUILD-AND-CRITIC.md` §0 for the full correction. This agent is SceneCraft's own capability.

- **Responsibilities:** Translate the current structured project data into SceneCraft's own working previs page (`/projects/{id}/previs`) — a deterministic data layer plus a bounded, schema-validated styling/customization layer, rendered by a fixed, pre-tested app shell (constrained scaffolding, not freeform code generation — see `Phases/PHASE-04-APP-BUILD-AND-CRITIC.md` §1).
- **Input:** Full `ProjectState` (scenes/shots/frame URLs), previous customization JSON reference (for incremental builds).
- **Output:** Data file + customization JSON (the previs route renders these directly — there is no separate deploy step per project).
- **Tools:** `write_previs_data` (MCP — persists the generated data file), Gemini call for the bounded customization JSON only.
- **Prompt (summarized, the one LLM-authored surface):** "Given this project's title, style reference, and tone, produce JSON matching this schema: `{title, accent_color, tone_note}`. Do not include anything else — the app shell already defines structure and content." Schema-validated on return; malformed output retries once, then falls back to defaults rather than failing the job.
- **Memory:** Keeps the last successful customization JSON so incremental iterations diff against it, not a full regeneration, where possible.
- **Failure handling:** On persistent schema-validation failure, falls back to defaults and proceeds (styling is cosmetic, never worth failing a job over); on data-file write failure, retries then escalates to the Coordinator as `failed_needs_review`.
- **Communication protocol:** Runs from within an async Cloud Run job (not in the user-facing request path); no external API dependency beyond Gemini, which the rest of the system already depends on.

## 5. Critic / Evaluator Agent

- **Responsibilities:** Verify the generated previs content actually reflects the intended project state before marking a job complete.
- **Input:** The generated data file + customization JSON, expected shot count/structure from `ProjectState`.
- **Output:** Pass/fail verdict + diagnostic notes.
- **Tools:** `compare_structure` (data-file diff against expectation), schema validator for the customization JSON.
- **Prompt:** None required for the structural check (deterministic comparison); no LLM call needed on the happy path.
- **Memory:** None — stateless verification per run.
- **Failure handling:** On mismatch, sends corrective feedback back to the App-Build Agent for one bounded retry; if still failing, surfaces to the user with specifics rather than silently shipping broken previs content.
- **Communication protocol:** Direct handoff to App-Build Agent on retry; otherwise reports terminal status to Coordinator.

## 6. Iteration Agent

- **Responsibilities:** Turn a natural-language edit request into a structured diff against project data.
- **Input:** User's free-text edit request + current `ProjectState` + recent edit history (memory).
- **Output:** A structured change-set: `{shot_id, field, old_value, new_value}[]`.
- **Tools:** `read_project_state` (MCP), `write_shot_records` (MCP).
- **Prompt (summarized):** "Interpret the user's requested change against the current shot data. Output only a structured diff of fields to change. If the request is ambiguous, output a clarification question instead of guessing."
- **Memory:** Firestore-backed edit history per project, so follow-up requests ("also revert the earlier lighting change") resolve correctly.
- **Failure handling:** Ambiguous requests short-circuit back to the user via the UI for clarification rather than applying a guessed change.
- **Communication protocol:** Writes the diff to shared state; Coordinator re-triggers App-Build + Critic agents for the affected shots only.

---

## 7. Design Principles That Apply to Every Agent

1. **Bounded retries, never silent infinite loops.** Every agent above has a stated max-retry count. If you add a new agent, give it one too.
2. **Fail loud to the Coordinator, never fail silent to the user.** A stalled job with a clear `failed_needs_review` status is always better than an app that looks finished but silently dropped three shots.
3. **State lives in `ProjectState`, not in an agent's head.** Agents are stateless workers reading/writing a shared, persisted object — this is what makes the Iteration Agent's incremental rebuilds possible and what makes the whole pipeline debuggable from the agent-trace log.
4. **Every tool call goes through MCP, never direct DB access.** This is both your security boundary and the actual MCP-server deliverable the hackathon rubric asks for — don't treat it as optional plumbing.
5. **Every agent emits a trace span.** If it's not visible in the agent-trace panel, a judge can't see the "genuine multi-agent" story you're telling — instrument first, not as an afterthought.
