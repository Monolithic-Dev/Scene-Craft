# SceneCraft — Phase 6 infrastructure. See infra/README.md for the
# apply/teardown workflow and cost notes before running `terraform apply`
# for real (this repo only runs `validate`/`plan` by default — see that
# README for why the actual apply is a deliberate, separately-triggered
# step).
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    grafana = {
      source  = "grafana/grafana"
      version = "~> 3.0"
    }
  }
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
    "redis.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
    "vpcaccess.googleapis.com",
    "compute.googleapis.com",
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
