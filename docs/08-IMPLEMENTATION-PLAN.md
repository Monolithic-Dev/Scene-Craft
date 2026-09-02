# SceneCraft — Phase-by-Phase Implementation Plan

> Read `00-INDEX.md` first for how this fits into the full documentation set. This is the file to work through, phase by phase, in your Claude Code sessions — do not start phase N+1 until phase N's acceptance criteria pass.

Each phase is independently buildable and independently demonstrable. If the hackathon clock runs out after Phase 4, you should still have a working, demoable product — that's the point of phasing it this way rather than building everything halfway.

---

## Phase 1 — Foundations
**Objectives:** Repo scaffolding, auth, project CRUD, script upload (no AI yet — store raw text only).
**Deliverables:** `apps/api` skeleton with auth + project/script endpoints, `apps/web` skeleton with login + upload UI, Cloud SQL schema migrated, CI pipeline running lint/type-check/tests.
**Acceptance criteria:** A user can sign up, create a project, upload a script, and see it stored and listed. All endpoints have request validation and error handling. CI green on a clean clone.
**Testing checklist:** Unit tests on auth + project service; integration test for the upload endpoint; migration runs cleanly against a fresh DB.
**Commit message:** `feat(phase-1): project scaffolding, auth, and script upload`

## Phase 2 — Script Breakdown Agent
**Objectives:** Implement the Breakdown Agent, wire it to the upload flow, persist structured scenes/shots.
**Deliverables:** `agents/breakdown_agent`, MCP write-tool for shot records, job status tracking (`generation_jobs`).
**Acceptance criteria:** Uploading a real script produces a correct, schema-valid scene/shot breakdown viewable via the API; job status transitions correctly (queued → running → complete/failed).
**Testing checklist:** Golden-file tests against 2–3 sample scripts; schema validation failure path tested explicitly.
**Commit message:** `feat(phase-2): script/shot breakdown agent`

## Phase 3 — Storyboard Frame Generation
**Objectives:** Implement the Frame Agent, Imagen integration, Cloud Storage asset pipeline, alt-text captioning.
**Acceptance criteria:** Every shot in a project gets a stored, retrievable frame image with alt-text; failures degrade to a flagged placeholder, never a blocked pipeline.
**Testing checklist:** Mocked Imagen tests for prompt construction; integration test for storage + retrieval; failure-path test for the placeholder fallback.
**Commit message:** `feat(phase-3): storyboard frame generation agent`

## Phase 4 — App-Build & Critic Agents
**Objectives:** Implement the App-Build Agent (constrained-codegen previs generation — see `Phases/PHASE-04-APP-BUILD-AND-CRITIC.md` §0/§1 for why this replaced the originally-specced Replit Agent API, which doesn't exist for a normal account) and the Critic Agent verification loop. Separately, satisfy the hackathon's actual Replit requirement: host SceneCraft itself on Replit (replit.app/replit.dev) and get a real piece of it built via a genuine Replit Agent session (§5 of the same doc).
**Acceptance criteria:** A project with breakdown + frames produces a live, navigable previs page whose content the Critic Agent verifies matches expectations before the job is marked complete.
**Testing checklist:** Critic Agent test with intentionally broken/missing shot data to confirm it catches and triggers retry; schema-validation test for the bounded customization JSON.
**Commit message:** `feat(phase-4): app-build and critic agents (self-hosted previs generation)`

## Phase 5 — Iteration Loop & Agent Trace UI
**Objectives:** Implement the Iteration Agent, the natural-language edit endpoint, and the live agent-trace panel in the frontend (Pub/Sub-driven).
**Acceptance criteria:** A user can submit a plain-English edit request and see the app redeploy correctly, with each agent step visible in real time in the UI.
**Testing checklist:** End-to-end test: upload → generate → edit → verify redeployed app reflects the change; UI test for the live trace panel updating correctly.
**Commit message:** `feat(phase-5): iteration agent and live agent-trace UI`

## Phase 6 — Observability, Security Hardening & Deployment
**Objectives:** OpenTelemetry instrumentation, Grafana dashboards, Secret Manager migration for all keys, Terraform-managed Cloud Run deployment, CI/CD to staging + production.
**Acceptance criteria:** Full request/agent trace visible in Grafana; no secrets in code or env files; one-command Terraform deploy to a clean GCP project.
**Testing checklist:** Load test on the API gateway; security review checklist (auth boundaries, input validation, secret handling) signed off.
**Commit message:** `feat(phase-6): observability, security hardening, production deployment`

## Phase 7 — Demo Polish & Submission Materials
**Objectives:** README, architecture docs, judge guide, 3-minute demo script/recording, pitch deck.
**Acceptance criteria:** Repo is public with a visible license, README explains setup + architecture, demo video shows the real script→app→edit loop end to end within 3 minutes.
**Testing checklist:** Fresh-clone setup test (someone who's never seen the repo can run it from the README); demo video timing check against Devpost's stated requirements.
**Commit message:** `docs(phase-7): submission documentation and demo materials`

---

## How to run a phase in Claude Code

For each phase:
1. Paste this file's section for the phase, plus `09-CODING-STANDARDS.md`, plus whichever domain doc the phase touches (`04-AGENT-ARCHITECTURE.md` for phases 2–5, `03-SYSTEM-DESIGN.md` for phase 6).
2. Ask Claude Code to implement against the stated deliverables — real code, real tests, no placeholders.
3. Run the testing checklist yourself before declaring the phase done — don't take "should work" as a substitute for a green test run.
4. Only then move to the next phase's prompt, in a fresh or continued session.

## Anti-patterns to explicitly avoid

- Building Phase 4's App-Build Agent before Phase 2's breakdown data exists to feed it — you'll end up mocking data you'll have to unwind later.
- Skipping a phase's tests "to save time" — a hackathon demo failing live because Phase 3's placeholder-fallback path was never tested is a worse outcome than spending the extra hour on it now.
- Writing all seven phases' code in one long session without running anything in between — verify as you go, the way this plan is sequenced to let you.
