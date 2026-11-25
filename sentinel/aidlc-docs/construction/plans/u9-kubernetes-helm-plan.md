# Construction Plan — U9 (Kubernetes runtime & Helm)

**Fase**: CONSTRUCTION — Design & Code Generation (ST-M8-01..04)
**Fecha**: 2026-11-25
**Estado**: APPROVED

## Pasos
- [x] **Step 1**: Crear `charts/sentinel/Chart.yaml` y `charts/sentinel/values.yaml` (imagen única, puertos 8080/9108, PVC, `explicit_hosts`/CIDR scope y parámetros baseline).
- [x] **Step 2**: Crear plantillas en `charts/sentinel/templates/` para Core (`Deployment`, `Service`, `PVC`), Discovery (`CronJob`) y Traffic Sensor (`Deployment`) usando comandos separados desde la misma imagen.
- [x] **Step 3**: Agregar prueba unitaria estructural `tests/unit/test_helm_chart.py` y resumen `aidlc-docs/construction/u9-kubernetes-helm/code/code-generation-summary.md`.
