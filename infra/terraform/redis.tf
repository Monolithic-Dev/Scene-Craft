# Backs core/rate_limiter.py's distributed limiter (replacing Phase 1's
# in-process one — see that module's docstring). Basic tier (no HA
# replica) and the smallest size: this is a coarse abuse-prevention
# counter, not data that needs to survive a node failure — losing the
# rate-limit window on a rare Memorystore restart just means a brief
# window of unlimited requests, not data loss.
resource "google_redis_instance" "cache" {
  name           = "${local.name_prefix}-cache"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region
  redis_version  = "REDIS_7_2"

  # DIRECT_PEERING (the default) rather than PRIVATE_SERVICE_ACCESS: the
  # latter needs its own reserved global address + service-networking
  # connection resource just to reach one Redis instance, which is more
  # moving parts than this deployment's size justifies. Cloud Run's direct
  # VPC egress (cloud_run.tf) reaches this instance fine either way, since
  # both ultimately land in the same VPC (network.tf).
  authorized_network = google_compute_network.vpc.id
  connect_mode       = "DIRECT_PEERING"

  depends_on = [google_project_service.apis]
}
