# Gated behind var.grafana_enabled so the rest of the stack applies cleanly
# before a Grafana Cloud account exists — see infra/README.md for account
# setup and why Grafana Cloud (not self-hosted Grafana+Tempo+Mimir on Cloud
# Run) was chosen: zero extra compute/storage infra, free tier is generous
# enough for a hackathon-scale system, and it's an explicitly allowed option
# per PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md SS1 ("export... directly
# to Grafana Cloud, depending on which Grafana deployment mode you choose").
#
# Each dashboard's JSON uses datasource *template variables*
# ($DS_PROMETHEUS / $DS_TEMPO) rather than a hardcoded datasource UID,
# since Grafana Cloud's auto-provisioned Prometheus/Tempo datasource UIDs
# are account-specific and don't exist until the account does — Grafana
# resolves the template variable to the account's real datasource at view
# time, no hardcoded UID needed here.
resource "grafana_dashboard" "system_health" {
  count       = var.grafana_enabled ? 1 : 0
  config_json = file("${path.module}/../grafana/dashboards/system-health.json")
}

resource "grafana_dashboard" "agent_activity" {
  count       = var.grafana_enabled ? 1 : 0
  config_json = file("${path.module}/../grafana/dashboards/agent-activity.json")
}

resource "grafana_dashboard" "cost_usage" {
  count       = var.grafana_enabled ? 1 : 0
  config_json = file("${path.module}/../grafana/dashboards/cost-usage.json")
}
