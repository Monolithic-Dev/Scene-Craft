# SceneCraft Infrastructure (Phase 6)

`infra/terraform/` provisions the production architecture described in
`docs/02-TECH-STACK.md` and `docs/10-DIAGRAMS.md` §8: three Cloud Run
services (API, web, agent workers), Cloud SQL, Pub/Sub, Cloud Storage,
Secret Manager, Artifact Registry, and IAM. This document covers what's
actually applied, what only you can set up (external accounts), the
gotchas that cost real debugging time getting there, and cost.

## Staging is live

As of 2026-09-03, `staging` is genuinely deployed and verified — not just
`terraform plan`-clean:

- API: https://scenecraft-staging-api-fq6tp4iyja-uc.a.run.app
- Web: https://scenecraft-staging-web-fq6tp4iyja-uc.a.run.app
- Agents (Pub/Sub push target, not for direct browsing): https://scenecraft-staging-agents-fq6tp4iyja-uc.a.run.app

Live-verified: real signup/login issuing a real JWT against real Cloud SQL,
auth-required and cross-user-403 checks against the live API (see
`docs/Phases/PHASE-06-SECURITY-REVIEW.md`), non-wildcard CORS, and the
actual rendered login page at the web URL. Not yet live-exercised: a full
script-upload-to-previs run through the deployed Pub/Sub → Agent Workers
path (the code path is identical to what Phases 2-5 verified locally
end-to-end; only the transport differs) — worth doing once during Phase 7
demo rehearsal, mindful of the Gemini free-tier's 20/day quota.

**Known cosmetic drift**: `terraform plan` against staging shows all three
Cloud Run services wanting to change `scaling.manual_instance_count` (`0`
→ `null`) every time — this is the GCP provider echoing back a computed
default we never set in config; applying it is a no-op for actual scaling
behavior (still governed correctly by `min_instance_count`/
`max_instance_count`). Not worth suppressing with an `ignore_changes`
lifecycle block for a hackathon-scale deployment; just don't be alarmed by
a non-zero plan diff on this specific field.

## Redis: Upstash, not Cloud Memorystore

Memorystore's cheapest tier still bills ~$35/mo continuously and is
VPC-only. Given a preference for free/open options wherever the tradeoff
is reasonable, Redis here is a free external **[Upstash](https://upstash.com)**
instance instead — no card required, 256MB/500K commands per month free.
Because `REDIS_URL` is just a connection string, this required no
application code changes, and removing Memorystore also removed the need
for a VPC entirely (Cloud SQL already reaches Cloud Run via its own Auth
Proxy sidecar, not a private network path) — `network.tf` and `redis.tf`
don't exist in this repo for that reason.

**Setup**: create a free database at console.upstash.com (Global or
nearest region, Free plan), copy its `rediss://` TCP connection string,
and set it as `TF_VAR_redis_url`.

## Gotchas found during the first real deploy

Every item below is a real failure hit live, not a hypothetical — each one
cost real debugging time because it's invisible to `terraform validate`
and `terraform plan`, and most are invisible to local testing too.

**Next.js `NEXT_PUBLIC_*` variables are inlined at `next build` time, not
read from the environment at container runtime.** `apps/web/lib/api.ts`
(and `lib/firebase.ts`) are used from client components, so setting
`NEXT_PUBLIC_API_BASE_URL`/`NEXT_PUBLIC_FIREBASE_*` as plain Cloud Run env
vars — which an earlier version of this Terraform did — silently has zero
effect on the deployed app; the browser would still call whatever was
baked in at image-build time (`localhost:8000` by default). Fixed by
making them Docker **build args** instead (`apps/web/Dockerfile`) — see
"Building images" below for the actual build command.

**A Cloud Run service that fails its first revision (e.g. because the
image doesn't exist yet in Artifact Registry) gets marked `tainted` in
Terraform state**, and `google_cloud_run_v2_service` defaults to
`deletion_protection = true`. A tainted resource is always destroyed and
recreated on the next apply — but you can't change `deletion_protection`
to `false` and destroy the resource in the same apply, so the error reads
"cannot destroy service without setting deletion_protection=false" even
after you've already added that line to the config. Fix: `terraform
untaint <resource>` first, then re-apply — this Terraform now sets
`deletion_protection = false` on all three Cloud Run services explicitly
(they're stateless and disposable, unlike Cloud SQL), so this shouldn't
recur, but the failure mode is worth knowing if a future deploy fails
mid-creation for any other reason (a bad env var, a missing secret, etc.).

**A directory-depth assumption in application code that only breaks
inside the container.** `apps/api/src/core/agent_runner.py` had a
module-level constant computed via `Path(__file__).resolve().parents[4]`
— correct in the local checkout (`apps/api/src/core/` is 4 levels below
repo root), but `apps/api/Dockerfile`'s `COPY src ./src` flattens the
layout to 3 levels inside the image, so `parents[4]` raised an uncaught
`IndexError` at **import time**, crashing the entire app before it could
serve a single request. `terraform validate`/`plan` can't catch this —
only an actual container boot does. Fixed by making the computation lazy
and exception-safe (see that file's `_default_agents_dir()`), with a
regression test in `apps/api/tests/test_agent_runner.py`. Worth grepping
any codebase for `Path(__file__).resolve().parents[N]` before a first real
container deploy — it's an easy pattern to write correctly for local dev
and never notice it's wrong until the container layout differs.

**Terraform's implicit dependency graph doesn't know a `secret_key_ref`
needs its IAM binding or its secret *version* to exist first.**
`google_cloud_run_v2_service.api`'s `env { value_source { secret_key_ref {
secret = google_secret_manager_secret.X.secret_id } } }` references the
secret *container* resource's ID, not the IAM-member or secret-version
resources — so neither is an implied dependency, and a `-target`-scoped
apply of just the Cloud Run service silently skips creating both. Symptoms
seen live: `Permission denied on secret ... /versions/latest` (missing
IAM binding), then `Secret ... was not found` (container existed, zero
versions in it — the version resource itself was never applied). Fixed
with explicit `depends_on` listing every `google_secret_manager_secret_iam_member`
and `google_secret_manager_secret_version` each service actually reads —
see `cloud_run.tf`'s `depends_on` blocks and their comments. The same gap
existed for `google_sql_user`/`google_sql_database` (real auth failure:
`password authentication failed for user "scenecraft"` — the user simply
didn't exist yet) and for the public-invoker IAM binding on `api`/`web`
(symptom: a Google-branded 404 page instead of the app, because the
request never reached the container at all). **Lesson: prefer a full,
untargeted `terraform apply` over chained `-target` runs whenever
possible** — targeting is exactly what lets these gaps hide, which is also
what Terraform's own `-target` warning says and is easy to dismiss as
boilerplate until it bites.

**IAM changes take real time to propagate, even after the API reports
success.** A `google_secret_manager_secret_iam_member` can show `Creation
complete` and still not be visible to a Cloud Run revision starting up
seconds later — hit this twice, requiring a ~1-2 minute wait before a
retry succeeded. Not a bug to fix, just budget for it when a deploy fails
immediately after a fresh IAM grant with a permission-denied error that
makes no sense given the binding you can see with `gcloud ... get-iam-policy`.

**The Pub/Sub service agent doesn't exist in a project until something
explicitly provisions it.** Granting `roles/pubsub.publisher`/`subscriber`
to `service-<project-number>@gcp-sa-pubsub.iam.gserviceaccount.com` (for
the dead-letter topic) failed with "Service account ... does not exist"
on a genuinely from-scratch project, even though that identity is
normally auto-created early in a project's life. Fixed with an explicit
`google_project_service_identity` (`google-beta` provider — not yet in
the stable `google` provider) that `depends_on` gates the two IAM
bindings that need it — see `pubsub.tf`.

**A 1.2GB web image over an unreliable local connection never finishes
pushing.** `apps/web/Dockerfile` copies the full `node_modules` into the
final image rather than using Next.js's `output: "standalone"` trace-based
pruning, so the built image is far larger than it needs to be — combined
with real IPv6 timeouts on this network reaching Artifact Registry (also
hit, smaller-scale, on the ~170MB API image earlier), a local `docker
push` of the web image hung indefinitely with zero byte-progress for
several minutes even after two clean retries. Worked around by building
+ pushing via **Cloud Build** instead (`gcloud builds submit --config
cloudbuild.yaml`, entirely within GCP's own network, no local upload of
the image at all) — genuinely more robust for a large image regardless of
local network quality, and closer to what `deploy.yml`'s CI pipeline does
anyway. A real local `.dockerignore`/`.gcloudignore` (both now present in
`apps/web/`) matters too — without them, the *build context* itself
included the host's own `node_modules` (770MB+, Windows-native binaries
that don't even run in the Linux container), not just the final image.
Genuine follow-up, not done here: switch `apps/web`'s `next.config` to
`output: "standalone"` and rewrite the Dockerfile's runner stage around
it — would cut the image from ~1.2GB to closer to ~150-200MB and make a
local `docker push` viable again.

## One-time account setup only you can do

**Grafana Cloud** (for the 3 dashboards in `infra/grafana/dashboards/` and
the OTel trace/metric export configured in `apps/api/src/core/telemetry.py`
and `agents/shared/telemetry.py`) — optional, everything else works
without it:

1. Create a free account at grafana.com — the free tier (10k active
   series, 50GB traces/logs) is generous enough for a hackathon-scale
   system; this is why Grafana Cloud was chosen over self-hosting
   Grafana+Tempo+Mimir on Cloud Run ourselves, which would mean 2-3 more
   persistent, billed services for zero functional gain.
2. From your stack's details page, copy the OTLP gateway URL and generate
   an API token with metrics/traces/logs write scope.
3. Set Terraform variables `grafana_enabled=true`, `grafana_url`, and
   `grafana_api_key` to provision the 3 dashboards via `grafana.tf`, and
   set `OTEL_EXPORTER_OTLP_ENDPOINT`/`OTEL_EXPORTER_OTLP_HEADERS` as
   secrets consumed by `apps/api`/`agents`.

Without this, spans/metrics are still created (see the "stays honestly
unconfigured" pattern in both `telemetry.py` modules) but never exported —
nothing breaks, the judge-facing panel just has nothing to show.

**Workload Identity Federation** (for `.github/workflows/deploy.yml`): a
one-time setup (`infra/terraform/wif.tf`) so GitHub Actions can
authenticate to GCP without a long-lived JSON key in a repo secret. Apply
`wif.tf`'s resources, then set the two output values as repo secrets:
`GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`.

**Repo secrets `deploy.yml` needs, per environment** (Settings → Secrets
and variables → Actions, scoped to the `staging`/`production` GitHub
Environments so production's real credentials are never visible to a
staging deploy): `TF_VAR_DB_PASSWORD`, `TF_VAR_JWT_SECRET_KEY`,
`TF_VAR_INTERNAL_SERVICE_KEY`, `TF_VAR_GEMINI_API_KEY`,
`TF_VAR_REDIS_URL` (an Upstash `rediss://` URL — see above; staging and
production need their own separate Upstash database, not a shared one),
each suffixed `_PROD` for the production environment's versions.

**`deploy.yml` builds `web` separately per environment, not once and
shared** — see `infra/terraform/variables.tf`'s `web_image_tag` and the
"Next.js `NEXT_PUBLIC_*`" gotcha above for why: the API URL gets baked
into the JS bundle at build time, and staging/production have different
API URLs, so "build once, promote the same image through environments"
(normally a CI/CD best practice) doesn't hold for this one service. Each
environment's job applies Terraform twice — once to get `api`'s stable
URL, then again after building `web` against that URL.

## Building images

```bash
SHA=$(git rev-parse --short HEAD)
REGISTRY="us-central1-docker.pkg.dev/<project-id>/scenecraft"

docker build -t "$REGISTRY/api:$SHA" -t "$REGISTRY/api:latest" -f apps/api/Dockerfile apps/api

docker build -t "$REGISTRY/agents:$SHA" -t "$REGISTRY/agents:latest" -f agents/Dockerfile .   # repo-root context — see agents/Dockerfile

# web needs the real API URL as a build arg (see the gotcha above) — apply
# the api service first, read its URL from `terraform output api_url`, then:
docker build \
  --build-arg NEXT_PUBLIC_API_BASE_URL=<api_url output> \
  --build-arg NEXT_PUBLIC_FIREBASE_API_KEY=... \
  --build-arg NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=... \
  --build-arg NEXT_PUBLIC_FIREBASE_PROJECT_ID=... \
  --build-arg NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=... \
  --build-arg NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=... \
  --build-arg NEXT_PUBLIC_FIREBASE_APP_ID=... \
  -t "$REGISTRY/web:$SHA" -t "$REGISTRY/web:latest" -f apps/web/Dockerfile apps/web

docker push "$REGISTRY/api:$SHA"    && docker push "$REGISTRY/api:latest"
docker push "$REGISTRY/agents:$SHA" && docker push "$REGISTRY/agents:latest"
docker push "$REGISTRY/web:$SHA"    && docker push "$REGISTRY/web:latest"
```

(`deploy.yml` automates all of this per push to `main` — this is the
manual equivalent for a first apply or a local rebuild.)

## Applying

```bash
cd infra/terraform
terraform init
export TF_VAR_db_password=$(openssl rand -base64 24)
export TF_VAR_jwt_secret_key=$(openssl rand -base64 32)
export TF_VAR_internal_service_key=$(openssl rand -base64 32)
export TF_VAR_gemini_api_key=<your real key>
export TF_VAR_redis_url=<your Upstash rediss:// connection string>
terraform apply -var-file=staging.tfvars   # or dev.tfvars / prod.tfvars
```

The Firestore database already exists (created manually in Phase 5, before
any of this Terraform existed) — import it into state before applying,
once, per environment that targets the real project:

```bash
terraform import google_firestore_database.default \
  "projects/<project-id>/databases/(default)"
```

Artifact Registry needs to exist (and images pushed into it) before the
Cloud Run services can be created — target-apply it first if doing a
from-scratch apply:

```bash
terraform apply -var-file=staging.tfvars -target=google_artifact_registry_repository.images
# ... build and push images (see above) ...
terraform apply -var-file=staging.tfvars -target=google_cloud_run_v2_service.api
# ... build the web image using the real api_url output (see above) ...
terraform apply -var-file=staging.tfvars   # everything else: web, agents, Pub/Sub subscription, IAM
```

**CORS bootstrapping**: `api`'s `ALLOWED_ORIGINS` and the web build's
`NEXT_PUBLIC_API_BASE_URL` are mutually referential — a real dependency
cycle if wired directly to each other's `.uri` attribute. First apply
falls back to `http://localhost:3000` for CORS (`var.web_allowed_origin`
defaults empty); after `web` exists, re-apply with `-var
web_allowed_origin=<web_url output>` to tighten it to the real deployed
frontend origin — this only touches the API service's env vars.

## Cost (staging/prod, if left running)

| Resource | Approx. monthly cost if always-on |
|---|---|
| Cloud SQL (`db-f1-micro`, dev/staging) | ~$10-15 |
| Redis (Upstash free tier) | $0 |
| Cloud Run (min_instances=0) | ~$0 idle, pay-per-request only |
| Cloud Run (min_instances=1, api only) | ~$15-20 additional |
| Artifact Registry / Cloud Storage / Pub/Sub / Secret Manager | Low single digits, usage-based |

Cloud SQL is the only line item that bills whether or not anyone is using
the app — everything else scales to zero or is free-tier. Tear down a
throwaway environment with `terraform destroy -var-file=<env>.tfvars`
(same `TF_VAR_*` exports as above).

## Known gaps (documented, not silently skipped)

- `agents/shared/storage.py` still writes to `agents/.local_storage/`
  rather than the `google_storage_bucket.frames` bucket this Terraform
  provisions — the bucket and its IAM scoping exist and are ready, but the
  code swap is a follow-up, not a blocker.
- `token_usage`/`tool_calls_count` span attributes from
  `PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md` §1 are omitted — no
  agent result currently threads that data back to the Coordinator (see
  `agents/shared/telemetry.py`'s `agent_span()` docstring).
