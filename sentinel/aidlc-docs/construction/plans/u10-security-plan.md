# Construction Plan — U10 (Security & negative tests)

**Fase**: CONSTRUCTION — Design & Code Generation (ST-M9-01..04, EN-04)
**Fecha**: 2026-11-25
**Estado**: APPROVED

## Pasos
- [x] **Step 1**: Crear `deploy/security/rbac.yaml` (ServiceAccounts y permisos mínimos para workloads en `sentinel`) y `deploy/security/networkpolicy-metrics.yaml` (política mínima permitiendo scrape TCP `9108` desde `monitoring` hacia `sentinel-core`, con `default-deny` y `EN-04` documentados).
- [x] **Step 2**: Crear prueba negativa unitaria `tests/unit/test_security_negative.py` (verificando ausencia de `privileged: true` / `CAP_SYS_ADMIN`, presencia de regla `9108` para `monitoring` y rechazo de operaciones de escritura sobre endpoints).
- [x] **Step 3**: Registrar `aidlc-docs/construction/u10-security/code/code-generation-summary.md` y validar localmente.
