# Functional Design Plan — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — Functional Design (Parte 1: Planning)
**Fecha**: 2026-11-19
**Estado**: GENERATED — Q1–Q13 = A (2026-11-19); artefactos FD generados; pendiente de aprobación
**Unidad**: U6 — `src/sentinel/baseline/` (línea base estadística, umbrales configurables con fallback absoluto, supresión durante establecimiento, indicadores de condición deterministas)
**Entradas**: `unit-of-work.md` (§U6), `unit-of-work-story-map.md` (ST-M5-01..04, todas documented-only con mínimo implementado para R-01/GT-04), `stories.md` (AC ST-M5-01..04), `requirements.md` (FR-BASE-01..05, FR-OBS-02), `component-methods.md` (§4 ConditionService C5), `components.md` (C5 Módulo), `implementation-scope.md` (M5: «se implementa solo lo necesario para R-01»), `demo-plan.md` (GT-01/GT-04), PRD §3.3/§3.4 (R-01), contratos de U1 (`Baseline`, `AlertCondition`, `ConditionState`, `METRIC_FAMILIES`) y U2 (tablas `baselines`/`alerts` + `BaselineRepository`/`AlertRepository` «los llena U6 — OQ-02», `HealthService.sensor_heartbeats`, `DiscoveryTrigger` como precedente de hook en ingesta).

---

## 1. Contexto de la unidad (Step 1 — analizado)

- **Responsabilidad**: línea base estadística (primeras 5 muestras, media y varianza muestral `n-1`), umbral configurable `μ + k·s` con fallback absoluto, supresión durante la ventana de establecimiento (25 s default) e indicadores de condición deterministas para U7/U8.
- **Alcance construido (implementation-scope §3)**: **solo lo mínimo para R-01/GT-04** — evaluación de umbral con fixtures dentro de U6; el diseño estadístico completo (y reglas R-02/R-04) se documenta. Historias ST-M5-01..04 **documented-only**.
- **Frontera**: no decide acciones automáticas, no llama a canales externos (alertas reales = PrometheusRule de U7/U8), no define labels de alta cardinalidad; pruebas con fixtures parametrizados (bajo/igual/encima del umbral; sin línea base), **sin dependencia de red**.
- **Depende de**: U1 (`Baseline`, `AlertCondition`, `ConditionState`, `UTCDateTime`, `ConfigError`, métricas contrato), U2 (esquema `baselines`/`alerts`, repos, `sensor_heartbeats`, hook de ingesta precedente `DiscoveryTrigger`), U5 (series `TrafficObservation` con `bytes_per_second`/`packets`/`flows`/`interface`/`protocol`/`window_start`).
- **Hechos que ya cierran diseño**: OQ-02 cerró el esquema exacto (U2 escribe schema, **U6 llena** `baselines`/`alerts`; `alert_id` = UUIDv5 por (condition, asset/metric, primera activación)); `ConditionState = baseline_establishing|firing|resolved|no_data`; U2 FD: «U6 consulta agregación de observaciones `traffic` … se define al implementar U6 sin cambiar el esquema base»; U2 FD: «U2 solo hace SELECT, evaluación es de U6»; ruta de AC de historias re-mapeable (precedente D-U5-04).
- **Categoría Frontend**: **no aplica** a U6 (sin UI; U3 ya consume `GET /api/v1/alerts`).

---

## 2. Checklist del plan

- [x] Analizar unidad, historias y restricciones
- [x] Generar preguntas de diseño funcional (Q1–Q13)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-19: "Acepto todo" ⇒ Q1–Q13 = A)
- [x] Analizar respuestas y resolver ambigüedades — interacciones revisadas (Q2×Q11 push sin vista; Q5×Q7 absoluto solo fuera de supresión; Q7×Q12 semántica de estados; Q9×Q10 catálogo vs alcance) ⇒ **sin FQ necesarias**
- [x] Generar `business-logic-model.md`, `business-rules.md`, `domain-entities.md` en `construction/u6-baseline/functional-design/`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño funcional

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Ubicación del paquete y frontera de imports

Contexto: `unit-of-work.md` §estructura define `src/sentinel/baseline/` (hermano de `core/`); los módulos U4/U5 tienen frontera estricta (solo `foundation` + HTTP, sin `sentinel.core`/`sqlite3`); pero C5 es un «Módulo» de Core y U2 ya inyecta dependencias en `app.state` (precedente: `DiscoveryTrigger` se arma en `create_app` y se invoca desde la ruta de ingesta).

- **A (recomendado)**: `src/sentinel/baseline/` con frontera estilo U4/U5 — importa solo `foundation` + stdlib; U2 (`create_app`) construye `ConditionService` y **inyecta** repositorios/callables (duck-typing, sin que `baseline/` importe `core`). Core importa baseline, nunca al revés.
- **B**: `baseline/` importa `sentinel.core.db.*` directamente (menos inyección, acoplamiento explícito a U2).
- **C**: módulo dentro de `src/sentinel/core/conditions/` (todo en U2).

[Answer]: A
### Question 2 — Momento de evaluación: push en ingesta vs pull al scrapear

Contexto: `component-methods.md` §4 firma `evaluate(window) -> list[Condition]` y `update_baseline(metric_key, sample)`; R-01: «Core publica condición verdadera cuando bytes/s supera el umbral»; GT-04 se verifica tras ingesta simulada de tráfico alto; precedente de hook: `DiscoveryTrigger` invocado desde la ruta de ingesta.

- **A (recomendado)**: **push** — tras persistir una observación `source=traffic` en `POST /ingest`, la ruta llama `ConditionService.on_traffic(observation)` (actualiza baseline + evalúa + persiste estado). Muestras sin leer BD; alerts/baselines frescos a cadencia de ventana (5 s); acoplo mínimo U2→U6 solo en el cableado de `app.state`.
- **B**: **pull** — `collect()` de métricas (U7) llama `evaluate()` leyendo las últimas ventanas de la BD. Desacoplado del ingesta, pero alerts/baselines solo se actualizan al scrapear (delay del intervalo de scrape) y U6 necesita lectura de BD.
- **C**: push + verificación pull (doble vía) para robustez.

[Answer]: A
### Question 3 — Dimensión de la serie (¿qué es un `metric_key`?)

Contexto: ST-M5-04 AC dice «vale 1 **para la interfaz/protocolo evaluado**»; labels permitidos U1: `component, protocol, interface, rule, state`; `Baseline.metric_key` es string libre; FR-BASE-02 habla de métrica «per flow metric».

- **A (recomendado)**: serie por `(interface, protocol, metric)` → `metric_key = "bytes_per_second|eth0|tcp"`; condición e indicador con labels `interface` + `protocol` (cardinalidad baja: pocas interfaces × 4 protocolos).
- **B**: serie global (todo el tráfico en un solo `metric_key`) — más simple, pero ignora «interfaz/protocolo» del AC.
- **C**: por interfaz solamente (sin protocolo).

[Answer]: A
### Question 4 — ¿Qué métricas llevan baseline (FR-BASE-02)?

Contexto: FR-BASE-02 pide μ y s² «per flow metric (bytes, packets, flows)»; implementation-scope dice «solo lo necesario para R-01» (R-01 evalúa **bytes/s**); ST-M5-01 AC habla de «cinco muestras consecutivas de bytes».

- **A (recomendado)**: baseline para **las 3 métricas** (bytes, packets, flows) con la misma función genérica `update_baseline` — costo marginal cero, satisface FR-BASE-01/02 completo; **condición R-01 solo sobre `bytes_per_second`** (las otras dos solo publican estado de baseline).
- **B**: mínimo estricto — solo `bytes_per_second`; packets/flows quedan documented-only.

[Answer]: A
### Question 5 — Configuración de `k` y umbral absoluto (¿defaults?)

Contexto: FR-BASE-03 «Helm-configurable `k`; absolute threshold as fallback»; ST-M5-02 AC «configurar k sin cambiar código»; PRD §3.3 «umbral TBD … **no se asignan umbrales arbitrarios**»; precedente de loader estricto U4/U5 (`SENTINEL_*` + `ConfigError`).

- **A (recomendado)**: loader propio `load_baseline_settings(env)` con `SENTINEL_BASELINE_K` (default `3.0`, `>0`) y `SENTINEL_BASELINE_ABSOLUTE_BPS` **sin default numérico** (opcional): si no hay baseline y no está configurado el absoluto ⇒ condición `no_data` (evita umbrales arbitrarios PRD); `SENTINEL_BASELINE_INTERVAL_SECONDS` default 5; sin editar `CoreSettings` (U1 intacto).
- **B**: como A pero con default numérico documentado para `ABSOLUTE_BPS` (p. ej. `1000000`).
- **C**: extender `CoreSettings` de U1 con los campos (edita U1; precedente Batch.reconcile).

[Answer]: A
### Question 6 — Ciclo de vida de la baseline

Contexto: PRD §3.3 «línea base **inicial**: cinco muestras consecutivas»; FR-BASE-01 «**first** 5 samples»; C5 `update_baseline` devuelve `BaselineState`; tabla `baselines.established` 0/1; determinismo requerido.

- **A (recomendado)**: **congelada** — primeras 5 muestras fijan μ/s² (`established=1`) y no se recalculan (salvo reinicio del proceso si no hay persistencia); determinista y mínima. Reset automático por gaps queda documentado como futuro.
- **B**: rolling — recalcula μ/s con las últimas 5 ventanas (más «vivo», pero deja de ser «primeras cinco muestras» del PRD y complica fixtures).
- **C**: congelada + re-establecimiento automático si la serie tiene un gap > N ventanas.

[Answer]: A
### Question 7 — Prioridad supresión vs fallback absoluto (ambigüedad FR-BASE-03×04)

Contexto: FR-BASE-04/ST-M5-03 «suprimir durante la ventana de inicialización (primeros 25 s)»; ST-M5-02 AC2 «baseline no disponible ⇒ usa umbral absoluto»; durante el establecimiento la baseline **no está disponible** — ¿el absoluto dispara igual?

- **A (recomendado)**: **la supresión tiene prioridad** durante el establecimiento (`n < 5` muestras o `now < inicio+25 s` ⇒ estado `baseline_establishing`, métrica condición = 0, sin fila firing). El fallback absoluto aplica **solo fuera** del establecimiento cuando la baseline no esté disponible (p. ej. `no_data` tras restart sin serie, métrica nueva posterior). Coherente con «no se disparan alertas basadas en línea base hasta que esté disponible» (PRD §3.3).
- **B**: el absoluto puede disparar incluso durante el establecimiento (no depende de la baseline).

[Answer]: A
### Question 8 — Persistencia: repos U2 inyectados vs solo memoria

Contexto: repos U2 ya existen y su docstring dice «los llena U6 — OQ-02»; `alerts` la consume GUI/report (U3) y `GET /api/v1/alerts`; `BaselineRepository.upsert/get/list`; U1 `Baseline`/`AlertCondition` modelados.

- **A (recomendado)**: **persistir ambos** — `BaselineRepository.upsert` por cada actualización de baseline y `AlertRepository.upsert` al transicionar (`firing`/`resolved`), con `alert_id` = UUIDv5 (condition + metric, primera activación, según U2 FD). Sobrevive restart; GUI/report/CSV muestran alertas reales.
- **B**: baseline persistida, alertas solo en memoria + métrica.
- **C**: todo en memoria (re-establece 25 s en cada restart; `alerts` queda sin filas ⇒ GUI sin datos).

[Answer]: A
### Question 9 — Nombres canónicos de los indicadores (AC vs catálogo U1)

Contexto: AC ST-M5-04/ST-M5-01 grepean `sentinel_traffic_threshold_exceeded`, `sentinel_baseline_status` (con valor `establishing`), `sentinel_collector_up{collector="traffic"}`; el catálogo U1 `METRIC_FAMILIES` ya tiene `sentinel_baseline_established` y `sentinel_collector_heartbeat_age_seconds`, **no** los tres del AC; U4 precedentó añadir familias al catálogo (edición U1 acotada).

- **A (recomendado)**: **los nombres del AC son canónicos** — añadir al catálogo U1 `sentinel_traffic_threshold_exceeded`, `sentinel_baseline_status` (labels `state`), `sentinel_collector_up` (label `collector`); mantener `sentinel_baseline_established` (0/1) y `sentinel_collector_heartbeat_age_seconds` existentes; U6 **produce** los valores, U7 (U7/next) los expone en `/metrics`.
- **B**: usar solo las familias ya existentes del catálogo y verificar los AC con esas (rompe el `grep` literal de los AC).
- **C**: los tres nombres nuevos viven solo en U6 sin tocar el catálogo (U7 los importará «a ciegas»).

[Answer]: A
### Question 10 — Alcance de indicadores y reglas en U6

Contexto: FR-BASE-05 lista R-01..R-04; implementation-scope: «solo lo necesario para R-01»; ST-M5-04 (documented-only) pide indicadores de tráfico **y** disponibilidad del sensor; R-02 (tasa ARP) ya la calcula U5; R-03 ya es evento de U2; R-04 sensor caído deriva de `sensor_heartbeats` de U2.

- **A (recomendado)**: implementar en U6: **condición R-01 completa** (baseline + umbral + supresión + alerta persistida) **+ los 3 indicadores de ST-M5-04** (`baseline_status`, `traffic_threshold_exceeded`, `collector_up` — este último es `heartbeat age > umbral`, barato); R-02/R-03/R-04 **sin AlertCondition persistida** (diseño documentado; consumidor final U7/U8).
- **B**: mínimo ultra-estricto — solo R-01 + `traffic_threshold_exceeded`; `baseline_status`/`collector_up` documentados.
- **C**: implementar R-01 y R-04 con alertas persistidas (R-02/R-03 documentados).

[Answer]: A
### Question 11 — Fuente de muestras y vista `traffic_windows`

Contexto: U2 FD menciona «`traffic_windows` … se define al implementar U6 sin cambiar el esquema base»; con Q2=A (push) las muestras llegan de la observación misma (`bytes_per_second`, `window_start`, `interface`, `protocol`), sin lectura de BD.

- **A (recomendado)**: con push, **no hace falta `traffic_windows`** — la muestra es la `TrafficObservation` persistida (ya es 1 fila = 1 ventana × protocolo); se documenta en domain-entities que la vista queda innecesaria para el mínimo implementado.
- **B**: crear la vista/consulta `traffic_windows` aunque haya push (por si se necesita históricos/rolling en el futuro).

[Answer]: A
### Question 12 — Semántica de comparación y bordes (fixtures)

Contexto: GT-04 «when **>** `μ + k·s`»; ST-M5-02 AC «**supera** `mu + 3·s`»; criterio de frontera de la unidad: fixtures **bajo/igual/encima** del umbral y sin línea base; determinismo requerido.

- **A (recomendado)**: estricto **`>`** — `measured > threshold` ⇒ `firing`; igual al umbral ⇒ no dispara (resuelve el fixture «igual»); sin baseline y sin absoluto ⇒ `no_data`; durante establecimiento ⇒ `baseline_establishing` (suprimido).
- **B**: `>=` (igual al umbral dispara).

[Answer]: A
### Question 13 — Rutas de verificación de los AC (re-mapeo D-U5-04)

Contexto: los AC citan `tests/unit/test_baseline.py -k five_samples`, `tests/unit/test_threshold.py -k mu_plus_k_sigma|absolute_fallback`, `tests/integration/test_baseline_suppression.py -k init_window|after_window` y `curl …/metrics | grep sentinel_baseline_status` (ruta de U7); la estructura de tests por unidad (`unit-of-work.md`) define `tests/unit/baseline/`.

- **A (recomendado)**: re-mapear a `tests/unit/baseline/test_baseline.py` (`-k five_samples`), `tests/unit/baseline/test_threshold.py` (`-k mu_plus_k_sigma`, `-k absolute_fallback`), `tests/integration/test_baseline_suppression.py` (`-k init_window`, `-k after_window`); los `curl /metrics` se verifican como tests unitarios de los **valores** que U6 produce (la exposición es U7) + `grep` sobre `render_prometheus` en el futuro U7.
- **B**: respetar rutas literales (renombrar/crear `tests/unit/test_baseline.py` en la raíz, como hacían los AC de U4 antes del re-mapeo).

[Answer]: A
---

## 4. Fuera de alcance de este plan (confirmado por scope)

- R-02 `ArpRateThresholdExceeded` y R-03 alert (U8 documented-only; R-02 la tasa ya la calcula U5).
- Exposición `/metrics` y `PrometheusRule` con duración `for` (U7/U8) — U6 solo produce valores/estados.
- Persistencia de series históricas/rolling window, resets por gap (diseño documentado).
- UI de umbrales (U3 ya consume `GET /api/v1/alerts`; sin frontend en U6).
