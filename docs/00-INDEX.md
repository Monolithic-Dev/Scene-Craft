# SceneCraft — Build Documentation Index

**Project:** SceneCraft — Agentic Previs Studio
**Hackathon:** Agentic Cinema: The Blockbuster Hackathon (Google Cloud) · Partner track: **Replit**
**Goal:** Build a production-grade, judge-ready submission — not an MVP.

---

## What SceneCraft is

A script goes in. A multi-agent system reads it, breaks it into scenes and shots, generates storyboard concept art, and **autonomously builds a real, interactive previs web app** — its own constrained-codegen capability, verified by a Critic Agent, hosted on Replit per the partner track's actual requirement (see `Phases/PHASE-04-APP-BUILD-AND-CRITIC.md` §0) — that a director can click through and iterate on in natural language. No developer required, no VFX budget required.

## How to use this documentation set

Read the files in this order. Each is self-contained and can be pasted into a Claude Code session on its own, but they build on each other — later files assume the decisions made in earlier ones.

| # | File | What it defines | Read this to... |
|---|------|------------------|------------------|
| 1 | `01-PRD.md` | Vision, personas, market gap, requirements, success metrics, risks, security/privacy/accessibility, roadmap | Understand *why* and *what* to build |
| 2 | `02-TECH-STACK.md` | Every technology, library, and service with version and rationale | Know exactly what to install and why |
| 3 | `03-SYSTEM-DESIGN.md` | Architecture diagrams, service breakdown, data flow, observability, deployment, cost/DR | Understand *how the whole system fits together* |
| 4 | `04-AGENT-ARCHITECTURE.md` | Every agent's responsibilities, prompts, tools, memory, and failure handling | Build the AI/agent layer correctly |
| 4b | `10-DIAGRAMS.md` | Every architecture, sequence, user-flow, ER, and deployment diagram in one place (Mermaid) | See the whole system and every user journey visually before writing code |
| 4c | `11-UI-UX-WIREFRAMES.md` | Design system tokens, screen wireframes, component hierarchy, navigation map, states/accessibility checklist | Build the actual UI to a consistent, judge-ready standard |
| 5 | `05-DATABASE-DESIGN.md` | Full ER diagram, tables, indexes, migration strategy | Build the data layer |
| 6 | `06-API-DESIGN.md` | Every REST endpoint, request/response, error codes, auth, validation | Build the API layer |
| 7 | `07-FOLDER-STRUCTURE.md` | The exact repo layout with a rationale per folder | Scaffold the repo correctly on day one |
| 8 | `08-IMPLEMENTATION-PLAN.md` | Phase-by-phase build plan with acceptance criteria and testing checklists | Sequence the actual build work |
| 9 | `09-CODING-STANDARDS.md` | Non-negotiable engineering rules — SOLID, DI, error handling, testing, security | Hold every phase to the same bar |

## Phase-wise build specs

Each phase in `08-IMPLEMENTATION-PLAN.md` now has its own deep-dive file — exact build order, exact schemas/prompts/contracts, full test lists, a Definition of Done checklist, and real pitfalls to avoid. Work through these in order in your Claude Code sessions, one phase per session (or per sitting), never skipping ahead:

| Phase | File | Covers |
|---|---|---|
| 1 | `PHASE-01-FOUNDATIONS.md` | Auth, project CRUD, script upload, repo scaffolding, CI |
| 2 | `PHASE-02-BREAKDOWN-AGENT.md` | Script/shot breakdown agent, MCP server, RAG chunking, job lifecycle |
| 3 | `PHASE-03-FRAME-GENERATION.md` | Storyboard frame agent, Imagen, parallel fan-out, accessibility captioning |
| 4 | `PHASE-04-APP-BUILD-AND-CRITIC.md` | App-build + critic/verification agents, and how the real Replit build/host requirement is satisfied |
| 5 | `PHASE-05-ITERATION-AND-TRACE-UI.md` | Natural-language iteration agent, live Firestore-backed trace UI |
| 6 | `PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md` | OTel/Grafana, Secret Manager, distributed rate limiting, Terraform, security review |
| 7 | `PHASE-07-DEMO-AND-SUBMISSION.md` | README, judge guide, demo video script, pitch deck, final submission checklist |

## How to brief Claude Code with these files

A good pattern for a Claude Code session:

1. Paste `01-PRD.md` and `02-TECH-STACK.md` first, ask Claude Code to confirm it understands the product and stack.
2. Paste `07-FOLDER-STRUCTURE.md` and ask it to scaffold the repo skeleton.
3. Paste `05-DATABASE-DESIGN.md` and `06-API-DESIGN.md`, work through **Phase 1** of `08-IMPLEMENTATION-PLAN.md`.
4. Paste `04-AGENT-ARCHITECTURE.md` when you reach the agent-building phases (Phase 2 onward).
5. Keep `09-CODING-STANDARDS.md` pinned/referenced in every session — it's the quality bar for every phase, not a one-time read.
6. **Never skip a phase's acceptance criteria before moving to the next phase** — this is what keeps a hackathon build from collapsing into an unfinished pile of half-features at the deadline.

## Non-negotiables carried through every file

- Google Cloud–native where sensible (Gemini, Vertex AI, Agent Builder/ADK, Cloud Run, Firestore, BigQuery, Secret Manager)
- Replit as a genuinely satisfied partner requirement — SceneCraft's own App-Build Agent generates the previs app, hosted on Replit (replit.app/replit.dev) with a real Replit-Agent-built piece merged into the repo, not a checkbox gesture (see `PHASE-04-APP-BUILD-AND-CRITIC.md` §0/§5)
- Production practices throughout: typed code, tested code, structured error handling, no TODOs, no mocked architecture, no shortcuts
- Every phase must be independently demonstrable — a judge (or you, at 2am before the deadline) should be able to see working software at the end of every phase, not just at the very end
