# Public IP + the Cloud SQL Auth Proxy (via Cloud Run's native
# cloud_sql_instances volume mount in cloud_run.tf) rather than private VPC
# peering — the Auth Proxy authenticates with short-lived IAM/TLS
# credentials regardless of whether the connection travels over the public
# internet, so this is Google's own recommended pattern, not a shortcut.
# Cheaper and simpler than provisioning Private Service Access purely to
# reach Cloud SQL (the VPC in network.tf exists only for Memorystore, which
# has no public-IP or Auth-Proxy option).
resource "google_sql_database_instance" "postgres" {
  name                = "${local.name_prefix}-pg"
  database_version    = "POSTGRES_15"
  region              = var.region
  deletion_protection = var.environment == "prod"

  settings {
    tier = var.environment == "prod" ? "db-custom-2-7680" : "db-f1-micro"

    ip_configuration {
      ipv4_enabled = true
      # No authorized_networks entries: only the Cloud SQL Auth Proxy
      # (IAM-authenticated) is expected to connect, never a bare client IP.
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = var.environment == "prod"
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "scenecraft" {
  name     = "scenecraft"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "scenecraft" {
  name     = "scenecraft"
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}
