# SceneCraft — Judge Guide

This document exists for one reason: you're reviewing many submissions quickly, and the mapping from "what we built" to "what you're scoring" shouldn't require you to reverse-engineer it from a README written for contributors. Four sections below, one per judging criterion, each pointing at specific evidence rather than asserting it.

Live app: **[hosted URL — see README]** · Demo video: **[link — see README]** · Repo: **[this repo]**

---

## Technological Implementation

SceneCraft is a genuine multi-agent system, not a single LLM call wearing a UI. Six agents (Breakdown, Frame, App-Build, Critic, Iteration, plus the Coordinator that orchestrates them) communicate through a real MCP server boundary — `agents/` never touches the database directly; every write goes `agent → MCP (stdio) → apps/api's /internal/v1 endpoints → Postgres`. See [`docs/04-AGENT-ARCHITECTURE.md`](04-AGENT-ARCHITECTURE.md) for the full architecture and [`docs/10-DIAGRAMS.md`](10-DIAGRAMS.md) §2 for the per-job state machine.

The genuine differentiator is the **App-Build/Critic Agent pair** ([`docs/Phases/PHASE-04-APP-BUILD-AND-CRITIC.md`](Phases/PHASE-04-APP-BUILD-AND-CRITIC.md) §1): rather than an unconstrained code-generation agent writing arbitrary source per project — slow, unverifiable, and a real security surface — the App-Build Agent fills in a fixed, pre-tested app shell from a deterministic data layer, with exactly one bounded, schema-validated LLM call for presentation-only values (accent color, tone note — never structure or content). The Critic Agent then independently re-verifies shot-frame coverage and the customization schema before a job is ever marked complete, with a bounded one-retry policy. This is constrained, verifiable generation, not a hope that the model got it right.

**The Replit requirement was handled honestly, not glossed over.** Early in this build, the docs assumed a "Replit Agent API" that turned out not to exist for a normal account — verified against the hackathon's actual rules and Replit's own docs, not assumed. Rather than quietly working around it, the premise was corrected across 13 documentation files before implementation started (see [`docs/Phases/PHASE-04-APP-BUILD-AND-CRITIC.md`](Phases/PHASE-04-APP-BUILD-AND-CRITIC.md) §0 for the full correction) — the real requirement is build-process + hosting (Replit Agent as part of development, `replit.app`/`.dev` hosting), which is what's actually implemented.

Phase 6 adds the production-track observability and security work a judge expects from a "not just a hackathon toy" submission: OpenTelemetry spans around every agent invocation (`agent.<name>.run`, with status/duration/retry visible per hop), a Redis-backed distributed rate limiter (replacing an explicitly-flagged-temporary in-process one), structured JSON logging, and a full Terraform-provisioned production architecture — 3 least-privilege-IAM Cloud Run services, Cloud SQL, Pub/Sub job dispatch, Secret Manager for every credential. See [`docs/Phases/PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md`](Phases/PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md) and `infra/`.

## Design

Judge this by using the product, not reading about it. The deployed previs app (`/projects/{id}/previs`) is a complete experience — a scene navigator, shot cards with generated storyboard frames and alt-text, a CSV export for real production use — not a bare API response. The live agent-trace panel (the project dashboard) shows each agent's stage transitions in real time via a genuine Firestore push subscription, not a polling spinner: upload a script and watch Breakdown → Frames → App-Build → Critic light up as they actually happen. Typing a plain-English edit ("make scene 4 night-time") and watching the trace panel run a scoped, faster rebuild is the single clearest demonstration of the system actually working end to end.

## Potential Impact

Three personas, from [`docs/01-PRD.md`](01-PRD.md) §5, each with a concrete before/after:
- **Priya, an independent director** on a sub-$500K feature, has no previs budget — storyboard artists run $150–500/scene. SceneCraft turns a script upload into a shareable, clickable previs link before her next production meeting, not weeks later.
- **Marcus, a VFX previs coordinator** on a mid-budget production, currently spends days per sequence manually building interactive walkthroughs. A first-pass previs in minutes lets his team spend its time refining, not starting from a blank page.
- **Dana, an investor evaluating a pitch**, currently green-lights decisions on incomplete visual information from text alone. A clickable previs app in a pitch meeting communicates tone and pacing a script cold cannot.

The concrete comparison across all three: **weeks of storyboard-artist time and multi-hundred-dollar-per-scene cost, versus minutes and the cost of a few LLM calls.**

## Quality of the Idea

The market-gap analysis in [`docs/01-PRD.md`](01-PRD.md) §6 is the case for why this specific combination doesn't exist elsewhere: traditional storyboard artists are slow and non-interactive; static AI image tools (Midjourney/DALL-E used ad hoc) have no script understanding or deployment step; desktop previs software (ShotPro, FrameForge) never produces a shareable web artifact; script-breakdown tools (Scenechronize, StudioBinder) stop at structured spreadsheets and never produce anything visual. Nothing in this space closes the full loop from raw script text to a deployed, interactive, navigable app autonomously — that full-loop autonomy, an agent system that actually writes and ships working software rather than producing an intermediate artifact a human still has to build from, is the white space SceneCraft occupies.
