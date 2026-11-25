# NFR Requirements — U8 (Observability & alerting)

- **NFR-U8-AVAIL-01 (Disponibilidad sin HA)**: alineado con `NFR-AVAIL-01`; el MVP opera con un sensor y stack único en laboratorio. La caída del sensor dispara `SensorUnavailable` (R-04) sin requerir alta disponibilidad del stack.
- **NFR-U8-AVAIL-02 (Recuperación tras reinicio)**: alineado con `NFR-AVAIL-02`; tras reiniciar pods en `monitoring` o `sentinel`, el `ServiceMonitor` restablece el scrape y los gauges de SQLite se reconstruyen desde la base persistida.
- **NFR-U8-PERF-01 (Latencia de evaluación y consulta)**: las consultas de reglas y paneles usan métricas agregadas y ventanas acotadas para mantener tiempos de respuesta bajos sin saturar `:9108/metrics` (`NFR-PERF-03`).
- **NFR-U8-SCAL-01 (Control de cardinalidad)**: las series y consultas de Grafana/Prometheus evitan dimensiones de alta cardinalidad (`SCAL-01`).
- **NFR-U8-SEC-01 (Aislamiento de red y sin secretos)**: los manifiestos de U8 no almacenan credenciales ni tokens; el acceso a `:9108` se restringe mediante `NetworkPolicy` (`FR-SEC-01`, `FR-SEC-02`) y la UI/dashboards en laboratorio se consultan vía `kubectl port-forward`.
- **NFR-U8-OPS-01 (Validación local sin clúster activo)**: los manifiestos y definiciones de U8 son verificables en entorno local mediante pruebas unitarias/estructurales sin exigir un clúster `kind` en ejecución durante este paso (`Q3=A`).
