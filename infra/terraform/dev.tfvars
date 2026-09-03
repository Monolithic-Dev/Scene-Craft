# Local/individual-developer environment — not part of the deploy.yml
# pipeline (which only targets staging/prod), for a developer who wants to
# apply Terraform by hand against their own throwaway resources. Secrets
# (db_password, jwt_secret_key, internal_service_key, gemini_api_key) are
# NEVER set here — export them as TF_VAR_* shell variables before running
# `terraform apply -var-file=dev.tfvars` — see infra/README.md.
project_id          = "scene-craft-507404"
region              = "us-central1"
environment         = "dev"
min_instances_api   = 0
container_image_tag = "latest"
grafana_enabled     = false
