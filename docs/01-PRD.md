# SceneCraft — Product Requirements Document

> Read `00-INDEX.md` first for how this fits into the full documentation set.

---

## 1. Vision

A script is the only artifact every filmmaker has on day one, yet it's the hardest one for anyone outside the writer's head to *see*. SceneCraft turns a script into a living, interactive previs application — not a slide deck, not a mood board, a real deployed app a director can click through, share, and iterate on — in the time it takes to get coffee.

## 2. Mission

Give any production, regardless of budget, a multi-agent system that reads a script, generates cinematic storyboard frames, reasons about shot composition and pacing, and autonomously builds + deploys an interactive previs web app — closing the gap between "script" and "seeing it" from weeks to minutes.

## 3. Goals

- Ingest a script (PDF, plain text, or Fountain-style format) and produce a structured scene/shot breakdown.
- Generate storyboard-quality concept frames per shot via Imagen, visually consistent across a project.
- Autonomously generate and deploy a working, navigable previs web app via Replit's Agent API.
- Support iteration: a director can request changes in natural language and see the app rebuild.
- Demonstrate genuine multi-agent orchestration — visible agent reasoning, not a single hidden LLM call wearing a UI.
- Be secure, observable, and deployable to a standard a Google Cloud judge accepts as "production-track."

## 4. Non-Goals

- **Not** a full VFX/animation pipeline — no 3D rendering, no motion capture.
- **Not** a script-writing tool — SceneCraft consumes scripts, it doesn't generate them.
- **Not** attempting final-shot-accurate camera lensing or physical simulation — this is rapid previs, not virtual production.
- **Not** building a custom low-code app builder — that capability is deliberately delegated to Replit's agent.

## 5. User Personas

### Priya — Independent Director (primary persona)
- **Context:** Directing a feature under $500K. No previs budget, no VFX supervisor on payroll.
- **Pain:** Can't communicate her shot vision to DPs or investors without expensive storyboard artists or previs studios (typically $150–500/scene).
- **Need:** A fast, cheap way to *show*, not describe, her vision.
- **Success looks like:** Uploading a scene and getting a shareable, clickable previs link before her next production meeting.

### Marcus — VFX Previs Coordinator (secondary persona)
- **Context:** Works on mid-budget productions with a real, if limited, previs budget and a small team.
- **Pain:** Manually building interactive previs walkthroughs takes his team days per sequence.
- **Need:** A strong first draft he can refine, not a replacement for his judgment.
- **Success looks like:** Generating a first-pass previs in minutes, then spending his time refining rather than starting from a blank page.

### Dana — Investor/Producer Evaluating a Pitch (tertiary persona)
- **Context:** Reviews dozens of scripts a year; struggles to visualize tone/pacing from text alone.
- **Pain:** Green-lighting decisions get made on incomplete visual information.
- **Need:** A shareable, interactive artifact that communicates vision faster than a static pitch deck.
- **Success looks like:** Clicking through a previs app during a pitch meeting instead of reading a script cold.

## 6. Competitive Analysis & Market Gap

| Category | Examples | Where it falls short |
|---|---|---|
| Traditional storyboard artists | Freelancers, boutique studios | Slow (days–weeks), expensive, output isn't interactive or easily shareable |
| Static AI image tools | Midjourney/DALL-E used ad hoc | No script understanding, no shot structure, no interactivity, no deployment |
| Previs software | ShotPro, FrameForge | Desktop-only, steep learning curve, output isn't a shareable web artifact, no AI script understanding |
| Script breakdown tools | Scenechronize, StudioBinder | Structured breakdown only — stops at spreadsheets, never produces a visual, interactive artifact |

**The gap:** nothing in this space closes the loop from *raw script text* to a *deployed, interactive, navigable app* autonomously. That full-loop autonomy — an agent that actually writes and ships working software — is the white space SceneCraft occupies, and it's why the Replit partner track is a structural fit rather than an arbitrary choice.

## 7. Feature Prioritization (MoSCoW)

**Must have**
- Script upload (PDF/plain text) → structured scene/shot breakdown
- Imagen-generated storyboard frame per shot
- Agent-driven generation + deployment of an interactive previs web app (scene navigator, shot notes, frame gallery)
- Natural-language iteration ("make scene 4 night-time") that triggers a rebuild
- Visible agent reasoning trace in the UI

**Should have**
- Multi-speaker scene read-aloud via Gemini TTS for tone-setting
- Shot-list export (CSV/PDF) for real production use
- Auth + per-project workspace (multi-user)

**Could have**
- Shot-composition critique agent (rule-of-thirds, 180-degree line checks)
- Music mood generation via Lyria for tone reference

**Won't have this cycle**
- 3D/animated previs
- Real-time multi-cursor collaborative editing

## 8. Functional Requirements

| ID | Requirement |
|---|---|
| FR1 | System shall accept script uploads in PDF and plain text, up to 50 pages |
| FR2 | System shall parse scripts into scenes, shots, characters, locations, and time-of-day metadata |
| FR3 | System shall generate one Imagen storyboard frame per identified shot, styled per a selectable visual tone |
| FR4 | System shall invoke Replit's Agent API to scaffold, generate, and deploy a Next.js previs web app from the current project data |
| FR5 | System shall accept natural-language edit requests, translate them into structured change-sets, and trigger redeployment |
| FR6 | System shall expose an agent activity log showing each agent's step, tool call, and reasoning summary |
| FR7 | System shall persist project state (script, breakdown, frames, deployed app URL) per user workspace |
| FR8 | System shall support authentication and per-project access control |

## 9. Non-Functional Requirements

- **Performance:** Script → first storyboard frame in <90s for a 10-page scene; full app deploy in <3 minutes.
- **Availability:** 99.5% target for the hosted control plane (hackathon/demo-grade; documented path to 99.9%).
- **Scalability:** Stateless API layer, horizontally scalable on Cloud Run; agent jobs queued, never synchronous in the request path.
- **Security:** All API keys in Secret Manager; no credentials in client code; signed URLs for asset storage.
- **Observability:** Full request/agent tracing via OpenTelemetry, dashboarded in Grafana.
- **Accessibility:** WCAG 2.1 AA on the control-plane UI; auto-generated alt-text for every storyboard frame.

## 10. Success Metrics & KPIs

- Time from script upload to deployed, navigable previs app — **target: under 5 minutes** for a 10-scene script.
- % of shots successfully parsed with usable metadata — **target: >90%**.
- Agent iteration success rate (edit requests that produce a correct, deployed change) — **target: >85%**.
- Judge-demo completion rate: the full script → app → edit loop fits inside the 3-minute demo video.

## 11. Risk Analysis

| Risk | Mitigation |
|---|---|
| Replit agent generation is nondeterministic/slow under demo pressure | Pre-warm a cached "golden path" script for the demo; keep a fallback pre-generated deployment |
| Imagen output style drifts across a script | Lock a style-reference prompt template per project, reused across every shot generation |
| Script parsing fails on non-standard formats | Support a strict Fountain/FDX-like format as the primary path; PDF as best-effort with a manual-correction UI |
| Scope creep from the full feature wishlist | The Must-have list above is the hackathon submission scope; Should/Could are explicitly post-hackathon |

## 12. Security & Privacy

- Scripts are unpublished IP — encrypted at rest (Cloud Storage default, CMEK optional) and in transit (TLS everywhere).
- No script content is used to train or fine-tune any model; Gemini calls use data-retention-minimizing settings.
- Per-project access control via a Firestore-backed RBAC model; JWT-based session auth.
- Secret Manager for every third-party key (Replit, Gemini) — never committed, never in plain env files in the repo.

## 13. Accessibility

- Control-plane UI meets WCAG 2.1 AA (keyboard navigation, contrast, screen-reader labels).
- Auto-generated alt-text for every storyboard frame via Gemini's multimodal captioning.
- Generated previs apps include a text-based shot-list view as a non-visual alternative to the frame gallery.

## 14. Scalability

- Control plane (FastAPI) is stateless and horizontally scaled on Cloud Run.
- Long-running agent jobs (frame generation, app build/deploy) run as async workers via Pub/Sub + Cloud Run jobs — never in the request path.
- BigQuery for analytical/history data at scale; Firestore for low-latency project state.

## 15. Future Roadmap

- Multi-user real-time collaboration on a previs project.
- Direct integration with production scheduling tools (call sheets referencing previs shots).
- A 3D camera-path previs layer, post-hackathon — likely a different partner integration.

## 16. Monetization (post-hackathon path)

- Freemium: N free script-to-app generations per month, paid tiers by team seats and generation volume.
- Studio tier: SSO, audit logs, VPC-isolated/on-prem deployment option.
