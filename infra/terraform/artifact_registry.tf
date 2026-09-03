# One shared repository across environments — images are tagged by git SHA
# (var.container_image_tag), not by environment, so dev/staging/prod can
# promote the exact same image rather than rebuilding per environment.
resource "google_artifact_registry_repository" "images" {
  repository_id = "scenecraft"
  location      = var.region
  format        = "DOCKER"
  description   = "SceneCraft container images: api, web, agents"

  depends_on = [google_project_service.apis]
}
