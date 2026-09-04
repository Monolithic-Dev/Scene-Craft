# Three services, matching 10-DIAGRAMS.md SS8's CR1 (api) / CR2 (web) / CR3
# (agents — the "Agent Workers" service, agents/orchestrator/
# pubsub_receiver.py). agents is deployed separately from api specifically
# so it can hold its own least-privilege service account (iam.tf) and never
# needs Cloud SQL access — everything it needs comes through Pub/Sub in and
# MCP-over-stdio-to-the-API out.

resource "google_cloud_run_v2_service" "api" {
  name                = "${local.name_prefix}-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.min_instances_api
      max_instance_count = 10
    }

    # No vpc_access block: Redis is external (Upstash, reached over the
    # public internet via TLS — see variables.tf's redis_url) and Cloud SQL
    # goes through its own Auth Proxy volume mount below, so nothing here
    # needs a private network path.

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
        name = "REDIS_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.redis_url.secret_id
            version = "latest"
          }
        }
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

  # Explicit edges to everything this revision needs to actually exist at
  # start time: the IAM grants (nothing above references those resources'
  # attributes, so Terraform's implicit graph doesn't know the
  # secret_key_ref values need their bindings first) AND the secret
  # *versions* themselves (secret_key_ref's `secret` argument is the
  # container's secret_id, not the version resource, so the version isn't
  # implied either) — found the hard way, twice: a `-target` apply of just
  # this resource first skipped the IAM bindings ("Permission denied on
  # secret"), then after adding those, skipped the versions too ("Secret
  # ... was not found" — the container existed with zero versions in it).
  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.api_reads_jwt_secret,
    google_secret_manager_secret_iam_member.api_reads_internal_service_key,
    google_secret_manager_secret_iam_member.api_reads_database_url,
    google_secret_manager_secret_iam_member.api_reads_redis_url,
    google_project_iam_member.api_cloudsql_client,
    google_secret_manager_secret_version.jwt_secret_key,
    google_secret_manager_secret_version.internal_service_key,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_version.redis_url,
    google_sql_database.scenecraft,
    google_sql_user.scenecraft,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service" "web" {
  name                = "${local.name_prefix}-web"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.web.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      # web_image_tag, not container_image_tag — see variables.tf's
      # web_image_tag for why this image can't be shared across
      # environments the way api/agents' images are.
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/web:${var.web_image_tag}"

      ports {
        container_port = 8080
      }

      # No NEXT_PUBLIC_* env vars here: Next.js inlines them into the
      # client JS bundle at `next build` time, not at container runtime —
      # a Cloud Run env var set here would have zero effect on the
      # already-built, already-pushed image. They're passed as Docker
      # build args instead when the image is built (see
      # apps/web/Dockerfile and infra/README.md's "Building the web image"
      # section) — this service just runs whatever was baked in.

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
  name                = "${local.name_prefix}-agents"
  location            = var.region
  deletion_protection = false
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

    # No vpc_access block: agents never talks to Redis (only apps/api's
    # rate limiter does) and reaches everything else — Gemini/Vertex AI,
    # the API's own /internal/v1 endpoints — over the public internet.

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

  # See the api service's depends_on comment above — same reasoning.
  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.agents_reads_gemini_key,
    google_secret_manager_secret_iam_member.agents_reads_internal_service_key,
    google_secret_manager_secret_version.gemini_api_key,
    google_secret_manager_secret_version.internal_service_key,
  ]
}
