# SceneCraft — Phase 7 Build Spec: Demo Polish & Submission Materials

> Read `PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md` (must be complete and passing first), `01-PRD.md` §1–2, and the hackathon's actual submission requirements (Devpost overview page) before starting. **This phase is not an afterthought — judges only ever see the artifacts this phase produces. A brilliant system with a weak demo video loses to a good system with a great one.**

## Objective

Turn a working, deployed system into a complete, judge-ready submission: a repo a stranger can clone and run, documentation that explains the architecture without requiring a live walkthrough, and a 3-minute demo video that actually shows the thing working end to end.

## Scope

**In scope:** README finalization, judge guide, demo script + recording, pitch materials, final repo hygiene (license visibility, no stray secrets/artifacts), Devpost submission form content.
**Out of scope:** any new functionality — if the demo reveals a bug, fix it as a proper commit against the phase it belongs to, then return here. Don't patch bugs directly in this phase's scope creep.

---

## 1. Submission Requirements Checklist (from the hackathon rules — verify each explicitly)

- [ ] Hosted URL to the live project
- [ ] 3-minute demo video: shows the **actual product functioning**, not a cinematic trailer — uploaded to YouTube or Vimeo, publicly visible, in English or with English subtitles
- [ ] Public open-source repository containing all source code, assets, and instructions needed to run it, demonstrating actual runtime use of Google Cloud (Gemini/Vertex AI imported and called in code, not merely named in the README) — Replit's requirement is structurally different (build-process + hosting, not a runtime call): verify separately that the live URL is genuinely `replit.app`/`replit.dev` and that the PR from a real Replit Agent session (`PHASE-04-APP-BUILD-AND-CRITIC.md` §5b) is in the repo's history
- [ ] A complete open-source license file, detectable and visible at the top of the repo (GitHub's "About" section license badge)
- [ ] Partner track selected in the Devpost submission form (**Replit**)
- [ ] Completed Devpost submission form
- [ ] Compliance confirmed against the full Official Rules (read them once yourself, don't rely solely on this checklist — rules can be updated)

## 2. README (final pass)

The Phase 1 README gets a final rewrite for a judge audience, not a contributor audience — assume the reader has 90 seconds before moving to the next submission. Structure:
1. **One-sentence pitch** at the very top, above the fold.
2. **A GIF or screenshot** of the deployed previs app — judges skim visually first.
3. **"How it works"** — 3–4 sentences, not a re-paste of the full system design.
4. **Live demo link** and **demo video link**, prominently placed, not buried after installation instructions.
5. **Architecture diagram** (pull the high-level one from `10-DIAGRAMS.md` §1) — a static image judges see without clicking anything.
6. **Tech stack** — a compact list, linking to `docs/02-TECH-STACK.md` for depth rather than repeating it in full.
7. **Local setup instructions** — kept, but below the fold; a judge evaluating quickly shouldn't need them, but the repo must still hold up if they do.
8. **License** section, matching the visible license file.

## 3. Judge Guide (`docs/judge-guide.md`)

A short document answering, explicitly, the exact four judging criteria from the hackathon (Technological Implementation, Design, Potential Impact, Quality of the Idea) — one paragraph each, pointing to specific evidence:
- **Technological Implementation:** point to the multi-agent architecture (`04-AGENT-ARCHITECTURE.md`), the App-Build/Critic Agent's constrained-codegen design (`PHASE-04-APP-BUILD-AND-CRITIC.md` §1) as the genuine differentiator, the honest handling of the Replit build+host requirement (§0/§5 of the same doc), and the observability/security work from Phase 6.
- **Design:** point to the deployed previs app itself and the live agent-trace UI — a complete product experience, not a bare API.
- **Potential Impact:** point to the specific personas in `01-PRD.md` §5 and the concrete cost/time comparison (weeks of storyboard-artist time vs. minutes).
- **Quality of the Idea:** point to the market-gap analysis in `01-PRD.md` §6 — why this specific combination (script understanding + autonomous app deployment) doesn't exist elsewhere.

This document exists because judges review many submissions quickly — making the mapping from "what we built" to "what you're scoring" explicit is a courtesy that measurably helps, not a gimmick.

## 4. Demo Script & Recording

**Timing budget for a 3-minute video** (adjust but keep the shape — don't let setup eat the runtime):
| Segment | Duration | Content |
|---|---|---|
| Hook | 0:00–0:15 | The problem in one sentence, stated over a shot of a blank page/script — "This is every indie director's starting point. Here's what SceneCraft does with it." |
| Upload → Breakdown | 0:15–0:45 | Real script upload, live agent-trace panel showing the Breakdown Agent working |
| Frames | 0:45–1:15 | Storyboard frames appearing, style consistency visible across shots |
| App-Build (the centerpiece) | 1:15–2:00 | The App-Build Agent generating the previs content live, the Critic Agent's verification pass visible in the trace panel, a quick click-through of the navigable previs app running on the `replit.app` URL |
| Iteration | 2:00–2:40 | Type a plain-English edit, watch the trace panel, show the redeployed app reflecting the change |
| Close | 2:40–3:00 | One sentence on impact/audience, the deployed URL and repo link on screen |

**Recording practices:**
- Use a real script, not a toy one-liner — a thin demo input undersells the breakdown agent's actual capability.
- Rehearse against the **actual deployed staging/production environment** from Phase 6, not localhost — timing and reliability differ, and judges may click through to the live URL themselves afterward.
- If the App-Build/Critic generation step takes more than a couple seconds on camera, either genuinely wait it out with a brief voiceover explaining what's happening, or use a clearly-labeled speed-up cut — don't hide a hard cut as if it were real-time, since the rules require the video to show the product actually functioning.
- Captions/subtitles in English, per the submission requirement, even if the narration is already in English — don't skip this.

## 5. Pitch Materials

A short slide set (5–7 slides) covering: problem, solution, live demo screenshot, architecture at a glance, why Replit specifically, impact/audience, ask (if presenting live to judges beyond the recorded video). Keep this visually consistent with the deployed app's own design language (the charcoal/signal-amber direction from the frontend, if you followed `02-TECH-STACK.md`/earlier UI work) rather than a generic corporate deck template — visual consistency between the product and the pitch is a small thing that reads as polish.

## 6. Final Repo Hygiene

- [ ] License file present at repo root, GitHub correctly detects and displays it in the About section
- [ ] `.gitignore` verified against a fresh `git status` — no `node_modules`, `.next`, `__pycache__`, `.db` files, or `.env` accidentally tracked
- [ ] `git log` reviewed for any accidentally committed secret at any point in history (a secret removed in a later commit is still in git history — if this happened, rotate the credential, don't just delete the line)
- [ ] Every phase's commit messages present and accurately describing what they contain (per the convention in `09-CODING-STANDARDS.md` §6) — a judge skimming commit history should see the same phase structure this documentation set describes
- [ ] CI badge in the README actually reflects the current build status, not a stale green badge from three phases ago
- [ ] Repo set to public, confirmed by checking it in an incognito/logged-out browser

## 7. Devpost Submission Form Content

Prepare these in advance, not while the form is open (avoids rushed, weaker copy):
- Project name and one-line tagline
- Full description (pull from `01-PRD.md` §1–2, condensed)
- "Built with" technology tags — list Gemini, Vertex AI, Agent Builder/ADK, Cloud Run, Firestore, BigQuery, Replit explicitly (accurate tagging affects discoverability and judge expectations)
- Partner track selection: **Replit**
- Links: hosted app, demo video, repo

## 8. Final Verification Pass (do this last, after everything else)

- [ ] Clone the repo fresh into an empty directory and follow only the README to get it running locally — if this fails, fix the README or the code, not just your memory of how it's supposed to work
- [ ] Click every link that will appear in the Devpost submission (live app, video, repo) from a logged-out, incognito session
- [ ] Watch the full demo video once, uninterrupted, with sound, as if seeing it for the first time
- [ ] Re-read the Official Rules once more against the checklist in section 1 — this is cheap insurance against a disqualifying oversight this late

## Definition of Done

- [ ] All Phase 1–6 checks still pass
- [ ] Every item in section 1's submission requirements checklist is checked
- [ ] The judge guide maps all four judging criteria to concrete evidence
- [ ] The demo video is recorded, uploaded, publicly visible, captioned, and within the time limit
- [ ] A fresh clone + README-only setup succeeds
- [ ] The Devpost form is fully drafted and ready to submit before the deadline, not assembled in the final minutes

## Common Pitfalls

1. **Recording the demo against localhost the night before, then discovering staging behaves differently** — rehearse against the real deployed environment early enough in this phase to catch discrepancies with time to fix them.
2. **A demo video that explains the architecture instead of showing the product working** — the rules are explicit that this must show actual functioning, not a slide-narrated trailer. Show clicks, show the trace panel, show the deployed app — narrate over it, don't replace it with slides.
3. **Treating the judge guide as redundant with the README** — they serve different readers at different moments; the judge guide's job is specifically to connect your work to the scoring rubric, which the README doesn't need to do.
4. **Discovering a stale secret in git history at the last minute** — this is exactly why section 6's history check happens *before* the final push, not as a surprise during judge review.

## Commit Message
`docs(phase-7): submission documentation and demo materials`

---

## You've now completed all 7 phases

At this point, per `08-IMPLEMENTATION-PLAN.md`, every phase's Definition of Done should be checked, the full system should be live, and the submission should be ready. If you're returning to this doc set mid-build and something doesn't match what you've actually built, treat the docs as the spec to reconcile toward — not as stale artifacts to ignore.
