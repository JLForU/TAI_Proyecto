# NFR Design Plan — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — NFR Design (Parte 1: Planning)
**Fecha**: 2026-11-24
**Estado**: Q1–Q8 = Acepto todo (2026-11-24); artefactos NFR Design generados; pendiente de aprobación
**Unidad**: U7 — `src/sentinel/core/metrics/` + `foundation/metrics_contract.py` (v2) + `deploy/monitoring/servicemonitor.yaml`
**Entradas**: `construction/u7-metrics-exposure/nfr-requirements/{nfr-requirements,tech-stack-decisions}.md` (aprobado 2026-11-24T06:17:17Z), FD U7 (aprobado 2026-11-24T05:54:38Z), precedentes NFR Design U4/U5/U6 (`nfr-design-patterns.md`, `logical-components.md`).

---

## 1. Contexto del assessment (Step 1 — analizado)

U7 incorpora NFR-U7-* (PERF-01/02, SCAL-01, AVAIL-01/02, REL-01, SEC-01/02, MNT-01..05, STACK-01, OPS-01) en un **exporter de scrape en hilo daemon** (`ThreadingHTTPServer`, host `0.0.0.0:9108`) + hook O(1) en el request de ingesta + manifiesto estático. Las decisiones de NFR Requirements (Q1–Q7 = A) y TS-U7-01..12 fijan ya: pipeline híbrido en funciones de módulo, contrato v2 con `assert_allowed`, 500 sin caché, hook compuesto aislado, SM standalone, sin auth, sin gate nuevo, PBT ligero, README.

**Ya decidido (NO se pregunta)**:
- 500 + `metrics_error` en fallo de scrape; sin caché ni render parcial (FD Q9, NFR-AVAIL-01).
- Hook con `try/except` por consumidor, sin excepción propagada (FD BR-U7-12, NFR-REL-01).
- Queries acotadas por índices existentes + `LIMIT`; retención/índice como futuro (NFR-PERF-01).
- Test informativo de latencia de scrape sin gate (NFR-PERF-02).
- Sin auth en 9108 (NFR-SEC-01), sin secretos en el manifiesto (NFR-SEC-02).
- Sin gate de cobertura nuevo; PBT `test_metrics_render.py`; README «Metrics & monitoring»; eventos `component=core.metrics` (MNT-01..04).
- Cero deps (STACK-01); host `0.0.0.0` ya fijado por U2 (scrape in-cluster).

**Hechos de código verificados**: `HealthService.health()` por scrape hace `SELECT 1` + `MAX(received_at)` + heartbeats `GROUP BY` + **3 COUNTs (assets/events/alerts)** + latest run — de los cuales U7 necesita solo los heartbeats (los COUNTs propios de U7 son distintos: `alerts WHERE firing`, `events` filtrado); `ThreadingHTTPServer` atiende scrapes concurrentes en hilos; SQLite en WAL permite lectores concurrentes.

**Categorías evaluadas** (todas con pregunta justificada):

| Categoría | Aplica | Pregunta |
|---|---|---|
| Resilience Patterns | Sí | Q1 (retry/aislamiento ante fallo puntual de un provider en el scrape y en el hook) |
| Scalability Patterns | Sí | Q2 (límite defensivo de series por scrape), Q3 (constante `K` del `LIMIT` en la query de últimas observaciones) |
| Performance Patterns | Sí | Q4 (heartbeats: `health()` completo vs método ligero), Q5 (concurrencia del scrape: lock o no) |
| Security Patterns | Sí | Q6 (escaping de label values en el render — inyección en formato de exposición) |
| Logical Components | Sí | Q7 (descomposición de módulos), Q8 (contratos de providers: Protocol vs import concreto) |

---

## 2. Checklist del plan

- [x] Analizar NFR Requirements y precedentes (Step 1)
- [x] Generar preguntas Q1–Q8 (Steps 2–3)
- [x] Guardar plan en `aidlc-docs/construction/plans/u7-metrics-exposure-nfr-design-plan.md` (Step 4)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-24: "Acepto todo" por precedente ⇒ Q1–Q8 = A)
- [x] Analizar respuestas y resolver ambigüedades — interacciones revisadas (Q1×FD Q9 sin retry; Q3×NFR-PERF-01 `K=500`; Q4×Q7 SQL en `collect.py`; Q6×SCAL-01 escaping sin cambiar catálogo de labels; Q8×FD Q8 funciones) ⇒ **sin FQ necesarias**
- [x] Generar `nfr-design/nfr-design-patterns.md` (Step 6)
- [x] Generar `nfr-design/logical-components.md` (Step 6)
- [ ] Presentar mensaje de completitud y esperar aprobación (Steps 7–8)
- [ ] Registrar aprobación en `audit.md` y marcar etapa en `aidlc-state.md` (Step 9)

---

## 3. Preguntas de NFR Design

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas **todas las recomendaciones**, responde `Acepto todo` (se aplicará la opción recomendada de cada pregunta).

### Question 1 — Reintento ante fallo puntual de un provider (Resilience Patterns)

Contexto: si un provider lanza dentro de `collect()` (BD, `ConditionService`), FD Q9/NFR-AVAIL-01 ⇒ 500 + log y el **próximo scrape** reintenta (patrón «la salud nunca rompe el proceso»). En el hook, NFR-REL-01 ya aísla consumidores con log. Queda abierto si añadir reintento **dentro** de un mismo request/scrape.

- **A (recomendado)**: **sin retry en el request**: un fallo ⇒ 500 (scrape) o log `metrics_hook_failed` (hook); el reintento natural es el siguiente scrape (cadencia de Prometheus ≈30 s) o la siguiente ingesta — cero estado, determinista, no alarga el request, coherente con U6 (Q1 NFR-Design U6 = try/log simple).
- **B**: retry ×1 inmediato del `collect()` completo antes de responder 500 (doble costo en fallo sostenido).
- **C**: circuit breaker: tras N fallos seguidos, responder 500 «rápido» sin ejecutar providers hasta que pasen M segundos.

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 2 — Límite defensivo de series por scrape (Scalability Patterns)

Contexto: las series por familia salen de datos propios: interfaces del sensor (acotadas en la práctica) × 4 protocolos fijos + contadores globales; `assert_allowed` impide labels no catalogados. Un escenario patológico (sensor reportando miles de nombres de interfaz) multiplicaría series sin tope.

- **A (recomendado)**: **sin cap duro**: la cardinalidad se acota por diseño (datos de nuestra propia ingesta validada, catálogo de familias cerrado, allowlist de 7 labels) — un cap añadiría pérdida silenciosa de series y lógica de agrupación que el operador no pidió; la revisión la da el test de cardinalidad (NFR-U7-SCAL-01).
- **B**: cap defensivo (p. ej. máx 200 samples por familia por scrape; excedente ⇒ `log event=metrics_cardinality_cap` y muestra agregada `interface="other"`) — protege contra escenario patológico a costa de complejidad y posible ocultamiento de datos.

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 3 — Constante del `LIMIT` en la query de últimas observaciones (Scalability / Performance Patterns)

Contexto: FD Q2=A/NFR-PERF-01: leer la última observación `traffic` por serie con `WHERE source='traffic' ORDER BY observed_at DESC LIMIT K` y tomar la primera aparición de cada `(interface, protocol)` en memoria. `idx_obs_source` cubre el orden. K demasiado pequeño pierde series antiguas (zero-fill); K enorme acerca el costo a «sin LIMIT».

- **A (recomendado)**: **`K = 500` como constante de módulo** documentada (cubre de largo las series vivas: interfaces reales × 4 protocolos con cientos de ventanas cada una); si una serie no aparece en las 500 filas más recientes, su gauge queda en zero-fill (ya estaba inactiva) — simple, acotado, testeable con fixtures.
- **B**: **sin `LIMIT`** (ordenar toda la fuente por `observed_at`) — correcto sin importar K, pero el costo crece sin cota con el tamaño de `observations`.
- **C**: **subquery por serie** (`DISTINCT interface, protocol` + `MAX(observed_at)` por serie) — exacto y acotado por nº de series, pero SQL más complejo y dos idas a la tabla.

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 4 — Fuente de los heartbeats en el scrape (Performance Patterns)

Contexto: hoy el wiring de U2 llama `HealthService(db).health().sensor_heartbeats` por scrape; `health()` además ejecuta `SELECT 1`, `MAX(received_at)`, **3 COUNTs** y el latest run — trabajo que U7 duplica o no necesita (los COUNTs de U7 son distintos: `alerts` solo `firing`, `events` solo tipos de cambio).

- **A (recomendado)**: **método ligero `HealthService.sensor_heartbeats()`** (edición aditiva mínima en `core/health/service.py`, reutiliza la misma query `GROUP BY sensor_id`); el wiring de U7 pasa a usarlo y `health()` queda intacta para `GET /health`. Ahorra ~5 queries por scrape sin cambiar comportamiento.
- **B**: **mantener `health()` completo** por scrape (cero edición en U2, precedente exacto del wiring actual) — paga las queries redundantes en cada scrape (baratas en lab, pero innecesarias).

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 5 — Concurrencia de los scrapes (Performance Patterns)

Contexto: `ThreadingHTTPServer` atiende cada scrape en un hilo; Prometheus y un `curl` manual pueden solaparse; SQLite en WAL admite lectores concurrentes; `collect()` es solo lectura (los contadores son `dict` de Python con GIL).

- **A (recomendado)**: **sin lock de scrape**: lecturas concurrentes vía `db.read()` (patrón ya usado por `health()` desde el hilo de métricas); los contadores se leen con `snapshot()` (copia) — cero contención, latencia mínima.
- **B**: `threading.Lock` alrededor de `collect()` — serializa scrapes (evita cualquier `SQLITE_BUSY` teórico bajo carga) a costa de cola de scrapes simultáneos (irrelevante a cadencia de 30 s, pero añade estado).

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 6 — Escaping de label values en el render (Security Patterns)

Contexto: `render_prometheus` hoy hace `f'{k}="{v}"'` sin escapar; el formato de exposición exige escapar `\` y `"` en valores. Los valores actuales (interfaces del sensor, estados del catálogo) son limpios en la práctica, pero un valor con `"` rompería el parseo de Prometheus (y sería un vector de inyección de líneas si un dato llegara sucio).

- **A (recomendado)**: **escapar `\` y `"` en cada label value al renderizar** (2 líneas, defensa en profundidad del formato; los HELP también se sanitizan de saltos de línea) — no depende de confiar en el origen de los datos.
- **B**: confiar en la validación upstream (interfaces/estados ya vienen de nuestro pipeline) — cero código nuevo, pero un dato sucio degrada el scrape entero de forma confusa.

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 7 — Descomposición de módulos (Logical Components)

Contexto: el FD ubica `ObservationCounters`, `collect()` v2 y `HELP` en `core/metrics/collect.py`, y `_compose_hooks` en `app.py`. El SQL de los gauges (4–5 queries) y el hook compositionado son los candidatos a extraer si el módulo crece.

- **A (recomendado)**: **todo en `collect.py` + `_compose_hooks` local en `app.py`** — un archivo de ~250–300 líneas con el pipeline coheso (contadores, providers, zero-fill, HELP); sin archivos ni imports nuevos; precedente: `collect.py` ya concentra counters+render.
- **B**: **submódulos**: `core/metrics/queries.py` (SQL de gauges, `DatabaseLike`) y `core/metrics/hooks.py` (`_compose_hooks`, reutilizable) — fronteras más nítidas, a cambio de 2 archivos e imports extra.

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 8 — Contratos de providers (Logical Components)

Contexto: `collect()` recibe `condition_service`, `db`, `obs_counters` opcionales; los tests unitarios deben inyectar mocks sin construir el stack real; `core` ya importa `baseline` en `baseline_wiring.py` (dirección permitida).

- **A (recomendado)**: **`Protocol` locales en `collect.py`** (solo los métodos usados: `metric_samples()`, `read()`) con duck-typing — tests con objetos simples, sin acoplamiento a clases concretas, precedente U6 (repos/clock inyectados con Protocol).
- **B**: **imports concretos** (`ConditionService`, `Database`) en las firmas — tipado completo de mypy sin Protocol, pero los tests deben construir/monkeypatchear clases reales y `collect.py` se acopla a más superficie.

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)
