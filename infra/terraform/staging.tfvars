# Applied by deploy.yml on every merge to main (before the manual approval
# gate) — see .github/workflows/deploy.yml. Secrets come from TF_VAR_* set
# by that workflow from GitHub Actions secrets, never committed here.
project_id          = "scene-craft-507404"
region              = "us-central1"
environment         = "staging"
min_instances_api   = 0
container_image_tag = "latest" # overridden per-run via -var on the CLI with the real git SHA
grafana_enabled     = false    # flip to true once a Grafana Cloud account exists — see infra/README.md
