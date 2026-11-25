# Business Rules & Validation — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-24
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U7 — `src/sentinel/core/metrics/` + `deploy/monitoring/servicemonitor.yaml`
**Traza**: ST-M6-01..03, FR-CORE-02, FR-OBS-01/02, PRD §3.2 (BR-20..22); plan Q1–Q11 = Acepto todo; `component-methods.md` §5, `implementation-scope.md` M6, contratos U1/U2/U6.

---

## 1. Contrato de métricas (v2) y validación de labels

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U7-01 | `METRIC_FAMILIES` pasa a **14** familias: las 12 de U1 + `sentinel_assets_total` + `sentinel_asset_changes_total`; `collect()` garantiza `names == set(METRIC_FAMILIES)` sin extras (zero-fill) | Q3=C, ST-M6-02, SN-033 AC | `tests/unit/foundation/test_metrics_contract.py` (longitud/contenido 14) + `tests/unit/core/test_metrics.py -k no_extras` |
| BR-U7-02 | `ALLOWED_LABELS_DEFAULT` pasa a **7**: `component, protocol, interface, rule, state` + `collector, metric` (labels acotados de U6) | Q10=B, `baseline/indicators.py` | `test_metrics_contract.py -k allowed_labels` |
| BR-U7-03 | `assert_allowed(labels)` = denylist BR-21 (`src_ip`,`dst_ip`,`mac`,`asset_id` → `ValueError`) **y** allowlist v2 (label fuera de catálogo → `ValueError`); `assert_labels` (solo denylist) **no cambia** (compatibilidad U6) | Q10=B, BR-21 | `test_metrics_contract.py -k assert_allowed_*` (prohibido y fuera de allowlist rechazados) |
| BR-U7-04 | `collect()` y `render_prometheus()` validan **cada sample** con `assert_allowed` — ningún sample llega al body con label fuera de catálogo | Q10=B | `tests/unit/core/test_metrics.py -k label_enforced` (sample con `src_port` ⇒ `ValueError`) |
| BR-U7-05 | Sin labels de alta cardinalidad: `src_ip`/`dst_ip`/`mac`/`asset_id` jamás aparecen en `/metrics` (PRD §3.2) | BR-21 U1, ST-M6-02 AC | `test_metrics.py -k no_forbidden_in_body` (grep `src_ip\|dst_ip` ⇒ 0) + integration scrape |

## 2. Pipeline de scrape (Q1/Q9/Q11=A)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U7-06 | `collect()` acepta providers **opcionales**; provider ausente ⇒ familia en cero con `component=core` (compat con tests bare de U2) | Q1=A, precedente U2 | `test_metrics.py -k bare_collect_zeros` |
| BR-U7-07 | Orden del pipeline: contadores en proceso → gauges SQLite → heartbeats → `condition_service.metric_samples()` → zero-fill → `assert_allowed` → render | Q1=A | `test_metrics.py -k pipeline_*` (mocks por fuente) |
| BR-U7-08 | `render_prometheus` emite `# HELP` desde dict con un texto por familia (14; sin «U2 stub») y `# TYPE` = `counter` si `_total` si no `gauge` | Q11=A | `test_metrics.py -k help_per_family` + `-k type_by_suffix` |
| BR-U7-09 | Excepción en `collect()`/render ⇒ handler responde **500** y log `event=metrics_error`; no se fabrican valores parciales ni hay caché de último valor bueno | Q9=A | `test_metrics.py -k scrape_error_500` (provider que lanza ⇒ 500) |
| BR-U7-10 | Rutas: solo `GET /metrics` y `/` ⇒ 200; cualquier otra ⇒ 404 (sin cambios de U2) | ST-M6-01, U2 | `test_metrics.py -k 404` (existente, sin regresión) |

## 3. Contadores en proceso y hook (Q1/Q2=A)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U7-11 | `ObservationCounters.on_accepted(obs_list)` incrementa `flows_total += Σ int(obs.flows)` por `TrafficObservation` y `arp_messages += 1` por `ArpObservation`; solo observaciones **aceptadas** (post-commit ⇒ reenvío deduplicado no duplica) | Q2=A, BR-U2-07 | `test_metrics.py -k observation_counters` (lote aceptado vs deduplicado) |
| BR-U7-12 | `create_app` compone el slot único `on_accepted` de `IngestionService` con `_compose_hooks(condition.on_accepted, obs_counters.on_accepted)`: cada consumidor en su propio `try/except` (log `metrics_hook_failed`); un fallo de un consumidor no afecta al otro ni a la ingesta | Q1=A, precedente `DiscoveryTrigger` | `tests/integration/test_ingestion_hook.py` (sin regresión) + `test_metrics.py -k hook_isolated` |
| BR-U7-13 | Contadores de proceso se reinician con el proceso (reset aceptado por Prometheus); no se persisten | Q1=A (rechazo de B) | `test_metrics.py -k counter_reset` (nueva instancia ⇒ 0) |

## 4. Gauges de SQLite al scrape (Q1/Q3/Q4=A)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U7-14 | `sentinel_alerts_firing` = `COUNT(*) FROM alerts WHERE state='firing'`, labels `component=core` (**conteo global**, sin desglose por regla) | Q4=A | `test_metrics.py -k alerts_firing_count` (2 firing + 1 resolved ⇒ 2.0) |
| BR-U7-15 | `sentinel_assets_total` = `COUNT(*) FROM assets`, labels `component=core` | Q3=C | `test_metrics.py` + `test_metrics_endpoint.py` (seed 1 activo ⇒ 1.0) |
| BR-U7-16 | `sentinel_asset_changes_total` = `COUNT(*) FROM events WHERE type IN ('asset_first_seen','asset_missing','arp_mapping_changed','port_service_changed')` — **monótono** (tabla append-only), sin hook nuevo | Q3+C, Step 5 («hook o COUNT» ⇒ COUNT) | `test_metrics.py -k asset_changes_count` |
| BR-U7-17 | `sentinel_bytes_per_second` = por cada serie `(interface, protocol)` con datos, el `bytes_per_second` de la observación `traffic` **más reciente** de esa serie (labels `interface`,`protocol`); sin series ⇒ zero-fill `component=core` | Q2=A | `test_metrics.py -k bytes_latest_window` (dos series ⇒ dos samples; orden por `observed_at`) |

## 5. Integración de indicadores U6 (Q5/Q6=A)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U7-18 | `collect()` llama `condition_service.metric_samples()` **en cada scrape** (bajo demanda, sin caché, sin hilo propio) — respeta el contrato «U6 produce; U7 expone» | Q5=A, docstring `indicators.py` | `test_metrics.py -k u6_samples_included` (mock con estados ⇒ familias presentes) |
| BR-U7-19 | `sentinel_collector_up` sale de `ConditionService.collector_up()` (umbral `collector_timeout_seconds` de U6) con label `collector=traffic`; U7 **no** reimplementa el umbral ni lo deriva de `heartbeat_age` | Q6=A, SN-029 | `test_metrics.py -k collector_up_from_u6` (fresco⇒1, vencido/`None`⇒0) + `tests/unit/baseline/test_conditions.py` sin regresión |
| BR-U7-20 | Las familias de U6 se emiten **tal cual** las devuelve `metric_samples()` (labels `interface`/`protocol`/`metric`/`state`/`collector` — cubiertos por allowlist v2); zero-fill solo si U6 no devolvió esa familia | Q5+Q10 | `test_metrics.py -k u6_labels_allowed` |

## 6. ServiceMonitor (ST-M6-03, Q7=A)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U7-21 | Manifiesto en `deploy/monitoring/servicemonitor.yaml`: `kind: ServiceMonitor`, `metadata.name: sentinel-core`, `metadata.namespace: sentinel`, `labels.release: monitoring`, `spec.selector.matchLabels."app.kubernetes.io/name": sentinel-core`, `spec.namespaceSelector.matchNames: [sentinel]`, `spec.endpoints[0].port: metrics`, `path: /metrics` | Q7=A, ST-M6-03 AC, SN-032 (`port: metrics`) | `tests/unit/test_servicemonitor.py` (aserciones estructuradas **sin PyYAML** — restricción de deps) |
| BR-U7-22 | U7 **no** modifica `server.py`, `charts/` (U9), `values.yaml` ni reglas (U8); el `Service sentinel-core` con puerto `metrics:9108` lo crea el chart (AIDLC U9); aplicar el SM exige CRD de kube-prometheus-stack (SN-031) | Q7=A, frontera unit-of-work §U7 | revisión de diff en codegen (`git diff --stat` acotado a `core/metrics/`, `foundation/metrics_contract.py`, `deploy/`, tests) |

## 7. Frontera de unidad (criterio de frontera)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U7-23 | Endpoint responde formato Prometheus válido (`# HELP`/`# TYPE`/samples) — tests con fixtures, **sin red ni clúster** | unit-of-work §U7 | `test_metrics.py` + `test_metrics_endpoint.py` (puerto 0/efímero) |
| BR-U7-24 | Tests de **cardinalidad** con fixtures: parametrización de labels prohibidos/fuera de allowlist y verificación de cuerpo sin `src_ip`/`dst_ip` | unit-of-work §U7, ST-M6-02 | `test_metrics_contract.py -k parametrized_forbidden` + `test_metrics.py -k no_forbidden_in_body` |
