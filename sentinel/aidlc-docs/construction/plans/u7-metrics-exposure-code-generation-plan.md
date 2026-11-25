# Code Generation Plan — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — Code Generation (Part 1: Planning + Part 2: Generation)
**Fecha**: 2026-11-24
**Estado**: COMPLETED — 18/18 steps ejecutados y validados
**Workspace root**: `/home/jhoseph/Documents/TAI/TAI_Proyecto/sentinel` (de `aidlc-state.md`)
**Patrón**: Greenfield multi-unit (monolith) → `src/sentinel/` (U7 toca `foundation/`, `core/metrics/`, `core/health/`, `core/api/` y `deploy/monitoring/`)
**Este plan es la única fuente de verdad de Code Generation para U7.**

---

## 1. Contexto de la unidad

- **Historias**: ST-M6-01..05 (M6 Metrics & observability) — `GET :9108/metrics` con las 14 familias, contadores post-commit, gauges de SQLite, indicadores U6, ServiceMonitor.
- **Diseño aprobado**: FD (BR-U7-01..24, Q1–Q11), NFR Requirements (NFR-U7-PERF-01/02, SCAL-01, AVAIL-01/02, REL-01, SEC-01/02, MNT-01..05, STACK-01, OPS-01; TS-U7-01..12), NFR Design (P1–P10, Q1–Q8), Infrastructure Design (ID-U7-01..06, Q1–Q6).
- **Dependencias satisfechas**: U1 (`metrics_contract.py`, `assert_labels`), U2 (`MetricsServer`, `collect.py` stub, `Database`, `IngestionService` hook de U6), U4 (`CycleCounter`), U5 (`TrafficObservation`/`ArpObservation`), U6 (`ConditionService.metric_samples()`).
- **Decisiones clave**: Q3=C (+2 familias ⇒ 14), Q10=B (allowlist de 7 labels + `assert_allowed`), Q7=A (ServiceMonitor), Q11=A (HELP por familia); infra Q1–Q6=A (SM standalone `kubectl apply`, sin resources/PVC/NetworkPolicy, sin `interval`/`scrapeTimeout`, labels `release: monitoring` + `app.kubernetes.io/name: sentinel-core`).
- **Límites**: sin cambios a `server.py` (9108, `GET /metrics`), sin cambios de esquema, sin deps pip nuevas, sin Helm/umbrella (U8/U9).

---

## 2. Pasos de generación (numerados, checkbox)

- [x] **Step 1 — Contrato v2 (BR-U7-01..04, Q3=C/Q10=B)**
  Editar `src/sentinel/foundation/metrics_contract.py`: `METRIC_FAMILIES` a 14 (+`sentinel_assets_total`, `sentinel_asset_changes_total`); `ALLOWED_LABELS_DEFAULT` a 7 (+`collector`, `metric`); nueva `assert_allowed(labels)` = denylist BR-21 + allowlist; `assert_labels` intacta.

- [x] **Step 2 — Unit tests: contrato v2**
  `tests/unit/foundation/test_metrics_contract.py`: 14 familias, 7 labels, `assert_allowed` acepta allowlist/`{}`, rechaza prohibidos y labels fuera de allowlist.

- [x] **Step 3 — Colector v2: contadores de observaciones (BR-U7-11..13)**
  `src/sentinel/core/metrics/collect.py`: `ObservationCounters` (`on_accepted` acumula `flows` de `TrafficObservation` y +1 por `ArpObservation`; `snapshot()`), `HELP_TEXT` (14), `LATEST_OBS_LIMIT=500`.

- [x] **Step 4 — Colector v2: gauges SQLite (BR-U7-05..09, Q4/Q7)**
  `_sqlite_gauges(db)`: `alerts_firing`, `assets_total`, `asset_changes_total` (eventos de cambio) y última ventana `bytes_per_second` por `(interface, protocol)` desde `observations` (`ORDER BY observed_at DESC LIMIT 500`, JSON payload).

- [x] **Step 5 — Colector v2: pipeline + zero-fill + validación (BR-U7-01/04/08)**
  `collect(..., condition_service=, db=, obs_counters=)`: providers opcionales, indicadores U6, zero-fill `component=core`, `assert_allowed` por sample, catálogo exacto; `render_prometheus` con HELP/TYPE, escapado de labels y validación por sample.

- [x] **Step 6 — Heartbeats reutilizables (BR-U7-09)**
  `src/sentinel/core/health/service.py`: `sensor_heartbeats()` (degrada a `{}`) y `_heartbeats(conn)` compartido con `health()`.

- [x] **Step 7 — Unit tests: colector v2**
  `tests/unit/core/test_metrics.py`: contadores, gauges SQLite + última ventana, `CycleCounter.failed_total`, escapado, rechazo de labels, aislamiento de hooks; actualizar test de wiring U6.

- [x] **Step 8 — Hook compuesto en `create_app` (BR-U7-11/12, D-U7-02)**
  `src/sentinel/core/api/app.py`: `_compose_hooks(*hooks)` (fallo ⇒ log `metrics_hook_failed`, no propaga), `ObservationCounters` en `app.state`, `IngestionService(on_accepted=compose(condition, counters))`, `collect_fn` con `condition_service`, `db`, `obs_counters`.

- [x] **Step 9 — Integration: métricas end-to-end (ST-M6-04)**
  `tests/integration/test_metrics_exposure.py`: discovery+traffic+arp ⇒ `assets_total`, `asset_changes_total`, `flows_total`, `arp_messages_total`, `bytes_per_second`; reenvío deduplicado no duplica; 14 familias.

- [x] **Step 10 — Property: render Prometheus (PB-U7-01/02)**
  `tests/property/test_metrics_render.py`: un HELP/TYPE por familia, líneas con familia válida, allowlist estricta.

- [x] **Step 11 — ServiceMonitor standalone (Q7=A, BR-U7-19/20/21)**
  Crear `deploy/monitoring/servicemonitor.yaml`: `monitoring.coreos.com/v1`, namespace `sentinel`, labels `release: monitoring`, selector `app.kubernetes.io/name: sentinel-core`, `namespaceSelector.matchNames: [sentinel]`, endpoint `port: metrics`, `path: /metrics`, sin `interval`/`scrapeTimeout`.

- [x] **Step 12 — Unit test: contrato del ServiceMonitor**
  `tests/unit/test_servicemonitor.py` (validación textual, sin PyYAML).

- [x] **Step 13 — NFR-U7-PERF-01 (informativo)**
  `tests/unit/core/test_metrics_scrape_latency.py`: p95 de 50 `collect(db=...)` < 1 s.

- [x] **Step 14 — Documentación de unidad**
  `README.md`: sección **Métricas (U7)** (14 familias, labels/allowlist, zero-fill, contadores post-commit, ServiceMonitor) y actualización del bullet de métricas.

- [x] **Step 15 — Validación local**
  `ruff check .` · `ruff format --check .` · `mypy src/sentinel` · `pytest ... --cov=sentinel --cov-fail-under=70` + gates gui/discovery/traffic/baseline · `docker build -t sentinel:test .`.

- [x] **Step 16 — Resumen de generación**
  Crear `aidlc-docs/construction/u7-metrics-exposure/code/code-generation-summary.md`.

- [x] **Step 17 — Registro de aprobación Infra U7**
  Actualizar `aidlc-docs/aidlc-state.md` y `audit.md` (Q1–Q6=A, ID-U7-01..06).

- [x] **Step 18 — Actualizar estado Code Generation U7**
  `aidlc-state.md` + `audit.md`: 18/18 steps, validación y estado COMPLETED.

---

## 3. Trazabilidad historias/diseño → pasos

| Elemento | Pasos |
|---|---|
| ST-M6-01 catálogo 14 familias | 1, 2, 5, 9 |
| ST-M6-02 contadores API/discovery | 3, 5, 7 |
| ST-M6-03 gauges SQLite | 4, 5, 7, 9 |
| ST-M6-04 contadores post-commit | 3, 8, 9 |
| ST-M6-05 ServiceMonitor | 11, 12 |
| BR-U7-01/04 allowlist + validación | 1, 2, 5, 10 |
| BR-U7-08 HELP/TYPE | 3, 5 |
| BR-U7-09 heartbeat | 6 |
| BR-U7-11/12 hook post-commit aislado | 3, 8, 9 |
| BR-U7-19/20/21 ServiceMonitor | 11, 12 |
| NFR-U7-PERF-01 | 13 |
