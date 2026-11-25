# Deployment Architecture — U8 (Observability & alerting)

**Fase**: CONSTRUCTION — Infrastructure Design
**Estado**: APPROVED (2026-11-24)

## Topología de observabilidad
```mermaid
flowchart LR
  subgraph MON["namespace: monitoring (kube-prometheus-stack)"]
    PROM["Prometheus (release: monitoring)"]
    AM["Alertmanager (webhook receiver doc)"]
    GRAF["Grafana (4 paneles FR-OBS-04)"]
    RULES["PrometheusRule (R-01, R-04)"]
    PROM --- RULES
    PROM --> AM
    GRAF --> PROM
  end
  subgraph SENT["namespace: sentinel"]
    CORE["sentinel-core (:9108/metrics)"]
    SM["ServiceMonitor sentinel-core"]
  end
  SM -.selecciona.- CORE
  PROM -->|"TCP 9108 scrape"| CORE
---

### Bloque 2: Manifiestos en `deploy/monitoring/`

Crea `prometheusrule.yaml`, `values-monitoring.yaml` y `grafana-dashboards.json` en `sentinel/deploy/monitoring/`:

```bash
mkdir -p ~/Documents/TAI/TAI_Proyecto/sentinel/deploy/monitoring

cat <<'EOF' > ~/Documents/TAI/TAI_Proyecto/sentinel/deploy/monitoring/prometheusrule.yaml
# Reglas Prometheus de Sentinel (U8 — ST-M7-01 implemented R-01, ST-M7-04 implemented R-04).
# R-02 (ArpRateThresholdExceeded, ST-M7-02) y R-03 (ArpMappingChanged, ST-M7-03)
# permanecen como documented-only en el diseño funcional de U8.
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: sentinel-observability-rules
  namespace: monitoring
  labels:
    release: monitoring
spec:
  groups:
    - name: sentinel.alerts.implemented
      rules:
        - alert: TrafficThresholdExceeded
          expr: >
            max_over_time(sentinel_traffic_threshold_exceeded[1m]) > 0
          for: 10s
          labels:
            severity: warning
            rule: R-01
          annotations:
            summary: "Umbral de tráfico excedido tras ventana de línea base (GT-04)"
            description: "Se detectó tráfico por encima del umbral configurado en Sentinel."
        - alert: SensorUnavailable
          expr: >
            min_over_time(sentinel_collector_up[30s]) == 0
          for: 15s
          labels:
            severity: critical
            rule: R-04
          annotations:
            summary: "Sensor o colector de telemetría no disponible (GT-05)"
            description: "No hay señal activa del colector de tráfico/observación durante la ventana configurada."
