# Business Rules — U8 (Observability & alerting)

- **BR-U8-01 (Cobertura de historias)**: `ST-M7-01` (R-01), `ST-M7-04` (R-04) y `ST-M7-05` (stack y dashboards Grafana) son `implemented`; `ST-M7-02` (R-02), `ST-M7-03` (R-03) y `ST-M7-06` (webhook Alertmanager) son `documented-only`.
- **BR-U8-02 (Cardinalidad estricta)**: ninguna expresión de alerta o panel de Grafana agrega por dirección IP, dirección MAC, puerto o hostname.
- **BR-U8-03 (No actuación automática)**: el sistema de alertas y dashboards es exclusivamente observable; no modifica tráfico, no bloquea hosts ni altera el estado de los activos.
- **BR-U8-04 (Independencia de sondas de salud)**: un fallo en la evaluación de reglas o en Prometheus no degrada las sondas de salud de Core en `:8080`.
- **BR-U8-05 (Ubicación de artefactos)**: los manifiestos y valores declarativos de observabilidad residen bajo `deploy/monitoring/`.
