# Applied by deploy.yml only after the manual approval gate (GitHub
# Environments, "production") — see .github/workflows/deploy.yml. Secrets
# come from TF_VAR_* set by that workflow from GitHub Actions secrets,
# never committed here.
project_id  = "scene-craft-507404"
region      = "us-central1"
environment = "prod"
# >=1 only worth the always-on cost right before/during judging — see
# infra/README.md's cost-conscious sequencing note. 0 the rest of the time.
min_instances_api   = 0
container_image_tag = "latest" # overridden per-run via -var on the CLI with the real git SHA
grafana_enabled     = false    # flip to true once a Grafana Cloud account exists — see infra/README.md
