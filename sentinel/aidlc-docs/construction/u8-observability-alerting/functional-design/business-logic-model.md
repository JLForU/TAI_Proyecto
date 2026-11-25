# Business Logic Model — U8 (Observability & alerting)

## 1. Flujo operativo de observabilidad y alertas
1. **Recolección (`U6` + `U7`)**: Sentinel Core expone las 14 familias de métricas en `:9108/metrics` mediante `MetricsServer` y `collect()`. El objeto `ServiceMonitor` en `deploy/monitoring/servicemonitor.yaml` (`release: monitoring`, puerto `metrics`) habilita el scrape desde Prometheus (`kube-prometheus-stack` en namespace `monitoring`).
2. **Evaluación de reglas (`PrometheusRule`)**:
   - **R-01 (`TrafficThresholdExceeded` — `implemented` / GT-04)**: se activa cuando el indicador de umbral de tráfico o tasa de bytes por segundo excede la condición configurada tras la ventana inicial de línea base (`U6`), respetando la duración `for` definida.
   - **R-04 (`SensorUnavailable` — `implemented` / GT-05)**: se activa cuando el indicador de disponibilidad del colector/sensor (`sentinel_collector_up` o ausencia de señal/scrape sostenido) indica indisponibilidad durante el periodo `for`.
   - **R-02 (`ArpRateThresholdExceeded` — `documented-only`)** y **R-03 (`ArpMappingChanged` — `documented-only`)**: quedan especificadas como diseño futuro sin regla activa en el alcance mínimo de alerta.
3. **Visualización (`Grafana`)**: cuatro vistas/paneles operativos (`FR-OBS-04`): inventario de activos, líneas base de tráfico, línea de tiempo de alertas y salud del sensor.
4. **Notificación (`Alertmanager` — `documented-only`)**: enrutamiento mediante receptor webhook (p. ej. `webhook.site` en pruebas de laboratorio), sin correo, SMS ni acciones automáticas sobre activos.

## 2. Contrato de red para scraping (`ID-U7-07` / `FR-SEC-01`)
- Permitir tráfico de entrada TCP `9108` desde pods del namespace `monitoring` hacia `sentinel-core` (`app.kubernetes.io/name: sentinel-core`) antes de aplicar políticas `default-deny`.
