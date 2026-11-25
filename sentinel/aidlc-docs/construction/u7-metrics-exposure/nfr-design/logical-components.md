# Logical Components — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — NFR Design
**Fecha**: 2026-11-24
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U7 — `src/sentinel/core/metrics/` + `foundation/metrics_contract.py` (v2) + `deploy/monitoring/servicemonitor.yaml`
**Decisiones clave**: Q1=A (sin retry en request), Q2=A (sin cap de series), Q3=A (`LIMIT K=500`), Q4=A (`sensor_heartbeats()` ligero), Q5=A (sin lock), Q6=A (escaping de labels), Q7=A (todo en `collect.py` + `_compose_hooks` en `app.py`), Q8=A (`Protocol` locales).

---

## 1. Componentes lógicos de U7

| Componente | Archivo | Responsabilidad | NFR / patrón |
|---|---|---|---|
| Contrato v2 | `foundation/metrics_contract.py` (edición) | `METRIC_FAMILIES` 14 (+`sentinel_assets_total`, +`sentinel_asset_changes_total`), `ALLOWED_LABELS_DEFAULT` 7 (+`collector`, +`metric`), nueva **`assert_allowed()`** (denylist BR-21 + allowlist); `assert_labels`/`metric_name`/`FORBIDDEN_LABELS` intactos | SCAL-01 (P3), FD Q3/Q10 |
| `ObservationCounters` | `core/metrics/collect.py` | Contador de proceso: `on_accepted(obs_list)` incrementa `flows += Σ int(obs.flows)` (`TrafficObservation`) y `arp_messages += 1` (`ArpObservation`); `snapshot()` copia — solo aceptadas (post-commit ⇒ dedup no duplica) | AVAIL-02 (P2), FD BR-U7-11/13 |
| Pipeline `collect()` | `core/metrics/collect.py` (edición) | Firma v2 con providers opcionales (`api_requests`, `cycles`, `heartbeats`, `condition_service`, `db`, `obs_counters`, `now`): contadores → gauges SQLite (`COUNT` alerts/assets/events-con-cambio + última obs `traffic` `LIMIT 500`) → `sensor_heartbeats()` → `metric_samples()` U6 → **zero-fill** (familia sin muestra ⇒ `component=core`, 0.0) → `assert_allowed` por sample | PERF-01 (P4/P5), AVAIL-01 (P1), SCAL-01 (P3) |
| Dict `HELP` + render | `core/metrics/collect.py` (edición) | `HELP: dict[str,str]` de 14 entradas (sin «U2 stub»); `render_prometheus` con **escaping** de `\`/`"` en label values y HELP sanitizado; TYPE por sufijo `_total` | MNT-04, SEC-01 (P7) |
| Composición de hook | `core/api/app.py` (edición acotada) | `_compose_hooks(*fns)` → callable que invoca cada consumidor en su propio `try/except` (log `metrics_hook_failed`); wiring: `IngestionService(on_accepted=_compose_hooks(condition.on_accepted, obs_counters.on_accepted))` y `collect_fn` con providers (`app.state.condition`, `db`, contadores, `sensor_heartbeats`) | REL-01 (P1), FD BR-U7-12 |
| Heartbeats ligeros | `core/health/service.py` (edición aditiva) | Método `sensor_heartbeats() -> dict[str, str]` con la misma query `GROUP BY sensor_id` que `health()`; `health()` sin cambios | PERF-01 (P5) |
| Constante `LATEST_OBS_LIMIT` | `core/metrics/collect.py` | `LATEST_OBS_LIMIT = 500` documentada para la query de últimas observaciones | PERF-01 (P4), Q3=A |
| Manifiesto SM | `deploy/monitoring/servicemonitor.yaml` (nuevo) | ServiceMonitor `sentinel-core` ns `sentinel`, `release: monitoring`, selector `app.kubernetes.io/name: sentinel-core`, endpoint `port: metrics`, `path: /metrics` — sin secretos | SEC-02 (P8), OPS-01, FD §3.4 |
| Tests unitarios | `tests/unit/core/test_metrics.py` (edición), `tests/unit/foundation/test_metrics_contract.py` (edición), `tests/unit/test_servicemonitor.py` (nuevo) | Pipeline por fuente, zero-fill, HELP/TYPE, escaping, 500, hook aislado, contadores, `bytes_latest_window`, contrato 14/7/`assert_allowed`, manifiesto (sin PyYAML) | MNT-01/04, SCAL-01 |
| Tests integración | `tests/integration/test_metrics_endpoint.py` (nuevo) | `create_app` + DB temporal + scrape real: `assets_total` con activo seed, muestras U6 tras ingest, heartbeats, ausencia de `src_ip`/`dst_ip` | AVAIL-02, SCAL-01 |
| PBT | `tests/property/test_metrics_render.py` (nuevo) | 3 propiedades: render íntegro/único por sample, `assert_allowed` rechaza, zero-fill == catálogo | MNT-02 (P10) |
| Test informativo latencia | `tests/unit/core/test_metrics_scrape_latency.py` (nuevo) | N scrapes contra DB sembrada ⇒ imprime p50/p95 **sin assert** (sin gate) | PERF-02 |

---

## 2. Layering interno (Q1/Q4/Q5/Q7=A — scrape en hilo daemon, sin retry ni lock)

```text
[create_app — app.py]                                     (ediciones acotadas de U7)
        │
        ├─ obs_counters = ObservationCounters()                       [nuevo]
        ├─ IngestionService(on_accepted=_compose_hooks(
        │       condition.on_accepted,        ← U6 intacto            [REL-01 P1]
        │       obs_counters.on_accepted))    ← U7                    [FD BR-U7-11]
        └─ MetricsServer(collect_fn=lambda: collect(                   [server.py intacto]
                api_requests=…, cycles=…,
                heartbeats=HealthService(db).sensor_heartbeats,        [P5 método ligero]
                condition_service=app.state.condition,                 [P: metric_samples()]
                db=db, obs_counters=obs_counters))

POST /ingest ─► IngestionService.process ─ post-commit ─► _compose_hooks
                                                      ├─ ConditionService.on_accepted  (U6)
                                                      └─ ObservationCounters.on_accepted (flows/arp)

GET :9108/metrics ─► hilo ThreadingHTTPServer ─► _render ─► collect()  [sin lock, P6]
        │  1. contadores en proceso (snapshot)
        │  2. gauges SQLite: COUNTs (idx_events_type) + última obs (idx_obs_source, LIMIT 500)  [P4]
        │  3. sensor_heartbeats()                                       [P5]
        │  4. condition_service.metric_samples() → familias U6          [sin caché]
        │  5. zero-fill → assert_allowed por sample                     [P3]
        │  6. render (HELP dict, escaping \ y ")                        [P7]
        ├─ ok   ⇒ 200 text/plain; version=0.0.4
        └─ excepción ⇒ log metrics_error + 500                          [P1, sin retry]

kubectl apply -f deploy/monitoring/servicemonitor.yaml
        └─ Prometheus (kube-prometheus-stack) ─ scrape pull → :9108/metrics  [sin auth, NFR-SEC-01]
```

---

## 3. Impacto por archivo (resumen de ediciones)

| Archivo | Tipo de cambio | Origen |
|---|---|---|
| `src/sentinel/foundation/metrics_contract.py` | +2 familias, +2 labels, `assert_allowed()` | FD Q3/Q10 |
| `src/sentinel/core/metrics/collect.py` | `ObservationCounters`, `collect()` v2, `HELP`, escaping, `LATEST_OBS_LIMIT`, SQL de gauges | FD Q1/Q2, plan NFR-Design Q3/Q6/Q7 |
| `src/sentinel/core/api/app.py` | `_compose_hooks` + `collect_fn` con providers | FD BR-U7-12 |
| `src/sentinel/core/health/service.py` | método aditivo `sensor_heartbeats()` | plan NFR-Design Q4 |
| `deploy/monitoring/servicemonitor.yaml` | archivo nuevo | FD Q7, ST-M6-03 |
| `README.md` | sección «Metrics & monitoring» | NFR-Req Q6 (MNT-03) |
| Tests: `test_metrics.py`, `test_metrics_contract.py`, `test_servicemonitor.py`, `test_metrics_endpoint.py`, `test_metrics_render.py`, `test_metrics_scrape_latency.py` | edición/nuevos | MNT-01/02/04, PERF-02 |
| `server.py`, Dockerfile, esquema, `CoreSettings`, `ci.yml`, `specs/backlog.md` | **sin cambios** | FD frontera, NFR-Req Q5 |

---

## 4. Frontera de componentes (qué NO se toca)

- **`MetricsServer`/`server.py`**: solo consume `collect_fn` (docstring «U7 sustituye el `collect` sin tocar este servidor»).
- **`IngestionService`**: slot único `on_accepted` intacto — la composición vive en `create_app`.
- **`baseline/` (U6)**: consumido vía `ConditionService.metric_samples()`/`collector_up()`; cero ediciones.
- **`HealthService.health()`**: comportamiento de `GET /health` idéntico; solo se añade el método ligero.
- **Repos U2**: sin métodos nuevos — el SQL de gauges vive en `collect.py` (Q7=A; `DatabaseLike`/`Protocol` local con `read()`).
