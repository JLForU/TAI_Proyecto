# Functional Design Plan — U8 (Observability & alerting)

**Fase**: CONSTRUCTION — Functional Design (Part 1 + Part 2)
**Fecha**: 2026-11-24
**Estado**: APPROVED (Q1=A, Q2=A, Q3=A)
**Workspace root**: `/home/jhoseph/Documents/TAI/TAI_Proyecto/sentinel`

## 1. Alcance de historias (Story Map)
- **Implementadas (`implemented`)**: `ST-M7-01` (regla `PrometheusRule` R-01 tráfico, GT-04), `ST-M7-04` (alerta R-04 `SensorUnavailable`, GT-05), `ST-M7-05` (dashboards Grafana y stack `kube-prometheus-stack`).
- **Documentadas (`documented-only`)**: `ST-M7-02` (regla R-02 tasa ARP), `ST-M7-03` (regla R-03 `ArpMappingChanged`), `ST-M7-06` (webhook receiver de Alertmanager).

## 2. Pasos de diseño funcional
- [x] **Step 1**: Modelar reglas `PrometheusRule` (R-01 y R-04 activas; R-02 y R-03 documentadas) usando métricas y labels aprobados en U7.
- [x] **Step 2**: Definir topología de `kube-prometheus-stack` (release `monitoring`, namespace `monitoring`), vinculación con `deploy/monitoring/servicemonitor.yaml` y 4 paneles/dashboards Grafana (`FR-OBS-04`).
- [x] **Step 3**: Especificar receptor webhook de Alertmanager (`ST-M7-06` / `FR-OBS-03`) y contrato de red `NetworkPolicy` para `:9108` (`ID-U7-07` / `FR-SEC-01`).
