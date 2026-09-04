# Workload Identity Federation for .github/workflows/deploy.yml — GitHub
# Actions authenticates to GCP by exchanging its own OIDC token for short-
# lived GCP credentials, so no long-lived service account JSON key ever
# sits in a GitHub secret (the industry-standard replacement for that
# pattern; a leaked JSON key has no expiry, a leaked OIDC exchange config
# alone grants nothing without GitHub's own token issuance in the loop).
#
# This is inherently a bootstrapping resource: deploy.yml needs it to exist
# before it can authenticate, but it's provisioned by the same Terraform
# deploy.yml applies — so its first-ever creation has to happen via a local
# `terraform apply` (see infra/README.md), same one-time chicken-and-egg
# category as the Firestore import.
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "${local.name_prefix}-github"
  display_name              = "GitHub Actions (${var.environment})"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Scoped to this exact repository — any other GitHub repo's OIDC token,
  # even a legitimate one from GitHub's own issuer, is rejected.
  attribute_condition = "assertion.repository == '${var.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# The identity deploy.yml impersonates — deliberately its own account, not
# any of the runtime service accounts (api/agents/web) from iam.tf, so a
# compromised deploy pipeline's blast radius is "can run terraform apply,"
# not silently inheriting whatever the running application services can do.
resource "google_service_account" "deployer" {
  account_id   = "${local.name_prefix}-deployer"
  display_name = "GitHub Actions deploy pipeline (${var.environment})"
}

resource "google_service_account_iam_member" "github_impersonates_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# The deployer needs to manage every resource type this Terraform creates,
# plus push images. roles/editor is explicitly what PHASE-06 Common
# Pitfall #4 warns against — granting the specific roles actually needed
# instead, even though it's more lines than one blanket role.
resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_artifact_registry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_cloudsql_admin" {
  project = var.project_id
  role    = "roles/cloudsql.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_pubsub_admin" {
  project = var.project_id
  role    = "roles/pubsub.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_secretmanager_admin" {
  project = var.project_id
  role    = "roles/secretmanager.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_iam_admin" {
  project = var.project_id
  # Needed because this Terraform itself manages IAM bindings (iam.tf) —
  # the deploy pipeline has to be able to grant the same permissions it
  # already grants today, or every apply after the first would fail trying
  # to reconcile bindings it can no longer touch.
  role   = "roles/resourcemanager.projectIamAdmin"
  member = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_service_usage_admin" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageAdmin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "deployer_can_act_as_runtime_sas" {
  # Keys are statically known at config-write time ("api"/"agents"/"web");
  # only the *values* (the actual SA resource names) are unknown until
  # apply. A for_each over the values directly (toset([google_service_
  # account.api.name, ...])) fails terraform plan on a from-empty project —
  # Terraform can't determine the for_each key set from values that don't
  # exist yet — caught via a real `terraform plan` against scene-craft-
  # 507404, not just `validate`.
  for_each = {
    api    = google_service_account.api.name
    agents = google_service_account.agents.name
    web    = google_service_account.web.name
  }
  service_account_id = each.value
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
