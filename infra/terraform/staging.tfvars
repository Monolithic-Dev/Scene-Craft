# Applied by deploy.yml on every merge to main (before the manual approval
# gate) — see .github/workflows/deploy.yml. Secrets come from TF_VAR_* set
# by that workflow from GitHub Actions secrets, never committed here.
project_id          = "scene-craft-507404"
region              = "us-central1"
environment         = "staging"
min_instances_api   = 0
container_image_tag = "latest" # overridden per-run via -var on the CLI with the real git SHA
grafana_enabled     = false    # flip to true once a Grafana Cloud account exists — see infra/README.md

# Cloud Run URLs are stable once assigned (hash of project+service+region),
# so this is safe to commit rather than pass via -var every time — without
# it, a future `terraform apply -var-file=staging.tfvars` (e.g. from
# deploy.yml) would silently revert CORS back to the http://localhost:3000
# default, undoing the bootstrapping step in infra/README.md.
web_allowed_origin = "https://scenecraft-staging-web-fq6tp4iyja-uc.a.run.app"
