# Replaces agents/.local_storage/ (shared/storage.py's local-dev stand-in
# for Cloud Storage — see that module's docstring). Provisioned here so the
# bucket exists and is correctly IAM-scoped ahead of wiring shared/storage.py
# to write to it directly — see infra/README.md's known-gaps section for
# that follow-up; this bucket is safe to provision now regardless, since an
# empty unused bucket costs nothing beyond what it stores.
resource "google_storage_bucket" "frames" {
  name                        = "${var.project_id}-scenecraft-${var.environment}-frames"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = var.environment != "prod"

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}
