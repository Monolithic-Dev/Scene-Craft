# VPC solely so Cloud Run's API/Agents services can reach Memorystore
# (redis.tf) via direct VPC egress (Cloud Run v2's simpler alternative to a
# separate Serverless VPC Access connector — no extra resource needed).
# Cloud SQL deliberately does NOT go through this VPC — it connects via the
# Cloud SQL Auth Proxy sidecar Cloud Run manages natively (see cloud_run.tf's
# volumes/cloud_sql_instance block), which needs no private networking.
resource "google_compute_network" "vpc" {
  name                    = "${local.name_prefix}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${local.name_prefix}-subnet"
  ip_cidr_range = "10.10.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
}
