# NFR Design Patterns — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — NFR Design (Parte 2: Generation)
**Fecha**: 2026-11-24
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U7 — `src/sentinel/core/metrics/` + `foundation/metrics_contract.py` (v2) + `deploy/monitoring/servicemonitor.yaml`
**Decisiones (plan Q1–Q8)**: **A en todas** — sin retry en request/scrape (reintento natural por cadencia); sin cap duro de series; `LIMIT K=500` como constante; `HealthService.sensor_heartbeats()` ligero; sin lock de scrape; escaping de `\`/`"` en labels; todo en `collect.py` + `_compose_hooks` en `app.py`; `Protocol` locales de provider.
**Entradas**: `nfr-requirements/*` (NFR-U7-*, TS-U7-01..12), Functional Design de U7 (BR-U7-01..24, FD Q1–Q11), precedentes NFR Design U4/U5/U6.

---

## 1. Patrones de Resilience

### P1 — Reintento natural por cadencia, sin retry en el request (→ NFR-U7-AVAIL-01/REL-01, Q1=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Fallo de cualquier provider dentro de `collect()` ⇒ try/except en el handler ⇒ `log event="metrics_error"` + causa + **500** (target `down` en Prometheus); el reintento lo hace **el siguiente scrape** (cadencia de Prometheus ≈30 s). En el hook: `_compose_hooks` envuelve **cada consumidor** en su propio try/except (`metrics_hook_failed`) — el fallo de un consumidor no afecta al otro ni al `202` |
| Por qué | Sin estado (contador de fallos, breaker) ⇒ determinismo de tests; no se alarga el scrape ni el `POST /ingest`; coherente con U6 (try/log simple) y con «la salud nunca rompe el proceso» |
| No hace | Sin retry ×1, sin backoff, sin circuit breaker, sin caché de último valor bueno, sin render parcial fabricado (FD Q9) |
| Verificación | `test_metrics.py -k scrape_error_500` (provider que lanza ⇒ 500 + `metrics_error`) + `-k hook_isolated` (un consumidor lanza ⇒ el otro incrementa) |

### P2 — Reinicio limpio sin recuperación de contadores (→ NFR-U7-AVAIL-02, heredado FD)

| Elemento | Diseño |
|---|---|
| Mecanismo | Contadores de proceso (`api`, `cycles`, `flows`, `arp`) nacen en 0 — Prometheus absorbe el reset de serie `counter`; los gauges se reconstruyen desde SQLite en el primer scrape post-restart y los indicadores U6 por hidratación de `ConditionService` |
| Por qué | Persistir contadores exigiría esquema/escrituras extra para un caso que el modelo de counter de Prometheus ya resuelve; los datos «valiosos» (inventario, alertas, baseline) **sí** viven en SQLite |
| No hace | Sin persistencia de contadores; sin warm-up diferido |
| Verificación | `test_metrics.py -k counter_reset` + integration (restart ⇒ familias presentes en el scrape) |

---

## 2. Patrones de Scalability

### P3 — Cardinalidad acotada por diseño, sin cap duro (→ NFR-U7-SCAL-01, Q2=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Tope de series = `interfaces_del_sensor × 4 protocolos fijos` para familias de serie + contadores globales de una etiqueta; catálogo **cerrado** de 14 familias; allowlist v2 de 7 labels con `assert_allowed()` por sample (rechaza cualquier label fuera de catálogo antes del render) |
| Por qué | Los datos provienen de nuestra propia ingesta validada (interfaces reales, protocolos del enum U1) — un cap duro perdería series silenciosamente y agregaría `interface="other"` sin pedido del operador; el test de cardinalidad da la vigilancia |
| No hace | Sin máximo de samples por familia; sin bucketing/agrupación; sin muestreo |
| Verificación | `test_metrics_contract.py -k assert_allowed_*` + `test_metrics.py -k no_forbidden_in_body` + PBT (Q4 NFR-Req) |

### P4 — Lectura acotada de últimas observaciones (`LIMIT K=500`) (→ NFR-U7-PERF-01, Q3=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `SELECT … FROM observations WHERE source='traffic' ORDER BY observed_at DESC LIMIT 500` (constante de módulo `LATEST_OBS_LIMIT = 500`, documentada) → en memoria, primera aparición por `(interface, protocol)` ⇒ gauge `bytes_per_second`; series no vistas en esas 500 filas ⇒ zero-fill (ya inactivas) |
| Por qué | `idx_obs_source` cubre el orden; K=500 da órdenes de magnitud de margen sobre las series vivas (interfaces reales × 4 protocolos); costo **constante** por scrape con independencia del tamaño de `observations` |
| No hace | Sin subquery por serie (Q3=C); sin DDL/índice nuevo (rompería «sin esquema nuevo»); sin `VACUUM`/retención (futuro global, anotado en NFR-U7-PERF-01) |
| Verificación | `test_metrics.py -k bytes_latest_window` (fixtures >K filas ⇒ series recientes tomadas, antigua en zero-fill) |

---

## 3. Patrones de Performance

### P5 — Heartbeats con método ligero (→ NFR-U7-PERF-01, Q4=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Nuevo método **aditivo** `HealthService.sensor_heartbeats() -> dict[str, str]` con la misma query `GROUP BY sensor_id` que ya usa `health()`; el `collect_fn` de U7 lo invoca en lugar de `health()` completo — ahorra `SELECT 1`, `MAX(received_at)`, 3 COUNTs y latest run **por scrape**; `health()` queda intacta para `GET /health` |
| Por qué | Los COUNTs de `health()` no coinciden con los gauges de U7 (`alerts` solo `firing`, `events` solo tipos de cambio) ⇒ duplicados inútiles; edición aditiva de ~10 líneas sin cambiar comportamiento de la API |
| No hace | Sin caché de heartbeats; sin cambiar la respuesta de `GET /health` |
| Verificación | `test_health.py` sin regresión + `test_metrics.py -k heartbeats_from_light_method` |

### P6 — Scrapes concurrentes sin lock (→ patrón de concurrencia, Q5=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `ThreadingHTTPServer` atiende cada scrape en un hilo; `collect()` es solo-lectura sobre SQLite WAL vía `db.read()` (patrón ya usado por `health()` desde el hilo de métricas) y lee contadores con `snapshot()` (copia bajo GIL) — lectores concurrentes sin serialización |
| Por qué | Prometheus + `curl` manual pueden solaparse sin efecto; un lock solo añadiría cola ante una cadencia de ~30 s; WAL ya garantiza un writer + N readers |
| No hace | Sin `threading.Lock`; sin pool de conexiones nuevo; sin rate-limiting del endpoint (NetworkPolicy U8 es el control) |
| Verificación | test de scrape concurrente simple (2 hilos ⇒ ambos 200) o revisión de ausencia de lock |

---

## 4. Patrones de Security

### P7 — Escaping del formato de exposición (→ NFR-U7-SEC-01/SCAL-01, Q6=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `render_prometheus` escapa `\` → `\\` y `"` → `\"` en **cada label value**; los textos HELP se sanitizan contra saltos de línea (una línea HELP por familia); `assert_allowed` ya impidió labels fuera de catálogo — doble capa: catálogo de labels + integridad del formato |
| Por qué | Un valor sucio (p. ej. interfaz con `"`) rompería el parseo de Prometheus o permitiría inyectar líneas/labels falsos en la exposition; son 2 líneas sin costo medible |
| No hace | Sin validación/normalización de los valores de entrada (interfaces siguen siendo strings libres de U5); sin auth nueva en 9108 (NFR-U7-SEC-01: NetworkPolicy U8) |
| Verificación | `test_metrics.py -k label_escaping` (label con `"`/`\` ⇒ render parseable, valores escapados) |

### P8 — Manifiesto de superficie mínima (→ NFR-U7-SEC-02, heredado)

| Elemento | Diseño |
|---|---|
| Mecanismo | `servicemonitor.yaml` contiene **solo** apiVersion/kind/metadata/selectores/endpoints — sin credenciales, sin `secretRef`, sin RBAC (eso es U8/SN-036..038); test `no_secrets` busca `password|token|secret|key` en el archivo; Dockerfile/imagen intactos |
| Verificación | `test_servicemonitor.py -k no_secrets` + revisión de diff |

---

## 5. Patrones de Operabilidad / Mantenibilidad

### P9 — Señal de fallo redundante y autocontenido (→ Q7 NFR-Req=A, MNT-04)

| Elemento | Diseño |
|---|---|
| Mecanismo | Fallo de scrape ⇒ **HTTP 500** (Prometheus: target `down`, alerta U8) **+** `log event=metrics_error` (`component=core.metrics`, con causa); hook ⇒ `metrics_hook_failed` — sin familia `scrape_errors_total` (el scrape caído no puede leerse a sí mismo fiablemente en el mismo request) |
| No hace | Sin self-instrumentación de errores; sin healthcheck nuevo del hilo de métricas |
| Verificación | `test_metrics.py -k scrape_error_500` (status + `event` en log) |

### P10 — PBT de invariantes del exporter (→ MNT-02, Q4 NFR-Req=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `tests/property/test_metrics_render.py`: (1) samples con labels del catálogo ⇒ render termina y cada sample aparece exactamente una vez; (2) label prohibido/fuera de allowlist ⇒ `ValueError`; (3) zero-fill ⇒ familias == `METRIC_FAMILIES` exacto |
| Por qué | `hypothesis` ya está (dev); barato y cubre el invariante central «contrato cerrado + formato válido» que los unitarios solo tocan por casos |

---

## 6. Matriz NFR → patrón → verificación

| NFR-U7 | Patrón | Verificación clave |
|---|---|---|
| PERF-01 | P4 (`LIMIT K=500`), P5 (heartbeats ligeros) | `bytes_latest_window`, `heartbeats_from_light_method`, sin DDL en diff |
| PERF-02 | (test informativo, NFR-Req) | `test_metrics_scrape_latency.py` imprime p50/p95 |
| SCAL-01 | P3 (sin cap + allowlist), P7 (escaping) | `assert_allowed_*`, `no_forbidden_in_body` |
| AVAIL-01 | P1 (500 + log, sin retry) | `scrape_error_500` |
| AVAIL-02 | P2 (restart limpio) | `counter_reset` |
| REL-01 | P1 (hook aislado) | `hook_isolated` |
| SEC-01 | P7 (formato), (sin auth decidido) | `label_escaping` |
| SEC-02 | P8 (manifiesto mínimo) | `no_secrets` |
| MNT-02 | P10 (PBT) | `tests/property/test_metrics_render.py` |
| MNT-04 | P9 (eventos canónicos) | `scrape_error_500` |
