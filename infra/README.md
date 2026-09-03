# SceneCraft Infrastructure (Phase 6)

`infra/terraform/` provisions the full production architecture described in
`docs/02-TECH-STACK.md` and `docs/10-DIAGRAMS.md` §8: three Cloud Run
services (API, web, agent workers), Cloud SQL, Memorystore (Redis),
Pub/Sub, Cloud Storage, Secret Manager, Artifact Registry, and IAM. This
document covers what this repo's CI does and does not do automatically,
account setup you need to do yourself, and cost.

## What's applied automatically vs. deliberately not

This repo's own CI (`ci.yml`) only runs `terraform validate`/`fmt -check`.
The `deploy.yml` workflow (`feat/phase-6c-cicd-deploy-pipeline`) runs
`terraform apply` against staging on every merge to `main`, and against
production behind a manual approval gate — but **as of this PR, that
pipeline has not yet been triggered for a real apply**. Cloud SQL,
Memorystore, and non-zero `min_instances_api` all bill continuously once
actually applied, unlike the per-call Gemini/Firestore usage this project
relied on through Phase 5 — so standing up a live environment is a
deliberate, explicit step, not something that happens just by merging
Terraform code. See "Cost" below, then either run the commands under
"Applying by hand" yourself, or ask for it to be triggered once you're
ready (ideally close to Phase 7 demo prep, to minimize how long it bills
before it's actually needed).

`terraform plan` (read-only, creates nothing) has been run against the
real `scene-craft-507404` project as part of writing this Terraform — 56
resources, no errors, no warnings. That's the extent of what's been done
against real infrastructure so far.

## One-time account setup only you can do

**Grafana Cloud** (for the 3 dashboards in `infra/grafana/dashboards/` and
the OTel trace/metric export configured in `apps/api/src/core/telemetry.py`
and `agents/shared/telemetry.py`):

1. Create a free account at grafana.com — the free tier (10k active
   series, 50GB traces/logs) is generous enough for a hackathon-scale
   system; this is why Grafana Cloud was chosen over self-hosting
   Grafana+Tempo+Mimir on Cloud Run ourselves, which would mean 2-3 more
   persistent, billed services for zero functional gain.
2. From your stack's details page, copy the OTLP gateway URL and generate
   an API token with metrics/traces/logs write scope.
3. Set on `apps/api` and `agents` (locally via `.env`, in Cloud Run via
   Terraform's Secret Manager wiring):
   ```
   OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-<region>.grafana.net/otlp
   OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64(instance_id:api_key)>
   ```
4. Set Terraform variables `grafana_enabled=true`, `grafana_url` (your
   stack's Grafana URL, e.g. `https://<stack>.grafana.net`), and
   `grafana_api_key` (a separate API token with dashboard write scope) to
   provision the 3 dashboards via `grafana.tf`.

Without this, spans/metrics are still created (see the "stays honestly
unconfigured" pattern in both `telemetry.py` modules) but never exported —
nothing breaks, the judge-facing panel just has nothing to show.

**Workload Identity Federation** (for `deploy.yml` — see
`feat/phase-6c-cicd-deploy-pipeline`'s own docs when that PR lands): a
one-time `gcloud iam workload-identity-pools` setup so GitHub Actions can
authenticate to GCP without a long-lived JSON key in a repo secret.

## Applying by hand

```bash
cd infra/terraform
terraform init
export TF_VAR_db_password=$(openssl rand -base64 24)
export TF_VAR_jwt_secret_key=$(openssl rand -base64 32)
export TF_VAR_internal_service_key=$(openssl rand -base64 32)
export TF_VAR_gemini_api_key=<your real key>
terraform apply -var-file=dev.tfvars   # or staging.tfvars / prod.tfvars
```

The Firestore database already exists (created manually in Phase 5, before
any of this Terraform existed) — import it into state before applying,
once, per environment that targets the real project:

```bash
terraform import google_firestore_database.default \
  "projects/scene-craft-507404/databases/(default)"
```

**CORS bootstrapping**: `api`'s `ALLOWED_ORIGINS` and `web`'s
`NEXT_PUBLIC_API_BASE_URL` are mutually referential Cloud Run URLs — a real
Terraform dependency cycle if both were wired directly to each other's
`.uri` attribute (see `cloud_run.tf`'s comment). First apply falls back to
`http://localhost:3000` for CORS; after it completes, read the `web_url`
output and re-apply with `-var web_allowed_origin=<that URL>` to tighten
it to the real deployed frontend. A second apply only touches the API
service's env vars.

**Firebase Web SDK config** (`NEXT_PUBLIC_FIREBASE_*`) isn't templated by
Terraform — set it once via `gcloud run services update` after the web
service exists, using `firebase apps:sdkconfig WEB <app-id> --project
scene-craft-507404` (same values already in local `.env.local`, not
secret — see `apps/web/lib/firebase.ts`).

## Cost (staging/prod, if left running)

| Resource | Approx. monthly cost if always-on |
|---|---|
| Cloud SQL (`db-f1-micro`, dev/staging) | ~$10-15 |
| Memorystore Basic 1GB | ~$35 |
| Cloud Run (min_instances=0) | ~$0 idle, pay-per-request only |
| Cloud Run (min_instances=1, api only) | ~$15-20 additional |
| Artifact Registry / Cloud Storage / Pub/Sub / Secret Manager | Low single digits, usage-based |

Cloud SQL and Memorystore are the two line items that bill whether or not
anyone is using the app — everything else scales to zero. Tear down a
throwaway environment with `terraform destroy -var-file=<env>.tfvars`
(same `TF_VAR_*` exports as above).

## Known gaps (documented, not silently skipped)

- `agents/shared/storage.py` still writes to `agents/.local_storage/`
  rather than the `google_storage_bucket.frames` bucket this Terraform
  provisions — the bucket and its IAM scoping exist and are ready, but the
  code swap wasn't in this PR's scope. Follow-up, not a blocker for the
  rest of Phase 6.
- `token_usage`/`tool_calls_count` span attributes from
  `PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md` §1 are omitted — no
  agent result currently threads that data back to the Coordinator (see
  `agents/shared/telemetry.py`'s `agent_span()` docstring).
- Security-review checklist items that require a live deployed target
  (re-running Phase 1 auth/ownership tests against staging, the IAM
  boundary verification scripts) are deferred until this Terraform is
  actually applied — see `feat/phase-6c-cicd-deploy-pipeline`.
