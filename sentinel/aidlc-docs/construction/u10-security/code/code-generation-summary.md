# Code Generation Summary — U10 Security & negative tests

**Stage**: Construction · Code Generation (ST-M9-01..04, EN-04)
**Fecha**: 2026-11-25

## Archivos generados
- `deploy/security/rbac.yaml`: `ServiceAccount`s separados y `Role`/`RoleBinding` de solo lectura en namespace `sentinel` (`ST-M9-01`).
- `deploy/security/networkpolicy-metrics.yaml`: política mínima de ingreso TCP `9108` desde `monitoring` hacia `sentinel-core` (`ID-U7-07`, `FR-SEC-01`); `ST-M9-02` (default-deny avanzado) y `EN-04` (escaneo de imagen) documentados.
- `tests/unit/test_security_negative.py`: pruebas negativas sobre RBAC/NetworkPolicy, ausencia de `privileged: true`/`CAP_SYS_ADMIN` y prohibición de mutaciones en endpoints (`ST-M9-03`, `ST-M9-04`).
