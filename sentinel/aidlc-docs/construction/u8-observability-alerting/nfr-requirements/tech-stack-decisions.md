# Tech Stack Decisions — U8 (Observability & alerting)

- **TS-U8-01 (Stack de monitoreo)**: `kube-prometheus-stack` desplegado en el namespace `monitoring` (release `monitoring`), consumiendo `deploy/monitoring/servicemonitor.yaml`.
- **TS-U8-02 (Formato de reglas y dashboards)**: manifiestos Kubernetes `PrometheusRule` (`monitoring.coreos.com/v1`) y definiciones declarativas de dashboards Grafana bajo `deploy/monitoring/`.
- **TS-U8-03 (Notificación)**: webhook HTTP de Alertmanager (`ST-M7-06`, `documented-only`) sin dependencias externas obligatorias en CI.
- **TS-U8-04 (Pruebas)**: validación local con `pytest` y verificaciones estructurales/textuales de manifiestos en el repositorio.
