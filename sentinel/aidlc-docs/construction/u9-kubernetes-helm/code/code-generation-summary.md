# Code Generation Summary — U9 Kubernetes runtime & Helm

**Stage**: Construction · Code Generation (ST-M8-01..04)
**Fecha**: 2026-11-25

## Archivos generados
- `charts/sentinel/Chart.yaml` y `charts/sentinel/values.yaml`: imagen única, puertos `8080`/`9108`, PVC `2Gi`, `explicit_hosts` y entrypoints por módulo (`sentinel.core`, `sentinel.discovery`, `sentinel.traffic`).
- `charts/sentinel/templates/core.yaml`: `PersistentVolumeClaim`, `Service` (`http-api` y `metrics`) y `Deployment` de `sentinel-core`.
- `charts/sentinel/templates/workloads.yaml`: `CronJob` de `sentinel-discovery` y `Deployment` de `sentinel-traffic`.
- `tests/unit/test_helm_chart.py`: prueba estructural local del chart.
