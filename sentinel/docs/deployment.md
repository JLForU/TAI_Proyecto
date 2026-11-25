# Despliegue de Sentinel en Kubernetes

1. **Imagen única**: construir la imagen `sentinel:test` desde `sentinel/Dockerfile` con entrypoints separados (`python -m sentinel.core`, `python -m sentinel.discovery`, `python -m sentinel.traffic`).
2. **Chart de Helm (`U9`)**: desplegar `charts/sentinel` en el namespace `sentinel` (`Deployment` de Core con PVC y puertos `8080`/`9108`, `CronJob` de Discovery y `Deployment` de Traffic).
3. **Observabilidad (`U7` + `U8`)**: instalar `kube-prometheus-stack` (release `monitoring`, namespace `monitoring`), aplicar `deploy/monitoring/servicemonitor.yaml`, `deploy/monitoring/prometheusrule.yaml` y `deploy/monitoring/values-monitoring.yaml`.
4. **Seguridad (`U10`)**: aplicar `deploy/security/rbac.yaml` y `deploy/security/networkpolicy-metrics.yaml` (permitiendo scrape TCP `9108` desde `monitoring` hacia `sentinel-core`).
