# Replaces apps/api/src/core/agent_runner.py's local subprocess spawn in
# deployed environments — see that module's docstring and
# agents/orchestrator/pubsub_receiver.py, the push target below.
resource "google_pubsub_topic" "jobs" {
  name = "${local.name_prefix}-jobs"

  depends_on = [google_project_service.apis]
}

# Push (not pull): the Agent Workers Cloud Run service is a normal request-
# driven service (pubsub_receiver.py's FastAPI app), not a long-running
# poller — push matches Cloud Run's scale-to-zero model, since a pull
# subscriber would need to stay running to poll.
resource "google_pubsub_subscription" "jobs_push" {
  name  = "${local.name_prefix}-jobs-push"
  topic = google_pubsub_topic.jobs.id

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.agents.uri}/pubsub/push"

    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }

  # A stuck job is worse silent than loud: after 5 delivery attempts, route
  # to a dead-letter topic rather than retrying forever against a job that
  # keeps failing the same way.
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.jobs_dead_letter.id
    max_delivery_attempts = 5
  }

  ack_deadline_seconds = 600 # a full initial_generation run can take minutes
}

resource "google_pubsub_topic" "jobs_dead_letter" {
  name = "${local.name_prefix}-jobs-dead-letter"

  depends_on = [google_project_service.apis]
}

# Dedicated identity for Pub/Sub's own push requests (distinct from the
# Agents service account that *runs* the workload) — lets IAM grant "may
# invoke this Cloud Run service" narrowly to Pub/Sub's push mechanism
# without widening the Agents SA's own permissions.
resource "google_service_account" "pubsub_invoker" {
  account_id   = "${local.name_prefix}-pubsub-invoker"
  display_name = "Pub/Sub push invoker for SceneCraft Agent Workers (${var.environment})"
}

resource "google_cloud_run_v2_service_iam_member" "pubsub_invokes_agents" {
  name     = google_cloud_run_v2_service.agents.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

resource "google_pubsub_topic_iam_member" "dead_letter_publish" {
  topic = google_pubsub_topic.jobs_dead_letter.name
  role  = "roles/pubsub.publisher"
  # Pub/Sub's own service agent republishes to the dead-letter topic, not
  # any of our application service accounts.
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "dead_letter_subscribe" {
  subscription = google_pubsub_subscription.jobs_push.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

data "google_project" "current" {
  project_id = var.project_id
}
