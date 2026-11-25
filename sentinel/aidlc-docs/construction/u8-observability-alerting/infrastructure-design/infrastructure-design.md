# Infrastructure Design — U8 (Observability & alerting)

**Fase**: CONSTRUCTION — Infrastructure Design (Q1=A, Q2=A, Q3=A)
**Estado**: APPROVED (2026-11-24)
**Unidad**: U8 — Manifiestos de monitoreo/alertas en `deploy/monitoring/` + stack `kube-prometheus-stack` en namespace `monitoring`

## 1. Mapeo de infraestructura
- **Stack de monitoreo**: `kube-prometheus-stack` (Helm release `monitoring`, namespace `monitoring`), con Prometheus, Alertmanager y Grafana.
- **Scraping**: consume `deploy/monitoring/servicemonitor.yaml` (`release: monitoring`, selector `app.kubernetes.io/name: sentinel-core`, puerto `metrics` en `:9108/metrics`).
- **Reglas de alerta (`PrometheusRule`)**: `deploy/monitoring/prometheusrule.yaml` en namespace `monitoring` con label `release: monitoring`, implementando **R-01 (`TrafficThresholdExceeded`)** y **R-04 (`SensorUnavailable`)** y documentando **R-02** y **R-03** (`ST-M7-02`, `ST-M7-03`).
- **Dashboards Grafana y receptor Alertmanager (`ST-M7-05`, `ST-M7-06`)**: `deploy/monitoring/values-monitoring.yaml` y `deploy/monitoring/grafana-dashboards.json` con los 4 paneles (`FR-OBS-04`) y configuración webhook documentada (`ST-M7-06`, `documented-only`).
- **Contrato de red (`ID-U7-07` / `FR-SEC-01`)**: habilita el flujo de entrada TCP `9108` desde pods del namespace `monitoring` hacia `sentinel-core` (`app.kubernetes.io/name: sentinel-core`) antes de aplicar políticas `default-deny` en U10.
