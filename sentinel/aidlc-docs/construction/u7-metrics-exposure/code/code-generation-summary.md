# Code Generation Summary — U7 Metrics exposure

**Stage**: Construction · Code Generation (Parte 2: Generation, 18/18 steps)
**Fecha**: 2026-11-24
**Plan**: `aidlc-docs/construction/plans/u7-metrics-exposure-code-generation-plan.md`

## 1. Archivos creados

### Despliegue / Observabilidad (`deploy/`)
| Archivo | Contenido |
|---|---|
| `deploy/monitoring/servicemonitor.yaml` | Manifiesto standalone `ServiceMonitor` (`monitoring.coreos.com/v1`, namespace `sentinel`, label `release: monitoring`, selector `app.kubernetes.io/name: sentinel-core`, puerto `metrics`, sin `interval`/`scrapeTimeout`) |

### Tests
| Archivo | Cubre |
|---|---|
| `tests/integration/test_metrics_exposure.py` | End-to-end ST-M6-04: discovery + traffic + arp → `assets_total`, `asset_changes_total`, `flows_total`, `arp_messages_total`, `bytes_per_second`; deduplicación sin doble conteo; catálogo completo de 14 familias |
| `tests/property/test_metrics_render.py` | PBT PB-U7-01/02: exactamente un `# HELP` y `# TYPE` por familia, nombres de familia válidos y cumplimiento estricto de la allowlist de labels |
| `tests/unit/test_servicemonitor.py` | Contrato textual del `ServiceMonitor` standalone sin dependencia de PyYAML |
| `tests/unit/core/test_metrics_scrape_latency.py` | NFR-U7-PERF-01 (informativo): p95 de 50 ejecuciones `collect(db=...)` < 1 s |

## 2. Archivos modificados

| Archivo | Edición |
|---|---|
| `src/sentinel/foundation/metrics_contract.py` | Catálogo ampliado a 14 familias (`+sentinel_assets_total`, `+sentinel_asset_changes_total`), allowlist de 7 labels (`+collector`, `+metric`) y validador `assert_allowed()` |
| `src/sentinel/core/metrics/collect.py` | `ObservationCounters` en memoria, gauges SQLite de solo lectura (`LIMIT 500`), integración con `ConditionService.metric_samples()`, zero-fill `component="core"`, validación `assert_allowed` y render Prometheus con `HELP`/`TYPE` y escapado de labels |
| `src/sentinel/core/health/service.py` | Método reutilizable `sensor_heartbeats()` con degradación segura a `{}` compartido con `health()` |
| `src/sentinel/core/api/app.py` | Composición de hooks post-commit (`_compose_hooks`) aislados por fallos (`metrics_hook_failed`), instancia de `ObservationCounters` en `app.state` e inyección en `collect_fn` |
| `tests/unit/foundation/test_metrics_contract.py` | Pruebas unitarias del catálogo de 14 familias, allowlist de 7 labels y `assert_allowed()` |
| `tests/unit/core/test_metrics.py` | Cobertura de contadores post-commit, gauges SQLite, última ventana, fallos de ciclo, escapado de labels y aislamiento de hooks |
| `README.md` | Documentación de la sección **Métricas (U7)** (14 familias, allowlist, zero-fill y `kubectl apply -f deploy/monitoring/servicemonitor.yaml`) |

## 3. Verificación de frontera y contratos

- **Solo lectura sobre SQLite**: `collect.py` ejecuta únicamente consultas `COUNT` y `SELECT ... LIMIT 500` en modo lectura sobre el PVC existente de U2; sin DDL ni nuevas escrituras.
- **Cardinalidad acotada**: `assert_allowed()` bloquea labels prohibidos (IPs, MACs, puertos, hostnames) y restringe las etiquetas a la allowlist cerrada de 7 claves.
- **Aislamiento de fallos**: `_compose_hooks()` captura excepciones individuales sin interrumpir otros consumidores ni alterar el `202 Accepted` de ingesta.

## 4. Handoffs hacia U8–U11

- **U8 (Observability & alerting)**: Instalar `kube-prometheus-stack` (release `monitoring`, ns `monitoring`), aplicar `deploy/monitoring/servicemonitor.yaml` e implementar la regla de `NetworkPolicy` (ingress TCP `9108` desde ns `monitoring` hacia `app.kubernetes.io/name=sentinel-core`, contrato `ID-U7-07`) antes de habilitar `default-deny` (SN-038).
- **U9 (Kubernetes runtime & Helm)**: Sin variables de entorno nuevas (`SENTINEL_METRICS_*` no existe); el ServiceMonitor se mantiene standalone fuera del chart (`ID-U7-06/10`).
- **U10 (Security)**: Validar que `:9108` opere sin autenticación interna protegido exclusivamente por la `NetworkPolicy` de U8 (`NFR-U7-SEC-01/02`).
- **U11 (Docs & GT)**: Verificar `up == 1` y las 14 familias en Prometheus durante la ejecución en `kind`.

## 5. Cobertura y validación (Step 15 — todo en verde)

| Gate | Resultado |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 189 files already formatted |
| `mypy src/sentinel` | Success: no issues found in 87 source files |
| `pytest tests/unit tests/property tests/integration --cov=sentinel --cov-fail-under=70` | **558 passed**, cobertura total **94.97%** |
| Cobertura `core/metrics/collect.py` | **98%** (138 stmts, 3 miss) |
| Cobertura `foundation/metrics_contract.py` | **100%** (24 stmts, 0 miss) |

## 6. Historias y trazabilidad

- **ST-M6-01..05** (M6 Metrics & observability): implementadas y verificadas mediante pruebas unitarias, de propiedades e integración (18/18 steps `[x]`).
