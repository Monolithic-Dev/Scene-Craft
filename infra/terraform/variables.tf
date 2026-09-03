variable "project_id" {
  type        = string
  description = "GCP project ID, e.g. scene-craft-507404."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Single-region deployment — sufficient for a hackathon-scale system; see infra/README.md for the multi-region non-goal."
}

variable "environment" {
  type        = string
  description = "dev | staging | prod — used in resource names and to gate prod-only settings (deletion_protection, backup retention, instance sizing)."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "github_repository" {
  type        = string
  default     = "Monolithic-Dev/Scene-Craft"
  description = "owner/repo — scopes Workload Identity Federation (wif.tf) so only this exact repo's GitHub Actions runs can authenticate as the deployer service account."
}

variable "container_image_tag" {
  type        = string
  default     = "latest"
  description = "Git SHA (preferred) or tag identifying which Artifact Registry image to deploy for api/agents — set by deploy.yml per build. Built once and shared across environments, since neither service bakes environment-specific values in at build time."
}

variable "web_image_tag" {
  type        = string
  default     = "latest"
  description = <<-EOT
    Separate from container_image_tag on purpose: Next.js inlines
    NEXT_PUBLIC_* values (API URL, Firebase config) into the JS bundle at
    build time (see apps/web/Dockerfile), so a single web image cannot be
    correct for both staging and production — each environment needs its
    own build with its own baked-in API URL. deploy.yml builds and tags a
    web image per environment (e.g. "<sha>-staging", "<sha>-prod") and
    passes the matching tag here.
  EOT
}

variable "web_allowed_origin" {
  type        = string
  default     = ""
  description = <<-EOT
    The web service's own URL, for the API's CORS allow-list. Left empty on
    a first apply (api and web's Cloud Run URLs are mutually referential —
    setting this from google_cloud_run_v2_service.web.uri directly would be
    a dependency cycle Terraform refuses to plan) — falls back to
    http://localhost:3000 until set. After the first apply, read the
    web_url output and pass it back via -var web_allowed_origin=<that URL>
    (or set it in the environment's .tfvars) to tighten CORS to the real
    deployed frontend origin; a second apply only touches the api service's
    env vars, nothing else.
  EOT
}

variable "min_instances_api" {
  type        = number
  default     = 0
  description = "Cloud Run min instances for the API service. 0 = scale to zero between demos (cheapest); set >=1 only right before a judged demo to avoid cold-start latency."
}

# --- Secrets (never given real values in any committed .tfvars — see
# infra/README.md for how CI injects these via TF_VAR_* from GitHub
# Actions secrets, and dev.tfvars.example for the local-apply equivalent). ---

variable "db_password" {
  type      = string
  sensitive = true
}

variable "jwt_secret_key" {
  type      = string
  sensitive = true
}

variable "internal_service_key" {
  type      = string
  sensitive = true
}

variable "gemini_api_key" {
  type      = string
  sensitive = true
}

# Full redis:// connection string from a free external provider (Upstash —
# see infra/README.md) rather than Cloud Memorystore: Memorystore's cheapest
# tier still bills ~$35/mo continuously, and is VPC-only (which is what
# network.tf/redis.tf existed for before this swap) — a free managed Redis
# with a public TLS endpoint needs no VPC at all, since Cloud Run reaches it
# directly over the internet like it already does for Gemini/Cloud SQL's
# Auth Proxy.
variable "redis_url" {
  type      = string
  sensitive = true
}

# --- Grafana Cloud (optional — see infra/README.md) -------------------------

variable "grafana_enabled" {
  type        = bool
  default     = false
  description = "Requires a Grafana Cloud account (free tier) you create yourself — see infra/README.md. false leaves dashboards unprovisioned without affecting the rest of the stack."
}

variable "grafana_url" {
  type    = string
  default = ""
}

variable "grafana_api_key" {
  type      = string
  default   = ""
  sensitive = true
}
