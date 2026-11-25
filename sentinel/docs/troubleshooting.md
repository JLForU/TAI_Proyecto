# Solución de problemas (Troubleshooting)

- **Target de Prometheus en `down` sobre `:9108`**: verificar que el `Service` `sentinel-core` exponga el puerto `metrics` (`9108`), que `deploy/monitoring/servicemonitor.yaml` tenga `release: monitoring` y que `allow-prometheus-scrape-9108` permita el ingreso TCP `9108` desde el namespace `monitoring`.
- **Alertas `R-01` o `R-04` no disparan**: revisar que hayan transcurrido las muestras iniciales de línea base (`U6`) y que la serie `sentinel_traffic_threshold_exceeded` o `sentinel_collector_up` cumpla su expresión y duración `for`.
- **Reinicio del pod `sentinel-core`**: los datos persistidos en SQLite sobre PVC se recuperan automáticamente al arrancar; los contadores en memoria reinician a cero.
