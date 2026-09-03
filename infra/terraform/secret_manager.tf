# Every credential audited across Phases 1-6 (see PHASE-06 SS3's checklist)
# moves here. Cloud Run reads these via its native Secret Manager
# integration (value_source.secret_key_ref in cloud_run.tf) — mounted as
# env vars at container start, never baked into an image or committed to
# a .env file. IAM access is granted per-secret, per-service-account, in
# iam.tf — not a blanket project-wide secretAccessor role.
resource "google_secret_manager_secret" "jwt_secret_key" {
  secret_id = "${local.name_prefix}-jwt-secret-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "jwt_secret_key" {
  secret      = google_secret_manager_secret.jwt_secret_key.id
  secret_data = var.jwt_secret_key
}

# Shared between apps/api (validates it) and mcp_server (sends it on every
# /internal/v1 call) — one Secret Manager entry, read by both service
# accounts, exactly like the two processes already share it via matching
# .env values in local dev.
resource "google_secret_manager_secret" "internal_service_key" {
  secret_id = "${local.name_prefix}-internal-service-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "internal_service_key" {
  secret      = google_secret_manager_secret.internal_service_key.id
  secret_data = var.internal_service_key
}

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "${local.name_prefix}-gemini-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "gemini_api_key" {
  secret      = google_secret_manager_secret.gemini_api_key.id
  secret_data = var.gemini_api_key
}

# The full connection string (not just the raw password) is the secret —
# Cloud Run's env model is one value per var, so DATABASE_URL has to be
# assembled once here rather than templated from a separate password env
# var at container start.
resource "google_secret_manager_secret" "database_url" {
  secret_id = "${local.name_prefix}-database-url"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id
  secret_data = join("", [
    "postgresql://scenecraft:", var.db_password,
    "@/", google_sql_database.scenecraft.name,
    "?host=/cloudsql/", google_sql_database_instance.postgres.connection_name,
  ])
}
