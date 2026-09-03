output "api_url" {
  value       = google_cloud_run_v2_service.api.uri
  description = "The API's public URL — set apps/web's NEXT_PUBLIC_API_BASE_URL to this if not deploying web through this same Terraform run."
}

output "web_url" {
  value       = google_cloud_run_v2_service.web.uri
  description = "The hosted app URL for the Devpost submission (distinct from the Replit URL — see PHASE-07-DEMO-AND-SUBMISSION.md SS7)."
}

output "agents_url" {
  value       = google_cloud_run_v2_service.agents.uri
  description = "Internal — only Pub/Sub's push subscription should call this."
}

output "cloud_sql_connection_name" {
  value       = google_sql_database_instance.postgres.connection_name
  description = "For connecting via the Cloud SQL Auth Proxy from outside Cloud Run (e.g. a one-off `gcloud sql connect` for debugging)."
}

output "redis_host" {
  value       = google_redis_instance.cache.host
  description = "Only reachable from inside the VPC (network.tf) — not a public endpoint."
}

output "artifact_registry_repository" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
  description = "Push images here as api:<sha>, web:<sha>, agents:<sha> — see .github/workflows/deploy.yml."
}

output "pubsub_topic" {
  value       = google_pubsub_topic.jobs.id
  description = "Set apps/api's PUBSUB_TOPIC to this to switch agent_runner.py from local subprocess spawn to real dispatch."
}

output "service_account_emails" {
  value = {
    api    = google_service_account.api.email
    agents = google_service_account.agents.email
    web    = google_service_account.web.email
  }
}
