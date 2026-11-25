# NFR Design Patterns — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — NFR Design (Parte 2: Generation)
**Fecha**: 2026-11-19
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U6 — `src/sentinel/baseline/`
**Decisiones (plan Q1–Q7)**: **A en todas** — try/log sin retry ni circuit breaker (reintento natural por upsert idempotente); buffer de ≤5 muestras en memoria, descartado al congelar; evaluación acotada a la serie observada; confianza en la frontera U2 (sin re-validación); descomposición en 4 módulos (`config`/`statistics`/`conditions`/`indicators`); `Clock` Protocol local (cero acoplamiento U6→U5); `metric_samples()` bajo demanda sin caché.
**Entradas**: `nfr-requirements/*` (NFR-U6-*, TS-U6-01..13), Functional Design de U6 (BR-U6-01..27, FD Q1–Q13), precedentes NFR Design U4/U5.

---

## 1. Patrones de Resilience

### P1 — Degradación sin excepción propagada en el hook (→ NFR-U6-AVAIL-01, Q1=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `ConditionService.on_accepted` envuelve la evaluación completa en try/except: cualquier fallo (upsert de baseline/alerta, error inesperado) ⇒ `log event="condition_persistence_failed"` (o `condition_evaluation_failed`) + causa; el servicio **sigue vivo en memoria** y el próximo upsert reescribe la fila entera (idempotente por clave) — **sin retry, sin backoff, sin circuit breaker** dentro del request |
| Por qué | El reintento ya lo da la cadencia de ventana (≤300 s): reintentar en el `POST /ingest` alargaría el 202 sin garantía (el fallo suele ser transitorio/estructural, p. ej. disco lleno); un breaker añadiría estado no determinista a los tests |
| No hace | Sin contador de fallos consecutivos; sin cola diferida; **nunca propaga** al `IngestionService` (BR-U6-15, 202 intacto) |
| Verificación | `tests/unit/baseline/test_conditions.py -k persistence_failure_degrades`: repo que lanza ⇒ log + estado en memoria actualizado + sin excepción |

### P2 — Arranque tolerante a fallo de hidratación (→ NFR-U6-AVAIL-02, heredado)

| Elemento | Diseño |
|---|---|
| Mecanismo | `create_app` llama `BaselineRepository.list()` dentro de try: excepción ⇒ `log event="baseline_hydration_failed"` + causa y el `ConditionService` **arranca vacío** — todas las series re-establecen con supresión conservadora (5 muestras + ventana) hasta que la BD vuelva a responder |
| Por qué | Patrón `HealthService` U2: el Core nunca deja de estar vivo por un fallo de lectura; re-supresión = comportamiento conservador coherente con `t_first` efímero (BR-U6-13) |
| No hace | Sin fail-fast en `create_app`; sin reintentos de lectura en el arranque; sin marcar el Core «no sano» por esto solo (la salud la decide U8) |
| Verificación | `tests/unit/baseline/test_restart.py -k hydration_failure_starts_empty`: repo que lanza en `list()` ⇒ servicio vacío + log + Core sirve |

### P3 — Fail-fast de configuración fuera del path de request (→ NFR-U6-SEC-02, heredado)

| Elemento | Diseño |
|---|---|
| Mecanismo | `BaselineSettings` + loader estricto (`extra="forbid"`, `k>0`, `absolute_bps>0`, `interval≥1`, `timeout≥1`, `ABSOLUTE_BPS` sin default) ⇒ `ConfigError` **al arranque**, antes de aceptar tráfico; en runtime la config es `frozen` (inmutable) |
| No hace | Sin re-validación por observación; sin overrides en caliente (reinicio de K8s aplica cambios de `values.yaml`, patrón U4/U5) |
| Verificación | `tests/unit/baseline/test_config.py -k strict_env / -k invalid_config / -k defaults` |

---

## 2. Patrones de Performance

### P4 — Evaluación acotada a la serie observada (→ NFR-U6-PERF-01, Q3=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Por cada `TrafficObservation` aceptada, el hook procesa **solo las ≤3 claves** `metric|interface|protocol` de esa observación (`update_baseline` + `evaluate` por clave): O(1) por métrica, sin recorrer el mapa global de series |
| Por qué | Mantiene el presupuesto O(1) del hook (≤3 update + 1 evaluate + ≤2 upserts) **independiente de la cardinalidad**; además elimina el riesgo de re-fire de series ajenas (una serie que no recibió muestras no cambia de estado por efecto colateral) |
| No hace | Sin batch de todas las series; sin evaluación periódica en background |
| Verificación | Test unitario: hook con 2 series registradas, ingesta de 1 observación ⇒ solo la serie de esa obs se actualiza |

### P5 — Push síncrono post-commit + baseline informativo (→ NFR-U6-PERF-01, heredado NFR-Req Q1=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Evaluación **post-commit** dentro del mismo request de `POST /ingest` (hook `on_accepted` de `IngestionService`, solo observaciones insertadas) — frescura a cadencia de ventana, idempotente por construcción (BR-U6-14); test **informativo** que imprime p95 de ingesta con hook, **sin assert de duración** (envolvente NFR-PERF-03 se valida en lab/Build & Test) |
| No hace | Sin cola/worker en proceso; sin medición en CI que pueda flakear |
| Verificación | Test informativo que imprime p95 en la suite de integración |

---

## 3. Patrones de Scalability

### P6 — Buffer de establecimiento en memoria, congelado (→ Q2=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `BaselineSeries` guarda `samples: list[float]` con tope `BASELINE_SAMPLES=5` **solo durante el establecimiento**; al 5.º valor se calcula μ/s² (`n-1`), se marca `established` y el buffer se **descarta** — a partir de ahí solo se comparan umbrales |
| Cardinalidad | Bufers vivos = series en ventana de establecimiento (interfaces × 3 protocolos × 3 métricas, acotado); series congeladas consumen solo μ/s² persistidos |
| Crecimiento | Si el proceso muere, el buffer se pierde ⇒ re-establecimiento (coherente con `t_first` efímero); **cero cambios de esquema** (sin tabla `samples`) |
| Verificación | `test_baseline.py -k freeze_discards_buffer`; test de proceso «nuevo» tras reinicio ⇒ re-supresión |

### P7 — `metric_samples()` bajo demanda sin caché (→ Q7=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `indicators.metric_samples()` recorre el mapa en memoria y devuelve `[(nombre, labels, valor)]` (formato `Sample` de U2/U7) **en cada llamada** — O(series) con series acotadas; sin estado de caché ni invalidación |
| Por qué | El scrapeo de U7 llega como máximo cada 15–30 s; el coste de materializar decenas de tuplas es despreciable y el valor es siempre fresco (sin staleness) |
| No hace | Sin memoización; sin snapshot incremental |
| Verificación | Test: `metric_samples()` refleja inmediatamente el último estado tras `on_accepted` |

### P8 — Cardinalidad acotada y sin retención (→ NFR-U6-SCAL-01, heredado)

| Elemento | Diseño |
|---|---|
| Mecanismo | Series = interfaces × {tcp,udp,icmp,other} × 3 métricas con labels permitidos (`interface`/`protocol`/`state`/`collector`; **prohibidos** `src_ip`/`dst_ip`/`asset_id`, BR-21 U1); una fila `alerts` por activación; sin retención en MVP (la query pagina, NFR-OPS-05) |
| Crecimiento documentado | Retención/VACUUM queda como futuro (NFR-U6-SCAL-01) — sin código hoy |
| Verificación | `test_indicators.py -k label_cardinality` |

---

## 4. Patrones de Security

### P9 — Confianza en la frontera U2 (→ Q4=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | La `TrafficObservation` del hook ya cruzó Pydantic U1 (`extra="forbid"`) en el `Batch` y fue insertada en la BD: `on_accepted` lee `interface`/`protocol`/`observed_at`/valores con `getattr` defensivo mínimo (atributo ausente ⇒ log + skip de esa clave), **sin modelo de re-validación propio** |
| Por qué | La obs nace dentro del Core (no del exterior): re-validar duplicaría el contrato U1 y añadiría superficie de mantenimiento; el patrón U4 (confiar en la frontera del proveedor) ya está probado |
| No hace | Sin Pydantic nuevo en el hook; sin sanitización extra (campos ya tipados y acotados) |
| Verificación | Test: obs sin atributo ⇒ log + no-crash; revisión: `baseline/` sin `BaseModel` propio |

### P10 — Superficie cero + config estricta (→ NFR-U6-SEC-01/02, heredado)

| Elemento | Diseño |
|---|---|
| Mecanismo | U6 no añade: endpoints, routers, secretos, sockets, dependencias, deserialización propia ni capabilities; solo un hook in-process + 4 env floats validados (P3) + repos inyectados; logs JSON sin IPs ni alta cardinalidad (BR-12 U1) |
| Verificación | Revisión: `httpx`/`socket` ausentes en `baseline/`; `requirements.txt` y `Dockerfile` sin cambios en U6 |

---

## 5. Patrones de Maintainability

### P11 — Protocolos locales + inyección por constructor (→ Q6=A, NFR-U6-REL-01)

| Elemento | Diseño |
|---|---|
| Mecanismo | `conditions.py` define `Protocol` locales **duck-typing**: `BaselineRepository` (`list`/`upsert`), `AlertRepository` (`upsert`/`list`), `Clock` (`now() -> datetime`); `ConditionService(settings, baseline_repo, alert_repo, clock, logger)` se construye en `create_app` con los repos reales de U2 y un `SystemClock` propio (una línea); los tests inyectan repos fake en memoria + `FakeClock` |
| Por qué | Cero acoplamiento U6→U5 (no se importa `traffic.worker.Clock`), cero acoplamiento a `core.db` desde `baseline/` (frontera U4/U5), cero monkeypatch de `datetime`, cero `sleep` |
| No hace | Sin contenedor DI/registry; sin variables globales de módulo |
| Verificación | Suite completa sin `time.sleep` en `tests/**/baseline*`; firmas con seams obligatorios |

### P12 — PBT designado de baseline calculations (→ NFR-U6-MNT-02 / NFR-TECH-03)

| Elemento | Diseño |
|---|---|
| Mecanismo | `tests/property/test_baseline_statistics.py` (hypothesis) con 4 propiedades: (1) media/varianza `n-1` == brute force; (2) congelada: muestras extra no alteran μ/s²; (3) `select_threshold` monótono en `k` y `measured > threshold` consistente con fixtures bajo/igual/encima; (4) la máquina de estados nunca sale de `ConditionState` U1 y `suppressed ⇒ nunca firing` |
| Verificación | `pytest tests/property/test_baseline_statistics.py` en job `test` |

### P13 — Gate de cobertura como step separado (→ NFR-U6-MNT-01)

| Elemento | Diseño |
|---|---|
| Mecanismo | Step propio `Baseline coverage gate (U6, P11)` en `ci.yml` ⇒ `coverage report --include='*/baseline/*' --fail-under=70` sobre el **mismo** `.coverage` (espejo de los gates `core/`/`gui/`/`discovery/`/`traffic/`; ~0 s) |
| Verificación | Step presente en `ci.yml`; comando en local con `baseline/` ≥70 |

### P14 — Logging canónico del componente (→ NFR-U6-MNT-03)

| Elemento | Diseño |
|---|---|
| Mecanismo | `foundation.logging` con `component=baseline.*` y eventos snake_case: `baseline_established` (serie, n, mu, sigma), `condition_firing` (serie, measured, threshold), `condition_resolved`, `condition_evaluation_failed`, `baseline_hydration_failed`, `condition_persistence_failed` — campos escalares, sin IPs ni alta cardinalidad |
| No hace | Sin servidor de métricas propio (U7 expone `metric_samples()`); sin reutilizar eventos de U2 |
| Verificación | Test de log JSON con `event`/`component` canónicos |

---

## 6. Patrón de Tech Stack (cerrado — sin pregunta)

### P15 — Estadística stdlib, cero dependencias (→ NFR-U6-STACK-01, heredado)

| Elemento | Diseño |
|---|---|
| Mecanismo | Funciones puras con stdlib (`sum`/`len` para media y varianza muestral `n-1`) en `statistics.py`; Pydantic vía `foundation` solo para modelos U1; `hypothesis` solo en dev; Python 3.11+ |
| No hace | Sin numpy/pandas/scipy; sin dependencias pip nuevas en `requirements.txt` |
| Verificación | `requirements.txt` sin cambios en U6; `ruff`/`mypy` en verde |

---

## 7. Trazabilidad de patrones → NFR

| NFR (U6) | Patrón |
|---|---|
| NFR-U6-PERF-01 | P4 + P5 (baseline informativo de latencia) |
| NFR-U6-SCAL-01 | P6, P7, P8 |
| NFR-U6-AVAIL-01/02 | P1, P2 |
| NFR-U6-REL-01 | P11 (reloj inyectable + funciones puras) |
| NFR-U6-SEC-01 | P10 |
| NFR-U6-SEC-02 | P3, P10 |
| NFR-U6-MNT-01 | P13 |
| NFR-U6-MNT-02 | P12 (NFR-TECH-03 designado) |
| NFR-U6-MNT-03 | P14 |
| NFR-U6-MNT-04 | integración `TestClient` + BD temporal + reloj falso + hook real (NFR-Req Q9=A; wiring en `logical-components.md` §4) |
| NFR-U6-MNT-05 | heredado TS-U4-05/TS-U5-10 (ruff/format/mypy) |
| NFR-U6-STACK-01 | P15 |
| NFR-U6-OPS-01 | handoff env en `logical-components.md` §3 (U9) |
