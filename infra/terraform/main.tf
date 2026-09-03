# SceneCraft — Phase 6 infrastructure. See infra/README.md for the
# apply/teardown workflow and cost notes before running `terraform apply`
# for real (this repo only runs `validate`/`plan` by default — see that
# README for why the actual apply is a deliberate, separately-triggered
# step).
terraform {
  required_version = ">= 1.9"

  # Remote state in GCS — without this, every `terraform apply` (a local
  # one, or a fresh GitHub Actions runner in deploy.yml) starts from empty
  # state and tries to recreate everything that already exists. The bucket
  # itself is a one-time bootstrap (created via `gcloud storage buckets
  # create`, not by this Terraform — same chicken-and-egg category as the
  # Firestore import and Workload Identity Federation in wif.tf) with
  # versioning enabled so a corrupted state write is recoverable.
  backend "gcs" {
    bucket = "scene-craft-507404-tfstate"
    prefix = "scenecraft"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
    grafana = {
      source  = "grafana/grafana"
      version = "~> 3.0"
    }
  }
}

# google-beta is used for exactly one resource (google_project_service_identity
# in pubsub.tf, for the Pub/Sub service agent — not in the stable google
# provider as of this writing) — everything else deliberately stays on the
# stable provider.
provider "google-beta" {
  project = var.project_id
  region  = var.region
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Only actually contacted when grafana_enabled=true and real resources
# reference it (see grafana.tf) — declaring the provider unconditionally
# is required by Terraform even though most environments won't use it
# until a Grafana Cloud account exists (see infra/README.md).
provider "grafana" {
  url  = var.grafana_enabled ? var.grafana_url : "https://unconfigured.invalid"
  auth = var.grafana_enabled ? var.grafana_api_key : "unconfigured"
}

locals {
  name_prefix = "scenecraft-${var.environment}"

  required_apis = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudbuild.googleapis.com",
    "sts.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
