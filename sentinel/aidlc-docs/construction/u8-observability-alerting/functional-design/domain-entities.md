# Domain Entities — U8 (Observability & alerting)

- **AlertRuleSpec**: define `name` (`TrafficThresholdExceeded`, `SensorUnavailable`; más `ArpRateThresholdExceeded` y `ArpMappingChanged` como `documented-only`), `expression`, `for_duration`, `severity` y `status` (`implemented` | `documented-only`).
- **DashboardSpec**: define los 4 paneles requeridos por `FR-OBS-04` (`asset_inventory`, `traffic_baselines`, `alert_timeline`, `sensor_health`) sobre métricas agregadas de U6/U7.
- **WebhookRouteSpec**: define el destino HTTP webhook de Alertmanager (`ST-M7-06`, `documented-only`) para demostración en laboratorio.
- **ScrapeIngressContract**: define el flujo permitido TCP `9108` (`namespace: monitoring` → `sentinel-core` en `namespace: sentinel`) requerido por `ID-U7-07`.
