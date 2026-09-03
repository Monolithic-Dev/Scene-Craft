# Three services, matching 10-DIAGRAMS.md SS8's CR1 (api) / CR2 (web) / CR3
# (agents — the "Agent Workers" service, agents/orchestrator/
# pubsub_receiver.py). agents is deployed separately from api specifically
# so it can hold its own least-privilege service account (iam.tf) and never
# needs Cloud SQL access — everything it needs comes through Pub/Sub in and
# MCP-over-stdio-to-the-API out.

resource "google_cloud_run_v2_service" "api" {
  name     = "${local.name_prefix}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.min_instances_api
      max_instance_count = 10
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.vpc.id
        subnetwork = google_compute_subnetwork.subnet.id
      }
      # Only private-range traffic (Memorystore) routes through the VPC;
      # calls to Cloud SQL (via its own Auth Proxy volume mount below),
      # Gemini, and Pub/Sub still go out directly.
      egress = "PRIVATE_RANGES_ONLY"
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/api:${var.container_image_tag}"

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = jsonencode([var.web_allowed_origin != "" ? var.web_allowed_origin : "http://localhost:3000"])
      }
      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.cache.host}:${google_redis_instance.cache.port}/0"
      }
      env {
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.jobs.id
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "JWT_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "INTERNAL_SERVICE_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.internal_service_key.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service" "web" {
  name     = "${local.name_prefix}-web"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.web.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/web:${var.container_image_tag}"

      ports {
        container_port = 8080
      }

      env {
        name  = "NEXT_PUBLIC_API_BASE_URL"
        value = google_cloud_run_v2_service.api.uri
      }
      # NEXT_PUBLIC_FIREBASE_* are not secrets (see apps/web/lib/firebase.ts
      # and infra/firestore/firestore.rules for why) — deliberately left as
      # plain vars set post-apply via `gcloud run services update`, rather
      # than templated here, since the Firebase Web App must exist first
      # (a one-time manual `firebase apps:create WEB` step — see
      # infra/README.md).

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "web_public" {
  name     = google_cloud_run_v2_service.web.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service" "agents" {
  name     = "${local.name_prefix}-agents"
  location = var.region
  # Pub/Sub push only — never a browser. No public health-check traffic
  # expected either; Pub/Sub's own OIDC-authenticated push is the only
  # caller (see pubsub.tf's push_config + IAM binding below).
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.agents.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.vpc.id
        subnetwork = google_compute_subnetwork.subnet.id
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    # Deliberately no cloud_sql_instance volume here — agents never touch
    # Cloud SQL directly, only through MCP -> the API's /internal/v1
    # endpoints (04-AGENT-ARCHITECTURE.md's MCP boundary; also why the
    # agents service account has no cloudsql.client role in iam.tf).

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/agents:${var.container_image_tag}"

      ports {
        container_port = 8080
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "API_BASE_URL"
        value = google_cloud_run_v2_service.api.uri
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "INTERNAL_SERVICE_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.internal_service_key.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          # Frame generation fans out one concurrent worker per shot
          # (frame_agent) — more headroom than the request/response-shaped
          # api/web services.
          cpu    = "2"
          memory = "1Gi"
        }
      }
    }

    timeout = "900s" # a full initial_generation run can take minutes
  }

  depends_on = [google_project_service.apis]
}
