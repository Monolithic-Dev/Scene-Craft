# Devpost Submission Content (draft)

Prepared in advance per [`docs/Phases/PHASE-07-DEMO-AND-SUBMISSION.md`](Phases/PHASE-07-DEMO-AND-SUBMISSION.md) §7 — copy into the form, don't compose live.

## Project name
SceneCraft

## Tagline (one line)
A script goes in. A working, deployed previs app comes out — in minutes.

## Full description

A script is the only artifact every filmmaker has on day one, and the hardest one for anyone outside the writer's head to *see*. SceneCraft is a multi-agent system that reads an uploaded script, breaks it into scenes and shots, generates storyboard-quality concept frames per shot, and autonomously builds and deploys an interactive previs web app from that data — verified by an independent Critic Agent before it's ever shown as done. A director can then click through the result and request changes in plain English ("make scene 4 night-time") and watch a live agent-trace panel show the rebuild happen in real time.

Five agents (Breakdown, Frame Generation, App-Build, Critic, Iteration) communicate through a real MCP server boundary — no agent ever touches the database directly. The App-Build Agent is deliberately *not* an unconstrained code-generation system: it fills in a fixed, pre-tested app shell from a deterministic data layer, with exactly one bounded, schema-validated LLM call for presentation-only styling — constrained, verifiable generation over a hope that the model got it right.

Built on Google Cloud (Gemini, Vertex AI, Cloud Run, Cloud SQL, Firestore, Pub/Sub, Secret Manager, full Terraform-provisioned production architecture with OpenTelemetry/Grafana observability and least-privilege IAM) and hosted on Replit per the partner track's actual requirement — Replit Agent as part of the build process, a real `replit.app` deployment kept in sync via the `repl.deploy` GitHub Action.

## "Built with" tags
`Gemini` · `Vertex AI` · `Google Cloud Run` · `Cloud SQL` · `Firestore` · `Pub/Sub` · `Cloud Storage` · `Secret Manager` · `Terraform` · `OpenTelemetry` · `Grafana` · `FastAPI` · `Next.js` · `TypeScript` · `Model Context Protocol (MCP)` · `Replit`

## Partner track
**Replit**

## Links
- Hosted app: _[fill in — the live `replit.app`/`.dev` URL]_
- Demo video: _[fill in — YouTube/Vimeo link]_
- Repository: `https://github.com/Monolithic-Dev/Scene-Craft`

## Submission checklist cross-reference

See `docs/Phases/PHASE-07-DEMO-AND-SUBMISSION.md` §1 for the full hackathon-rules checklist this draft feeds into — this file only covers the form's own content fields, not the surrounding requirements (video captions, repo visibility, etc.), which are tracked there.
