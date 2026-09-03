# The Firestore Native database itself was already created manually in
# Phase 5 (gcloud firestore databases create --type=firestore-native, before
# any of this Terraform existed) and already holds real job_traces/{job_id}
# documents — this resource block brings it under Terraform management via
# import rather than creating a second one (a GCP project can have at most
# one Firestore database in most configurations, so a plain `apply` without
# first importing would conflict with the one that already exists):
#
#   terraform import google_firestore_database.default \
#     "projects/${var.project_id}/databases/(default)"
#
# Security rules (infra/firestore/firestore.rules) are deployed separately
# via `firebase deploy --only firestore:rules`, not through this resource —
# the Firebase CLI's deploy step is more direct for rules than routing
# through Terraform's firestore provider surface.
resource "google_firestore_database" "default" {
  project                     = var.project_id
  name                        = "(default)"
  location_id                 = var.region
  type                        = "FIRESTORE_NATIVE"
  concurrency_mode            = "OPTIMISTIC"
  app_engine_integration_mode = "DISABLED"

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.apis]
}
