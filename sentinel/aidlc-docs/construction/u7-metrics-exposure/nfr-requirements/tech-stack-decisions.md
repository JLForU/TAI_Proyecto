# Tech Stack Decisions — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — NFR Requirements
**Fecha**: 2026-11-24
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U7 — `src/sentinel/core/metrics/` + `foundation/metrics_contract.py` (v2) + `deploy/monitoring/servicemonitor.yaml`
**Nota**: decisiones de la **unidad**; hereda TS-01..11 de U1, TS-U2-01..11 de U2, TS-U3 de U3, TS-U4-01..12 de U4, TS-U5-01..13 de U5, TS-U6-01..13 de U6 y el stack global de `requirements.md` §4. Plan NFR Q1–Q7 = A.

---

## 1. Tabla de decisiones

| # | Decisión | Elegida | Alternativas descartadas | Justificación | Origen |
|---|---|---|---|---|---|
| TS-U7-01 | Arquitectura del exporter | **Pipeline de scrape híbrido en `collect()`** (funciones de módulo con providers opcionales; `create_app` ensamla el `collect_fn`) | clase `MetricsExporter` (forma C6, FD Q8 descartó — diff mínimo); caché de gauges por TTL (invalidación/frescura, Q1=C); todo scrape-time con `COUNT(*)` de contadores (parseo/acoplamiento, Q1=B) | FD Q8=A + NFR Q1=A; precedente de docstrings «U7 sustituye `collect()` sin tocar familias/rutas» | FD §2, Plan NFR Q1 |
| TS-U7-02 | Fuentes de datos por familia | **Contadores en proceso** (`ApiRequestCounter`/`CycleCounter` existentes + `ObservationCounters` por hook) **+ gauges SQLite al scrape** (índices `idx_obs_source`/`idx_events_type`, con `LIMIT` en la query de últimas observaciones) **+ `ConditionService.metric_samples()` en el scrape** | índices nuevos en `observations` (DDL rompe «sin esquema nuevo» del FD); caché en proceso (Q1=C); re-implementar umbral de `collector_up` en U7 (duplica U6) | Plan NFR Q1=A, FD Q5/Q6, NFR-U7-PERF-01 | Plan NFR Q1 |
| TS-U7-03 | Contrato de métricas | **U1 v2**: `METRIC_FAMILIES` 12→14 (`+sentinel_assets_total`, `+sentinel_asset_changes_total`), `ALLOWED_LABELS_DEFAULT` 5→7 (`+collector`, `+metric`), nueva **`assert_allowed()`** (denylist+allowlist) aplicada por sample en `collect()`/`render_prometheus()`; `assert_labels` intacta | solo denylist (deja pasar labels no catalogados, Q10=A); re-etiquetar U6 para encajar en allowlist de 5 (toca código/test de U6, Q10=C); familias de inventario fuera del contrato (SN-033 no podría mostrar agregados, Q3=B) | FD Q3=C + Q10=B, ST-M6-02, SN-033 AC | FD §5 |
| TS-U7-04 | Alimentación de contadores de tráfico/ARP | **`_compose_hooks(condition.on_accepted, obs_counters.on_accepted)`** en `create_app` — un solo slot `on_accepted` de `IngestionService` (sin editar `service.py`), consumidores con `try/except` individual | editar `IngestionService` para multi-slot (toca U2 sin necesidad); incrementar dentro de `ConditionService.on_accepted` (acopla U6 a U7); leer `COUNT(*)` de `observations` en el scrape (Q1=B) | FD BR-U7-12, precedente composición en `create_app` (`DiscoveryTrigger`) | FD §3.1/§3.2 |
| TS-U7-05 | Ubicación del ServiceMonitor | **Manifiesto standalone `deploy/monitoring/servicemonitor.yaml`** (ns `sentinel`, selector `app.kubernetes.io/name: sentinel-core`, `release: monitoring`, endpoint `port: metrics`) | template de `charts/sentinel` (chart es de U9; ST-M6-03 quedaría sin artefacto); ambos (duplicidad a reconciliar) | FD Q7=A, ST-M6-03 AC, alineación con `deploy/monitoring/` de U8 | FD §3.4 |
| TS-U7-06 | Validación del manifiesto en tests | **Aserciones estructurales sin parser** (líneas clave: kind/name/namespace/selectores/endpoint + `no_secrets`) — `tests/unit/test_servicemonitor.py` | PyYAML (dep nueva prohibida, NFR-TECH-01); parser YAML propio (código muerto para un archivo); solo revisión manual (pierde regresión) | FD BR-U7-21, NFR-U7-STACK-01 | Plan NFR (fijado) |
| TS-U7-07 | Fallo de scrape | **500 + `log event=metrics_error`** (handler existente), sin caché de último valor | 200 con render parcial (enmascara fallo; target seguiría `up`); 200 solo con contadores (inconsistente); reintento/backoff (el próximo scrape reintenta) | FD Q9=A, NFR-U7-AVAIL-01, precedente U6 (degradar con log) | FD Q9 |
| TS-U7-08 | PBT | **`tests/property/test_metrics_render.py`** (3 propiedades: render íntegro, `assert_allowed` rechaza, zero-fill == catálogo) — opcional porque NFR-TECH-03 **no** designa metrics | sin PBT (Q4=B; la lógica de render/labels es barata de propiedad-testear); designar en NFR-TECH-03 (cambio de requisito global, no de U7) | Plan NFR Q4=A, precedente U5 (PBT adicional) | Plan NFR Q4 |
| TS-U7-09 | Gate de cobertura | **Sin gate nuevo**: global ≥70 cubre `core/metrics/` + `foundation/`; tests dedicados de U7 sostienen la barra | gate `*/core/metrics/*` ≥70 (precedente de subpaquete, Q5=B); gate `foundation/` ≥70 (decisión de repo más amplia que U7, Q5=C) | Plan NFR Q5=A, coherencia U1/U2 | Plan NFR Q5 |
| TS-U7-10 | Documentación | **Sección README «Metrics & monitoring»** (14 familias, curl, apply del SM, nota de cardinalidad) | solo docstrings (operador sin runbook mínimo); README + runbook `operations/` (runbooks globales = U11/EN-03) | Plan NFR Q6=A, NFR-OPS-03 | Plan NFR Q6 |
| TS-U7-11 | Auth del puerto 9108 | **Sin autenticación (confirmado)**: pull in-cluster, agregados sin datos sensibles, acceso restringido por NetworkPolicy (U8) | bearer token por env (config + handoff Helm + `authorization` en Prometheus, fuera de M6); bind `127.0.0.1` (imposible el scrape entre pods) | Plan NFR Q3=A, ST-M6-01/03, NFR-SEC-01 | Plan NFR Q3 |
| TS-U7-12 | Logging | **`foundation.logging` con `component=core.metrics`**: eventos canónicos `metrics_error`, `metrics_hook_failed` (con causa, sin IPs) | reutilizar eventos de U2 (el operador debe distinguir fallos del exporter); métrica self-instrumentada de errores (Q7=B: redundante con 500+log y no legible en el request fallido) | FD BR-U7-09/12, Plan NFR Q7=A, BR-12 U1 | Plan NFR Q7 |

---

## 2. Dependencias que U7 añade

**Pip: NINGUNA** (runtime y dev). U7 usa stdlib + pydantic vía `foundation.*` + `hypothesis` (dev, ya presente desde U1) + toolchain heredada. **Sin PyYAML** (validación textual del manifiesto).

| Paquete | Uso en U7 | Tipo |
|---|---|---|
| *(ninguno nuevo)* | — | — |

---

## 3. Impacto en artefactos heredados

| Artefacto | Cambio requerido por U7 |
|---|---|
| `src/sentinel/foundation/metrics_contract.py` | **+2 familias** (`sentinel_assets_total`, `sentinel_asset_changes_total`), **+2 labels** (`collector`, `metric`), nueva `assert_allowed()` (denylist+allowlist) — aprobado FD Q3/Q10 |
| `src/sentinel/core/metrics/collect.py` | `ObservationCounters` (nuevo), `collect()` v2 con providers opcionales (condition_service/db/obs_counters), dict `HELP` de 14 familias, `assert_allowed` por sample |
| `src/sentinel/core/api/app.py` | `_compose_hooks` para el slot `on_accepted`; `collect_fn` con providers nuevos (`app.state.condition`, `db`, contadores) |
| `deploy/monitoring/servicemonitor.yaml` | **Archivo nuevo** (Q7=A FD) — primer contenido de `deploy/monitoring/` (U8 añadirá `values.yaml` y `rules/`) |
| `.github/workflows/ci.yml` | **Sin cambios** (Q5=A; sin gate nuevo) |
| `README.md` | Sección **Metrics & monitoring** (14 familias, curl, apply SM) al final de U7 Code Gen (Q6=A) |
| `tests/property/test_metrics_render.py` | **Archivo nuevo** (PBT ligero, Q4=A) |
| Dockerfile / esquema SQLite / `CoreSettings` / `specs/backlog.md` | **Sin cambios** (NFR-SEC-02, FD frontera, decisión del usuario de no tocar backlog) |
