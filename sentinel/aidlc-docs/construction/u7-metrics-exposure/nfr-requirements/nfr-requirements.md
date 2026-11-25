# NFR Requirements — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 2: Generation)
**Fecha**: 2026-11-24
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U7 — `src/sentinel/core/metrics/` + `foundation/metrics_contract.py` (v2) + `deploy/monitoring/servicemonitor.yaml`
**Decisiones (plan Q1–Q7)**: **A en todas** (2026-11-24).
**Entradas**: Functional Design de U7 (aprobado 2026-11-24T05:54:38Z), `requirements.md` §3/§4/§5, U1–U6 `tech-stack-decisions.md`, `implementation-scope.md` (M6).

---

## 1. Alcance

NFR **específicos de U7** (exporter real de métricas en `:9108`: pipeline de scrape híbrido, contrato U1 v2 de 14 familias con allowlist enforceada, hook O(1) post-commit, manifiesto ServiceMonitor). Hereda sin cambio TS-01..11 de U1, TS-U2-01..11, TS-U3, TS-U4-01..12, TS-U5-01..13, TS-U6-01..13 y el stack global (Python 3.11, sin deps nuevas).

**Fijados por requisito/aprobados (no se preguntaron)**:
- **FD Q1–Q11** (pipeline híbrido, 500 sin caché en error de scrape, `assert_allowed` por sample, HELP dict, SM en `deploy/monitoring/`, funciones de módulo, sin tocar `server.py`).
- **NFR-SEC-01** (SECURITY blocking), **NFR-SEC-02** (non-root; U7 no toca imagen), **NFR-SEC-03** (scan CI global).
- **NFR-AVAIL-01/02** (single-sensor; restart ⇒ contadores en cero aceptados, gauges reconstruidos desde SQLite).
- **NFR-TECH-03**: PBT designado completo (Nmap XML, flow normalization, baseline) — metrics **no** está designado (Q4 = opcional, respondido A).
- **NFR-PERF-03** (API p95 <500 ms): el scrape no compite con el path de la API; el hook añade 2 incrementos O(1) por lote (el test informativo de ingesta de U6 sigue cubriendo el hook completo).
- **Índices existentes** `idx_obs_source` y `idx_events_type` ⇒ sin cambio de esquema; **sin auth en 9108** (Q3=A); **sin gate de cobertura nuevo** (Q5=A).
- **Usability no aplica** (sin UI; dashboards son U8).

---

## 2. Requisitos no funcionales de U7

### 2.1 Rendimiento y capacidad (Performance / Scalability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U7-PERF-01 | **Scrape con lecturas acotadas por índice**: ≤5 lecturas SQLite por scrape (`COUNT alerts`, `COUNT assets`, `COUNT events WHERE type IN (4)` vía `idx_events_type`, última obs `traffic` por serie vía `idx_obs_source` con `LIMIT` razonable, `HealthService.health()`); cadencia la decide Prometheus (default del stack ≈30 s); si `observations`/`events` crecen fuera de laboratorio ⇒ revisar retención/VACUUM o índice adicional como **futuro** (no en U7) | Plan Q1=A, FD §3.3 | query de última ventana usa `WHERE source='traffic' ORDER BY observed_at DESC LIMIT …`; revisión de diff sin DDL |
| NFR-U7-PERF-02 | **Test informativo de latencia de scrape**: N scrapes de `GET /metrics` contra DB sembrada (activos + observaciones + alertas + estados U6) imprime p50/p95 **sin assert de duración** (sin gate en CI); Build & Test lo registra con `-s` — precedente NFR-U6-PERF-01 | Plan Q2=A, NFR-PERF-03 | `tests/unit/core/test_metrics_scrape_latency.py` (informativo, imprime p50/p95) |
| NFR-U7-SCAL-01 | **Cardinalidad acotada**: 14 familias cerradas; series limitadas a `interfaces × {tcp,udp,icmp,other} × familias de serie` + contadores globales con `component`/`state`; labels solo de la allowlist v2 (7); **prohibidos** `src_ip`/`dst_ip`/`mac`/`asset_id` (BR-21) — ningún hostname/IP en HELP ni labels | FD BR-U7-01..05, PRD §3.2, ST-M6-02 | `test_metrics_contract.py -k assert_allowed_*` + `test_metrics.py -k no_forbidden_in_body` (grep del body ⇒ 0) |

### 2.2 Disponibilidad y fiabilidad (Availability / Reliability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U7-AVAIL-01 | **Error de scrape ⇒ 500 + `log event=metrics_error`** (`component=core.metrics`): target `down` en Prometheus (señal que U8 alertará); **sin caché** de último valor bueno ni render parcial fabricado; proceso Core **nunca** muere por un scrape fallido (handler ya captura) | FD Q9=A, NFR-AVAIL-01 | `test_metrics.py -k scrape_error_500` (provider que lanza ⇒ 500 + log) |
| NFR-U7-AVAIL-02 | **Restart limpio**: contadores de proceso (`api`, `cycles`, `flows`, `arp`) vuelven a 0 (reset aceptado por Prometheus); gauges (`assets_total`, `alerts_firing`, `asset_changes_total`, `bytes_per_second`, heartbeat) se reconstruyen desde SQLite al primer scrape; indicadores U6 se rehidratan por `ConditionService` (FD U6) | FD BR-U7-13, NFR-AVAIL-02 | `test_metrics.py -k counter_reset` + integration (restart con DB ⇒ familias presentes) |
| NFR-U7-REL-01 | **Hook compuesto aislado**: `_compose_hooks` ejecuta `condition.on_accepted` y `obs_counters.on_accepted` cada uno en su propio `try/except` (log `event=metrics_hook_failed`); fallo de un consumidor no afecta al otro ni al `202` de la ingesta | FD BR-U7-12 | `test_metrics.py -k hook_isolated` + `tests/integration/test_ingestion_hook.py` sin regresión |

### 2.3 Seguridad (Security — extensión SECURITY blocking)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U7-SEC-01 | **Puerto 9108 sin autenticación (confirmado, no olvido)**: pull interno in-cluster; contenido = agregados permitidos por allowlist (sin IPs/hostnames/`asset_id`); restricción de acceso = NetworkPolicy del namespace (U8, SN-038); token/binder localhost descartados (romperían el scrape de Prometheus) | Plan Q3=A, NFR-SEC-01, ST-M6-01 | revisión de decisión en este documento + `test_metrics.py -k no_forbidden_in_body` |
| NFR-U7-SEC-02 | **Sin superficie nueva**: mismo handler/`MetricsServer` de U2 (sin rutas, sin auth middleware, sin deserialización propia); manifiesto ServiceMonitor **sin secretos** (solo metadata/selectores/puerto); sin deps pip nuevas; SECURITY blocking hereda sin cambios (Dockerfile intacto) | FD §1, Q3=A, NFR-SEC-01/02 | revisión de diff (sin cambios en `server.py`/Dockerfile) + `test_servicemonitor.py -k no_secrets` (ausencia de `password|token|secret|key`) |

### 2.4 Mantenibilidad (Maintainability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U7-MNT-01 | **Sin gate de cobertura nuevo**: el global `--cov-fail-under=70` cubre `core/metrics/` y `foundation/`; los tests dedicados de U7 (unit + integration + property) sostienen la barra; coherente con U1/U2 (sin gate `foundation`/`core`) | Plan Q5=A | `ci.yml` sin pasos nuevos (solo gates existentes) |
| NFR-U7-MNT-02 | **PBT ligero adicional** (no designado; Q4=A) en `tests/property/test_metrics_render.py`: (1) samples con labels del catálogo ⇒ render termina y cada sample aparece una vez; (2) labels prohibidos/fuera de allowlist ⇒ `ValueError`; (3) zero-fill ⇒ familias exactas == `METRIC_FAMILIES` | Plan Q4=A, precedente U5 (PBT adicional) | `pytest tests/property/test_metrics_render.py` en job `test` |
| NFR-U7-MNT-03 | **Documentación README «Metrics & monitoring»** (Q6=A): tabla de 14 familias (tipo/labels/fuente), `curl localhost:9108/metrics`, `kubectl apply -f deploy/monitoring/servicemonitor.yaml` (requiere kube-prometheus-stack), nota de cardinalidad/allowlist | Plan Q6=A, NFR-OPS-03 | sección en `README.md` al cerrar Code Gen |
| NFR-U7-MNT-04 | **Eventos de log canónicos** `component=core.metrics` snake_case: `metrics_error` (scrape fallido, con causa), `metrics_hook_failed` (consumidor del hook, con causa) — sin valores de alta cardinalidad (sin IPs) | FD BR-U7-09/12, BR-12 U1 | `test_metrics.py -k scrape_error_500` (assert de `event`) |
| NFR-U7-MNT-05 | `ruff check` + `ruff format --check` + `mypy` en verde sobre `core/metrics/`, `foundation/metrics_contract.py` y tests nuevos (hereda TS-04/05) | TS-04/05 | job `lint`/`typecheck` de CI |

### 2.5 Stack técnico (Tech Stack)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U7-STACK-01 | **Cero dependencias pip nuevas** (runtime y dev): stdlib + pydantic vía `foundation` + `hypothesis` (solo dev, ya presente); **sin PyYAML** — validación del manifiesto con aserciones estructurales sobre líneas (FD BR-U7-21) | Plan (fijado), Q4=A, NFR-TECH-01/02 | `requirements.txt` sin cambios en U7 |

### 2.6 Operaciones (Ops)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U7-OPS-01 | **Handoff del ServiceMonitor**: el manifiesto se aplica con `kubectl apply -f deploy/monitoring/servicemonitor.yaml` **después** de instalar kube-prometheus-stack (SN-031); el `Service sentinel-core` con puerto nombrado `metrics:9108` lo crea el chart (AIDLC U9) — U7 solo publica el archivo y lo documenta (README, NFR-U7-MNT-03) | Q7=A (FD), ST-M6-03, NFR-OPS-01 | `test_servicemonitor.py` + nota de orden en README |

---

## 3. Trazabilidad NFR → historias / reglas globales

| NFR-U7 | Historias / reglas |
|---|---|
| NFR-U7-PERF-01/02 | ST-M6-01 (scrape), NFR-PERF-03 |
| NFR-U7-SCAL-01 | ST-M6-02, BR-21 U1, PRD §3.2 |
| NFR-U7-AVAIL-01/02 | FD Q9, NFR-AVAIL-01/02, GT-05 (target down ⇒ alerta U8) |
| NFR-U7-REL-01 | FD BR-U7-12, BR-U2-07 (ingesta intacta) |
| NFR-U7-SEC-01 | ST-M6-01/03, NFR-SEC-01, SN-032 (pull) |
| NFR-U7-SEC-02 | NFR-SEC-01/02/03 |
| NFR-U7-MNT-01 | gates globales/por paquete existentes |
| NFR-U7-MNT-02 | NFR-TECH-03 (no designado ⇒ opcional, Q4=A) |
| NFR-U7-MNT-03 | NFR-OPS-03, ST-M6-03, SN-033 |
| NFR-U7-MNT-04 | BR-12 U1, FD BR-U7-09/12 |
| NFR-U7-STACK-01 | NFR-TECH-01/02 |
| NFR-U7-OPS-01 | NFR-OPS-01, SN-031→SN-032 (orden de aplicación) |
