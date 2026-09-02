# SceneCraft — Phase 3 Build Spec: Storyboard Frame Generation Agent

> Read `PHASE-02-BREAKDOWN-AGENT.md` (must be complete and passing first), `04-AGENT-ARCHITECTURE.md` §3, `10-DIAGRAMS.md` §1 and §9, and `09-CODING-STANDARDS.md` before starting.

## Objective

For every shot produced by Phase 2, generate a visually consistent Imagen storyboard frame, store it durably, and caption it for accessibility — with a fan-out/rejoin execution model so a project with 40 shots doesn't generate them one at a time in serial.

## Scope

**In scope:** the Frame Generation Agent, the `shot_frames` table (already specified in `05-DATABASE-DESIGN.md`, built now), Cloud Storage integration, parallel async worker execution, style-reference locking, alt-text captioning, placeholder-on-failure behavior.
**Out of scope:** anything Replit/app-build related (Phase 4), the live UI trace panel (Phase 5 — Phase 3 exposes status via the same `GET /jobs/{id}` polling endpoint from Phase 2, extended with a `frames` step).

---

## 1. Data Model

Add `ShotFrame` per `05-DATABASE-DESIGN.md` §3 (`shot_id` FK, `image_url`, `alt_text`, `generated_at`). New Alembic migration. Add an index on `shot_frames(shot_id)` if not already covered.

## 2. Style Reference Locking

`Project.style_reference` (already in the schema from Phase 1) is set once at project creation and treated as immutable for the life of the project's initial generation — **every** frame-generation prompt must interpolate the same style-reference string verbatim. This is the single biggest lever against visual inconsistency across a project's storyboard, and it should be enforced in code (the agent reads it from `ProjectState`, never accepts a per-call override during initial generation), not just as a convention.

If a user wants to change the visual style later, that's an explicit "restyle project" action (out of scope for the hackathon submission, but worth a one-line note in code — don't silently let the Iteration Agent (Phase 5) drift the style prompt shot-by-shot).

## 3. The Frame Agent (`agents/frame_agent/`)

**Structure:**
```
agents/frame_agent/
├── agent.py          # entrypoint: run(project_id) -> FrameGenerationResult
├── prompts.py          # Imagen prompt template
├── worker.py            # per-shot Cloud Run job logic (the fan-out unit)
└── captioning.py         # Gemini multimodal alt-text generation
```

**Model note:** implemented against `gemini-2.5-flash-image` ("Nano Banana") via `generate_content`, not the dedicated Imagen `generate_images()` API this section originally specced. Confirmed empirically against a real GCP project with billing and the Vertex AI API enabled: the Imagen publisher models stayed 404 (Model Garden gates generative-media models individually, separate from API enablement), while `gemini-2.5-flash-image` worked immediately with good output quality — and the `google-genai` SDK itself flags `generate_images()` as deprecated in favor of this path. `shared/imagen_client.py` keeps the `Imagen*` naming (it's still the image-generation role in the pipeline) but the model is configurable via `IMAGEN_MODEL` in `agents/.env`.

**Prompt template (`prompts.py`)** — the real prompt, not a summary:
```
Generate a storyboard-style concept frame for the following shot.

Shot action: {action_summary}
Camera: {suggested_camera}
Location: {location}
Time of day: {time_of_day}
Characters present: {characters}

Visual style (apply consistently): {project_style_reference}

Composition should read clearly as a single storyboard panel — favor
clarity of action and camera framing over photorealistic detail.
```

**Fan-out execution model:**
1. Coordinator, after the Breakdown Agent completes, publishes one Pub/Sub message per shot (not one message for the whole project) to a `scenecraft.frame.generate` topic.
2. Each message is picked up by an independent Cloud Run job invocation (`worker.py`) — this is what makes 40 shots generate in parallel rather than serially blocking the job.
3. Each worker: calls Imagen with the interpolated prompt, uploads the result to Cloud Storage under `projects/{project_id}/frames/{shot_id}.png`, calls Gemini multimodal captioning for alt-text, writes the `ShotFrame` record via the MCP `write_shot_records` extension (add a `write_frame_record` MCP tool alongside the two from Phase 2), and publishes a completion event.
4. The Coordinator tracks completion by counting expected-vs-received completion events per job, and transitions `GenerationJob` to the next stage only once every shot has reported complete **or** failed (never partial-silent).

## 4. Captioning (`captioning.py`)

Real Gemini multimodal call: given the generated image, produce a one-sentence, screen-reader-appropriate alt-text description (not a restatement of the prompt — describe what's actually visible in the generated image, since generation output can diverge from the prompt). This directly satisfies the accessibility NFR in `01-PRD.md` §13 — don't treat it as optional polish.

## 5. Failure Handling (this is the part most likely to be under-built — don't skip it)

- **Imagen API error (rate limit, transient failure):** retry with exponential backoff, max 3 attempts, per shot — one shot's retries must never block other shots' parallel generation.
- **Persistent failure after retries:** insert a placeholder `ShotFrame` (a static "frame unavailable" asset, `alt_text = "Storyboard frame generation failed for this shot"`), flag the shot record itself (`needs_review` boolean or similar), and let the job proceed. **A job must never get stuck because one shot out of forty failed.**
- **Captioning failure (image succeeded, caption call failed):** store the frame with an empty/fallback alt-text and flag for caption regeneration — don't fail the whole shot over a captioning-only error, since the image itself is still usable.

## 6. Extended API Surface

| Method | Path | Change |
|---|---|---|
| GET | `/api/v1/jobs/{job_id}` | `steps` now includes a `frames` entry with sub-progress (`{"completed": 12, "total": 18, "failed": 1}`) |
| GET | `/api/v1/projects/{id}` | Response now includes `shot_frames` (image URL + alt text) nested under each shot |

## 7. Required Tests

**Prompt construction (pure unit tests, no external calls):**
- `test_frame_prompt_includes_style_reference` — assert the interpolated prompt string contains the exact project style-reference text
- `test_frame_prompt_handles_missing_characters` — a shot with an empty character list still produces a valid prompt (no `None`/`null` leaking into the string)

**Fan-out/rejoin logic (mocked Imagen/Cloud Storage):**
- `test_all_shots_get_a_frame_on_success` — N shots in, N `ShotFrame` records out
- `test_job_waits_for_all_shots_before_advancing` — job status stays at `frames` stage until every shot reports complete, even if some finish much faster than others
- `test_one_failed_shot_does_not_block_others` — mock one shot's Imagen call to fail persistently; assert the other shots still complete and the job still advances

**Failure/placeholder path:**
- `test_persistent_imagen_failure_inserts_placeholder` — after exhausting retries, a placeholder frame with the documented alt-text is stored, not a missing record
- `test_retry_backoff_is_exponential_and_bounded` — assert exactly 3 attempts, with increasing delay, then the placeholder path triggers

**Captioning:**
- `test_caption_failure_does_not_fail_the_shot` — mock a captioning error after a successful image generation; assert the frame record still exists with a fallback alt-text

**Integration:**
- `test_frame_generation_follows_breakdown_in_orchestrator` — end-to-end (mocked LLM/Imagen) confirms the Coordinator only starts frame generation after breakdown completes, per the state diagram in `10-DIAGRAMS.md` §2

## Definition of Done

- [ ] All Phase 1 and 2 checks still pass
- [ ] All tests above pass
- [ ] A real project with a multi-scene script produces one frame per shot, all sharing a visually consistent style (manually verify a sample run)
- [ ] Killing/failing one shot's generation (simulate in a manual test) does not prevent the rest of the project's frames from completing
- [ ] Every stored frame has non-empty alt-text (either real or a documented fallback)
- [ ] `GET /jobs/{id}` shows real-time sub-progress during frame generation when polled repeatedly

## Common Pitfalls

1. **Generating frames serially "to keep it simple"** — this is the single most common way a hackathon demo times out live. Build the fan-out from the start; retrofitting parallelism under deadline pressure is worse than building it correctly now.
2. **Letting the Coordinator advance the job before every shot reports in** — a race condition here produces an app in Phase 4 that's missing frames for shots that were still generating. Count completions explicitly; don't just wait for "the topic to go quiet."
3. **Re-deriving the style prompt per shot instead of reading the locked project-level value** — even a subtly different phrasing of the "same" style across shots measurably degrades visual consistency in Imagen output.
4. **Treating a captioning failure as a shot failure** — they're independent concerns with independent failure handling; conflating them means a flaky captioning call can needlessly trigger the placeholder-image path for a perfectly good frame.

## Commit Message
`feat(phase-3): storyboard frame generation agent`
