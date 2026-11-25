# NFR Requirements Plan — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 1: Planning)
**Fecha**: 2026-11-19
**Estado**: GENERATED — respuestas todas A (2026-11-19); artefactos generados; pendiente de aprobación
**Unidad**: U6 — `src/sentinel/baseline/`
**Entradas**: `construction/u6-baseline/functional-design/*` (aprobado 2026-11-19T07:35:00Z), `requirements.md` §3 NFR + §4 constraints + §5, U1 `tech-stack-decisions.md` (TS-01..11), U2 (TS-U2-01..11), U3, U4 (TS-U4-01..12), U5 (TS-U5-01..13), `implementation-scope.md` (M5), `unit-of-work.md` §U6.

---

## 1. Contexto del assessment (Step 1 — analizado)

U6 es el **servicio de condiciones deterministas**: estadística pura (μ, s² `n-1`), umbral `μ + k·s` con fallback absoluto, supresión durante establecimiento, persistencia de `baselines`/`alerts` vía repos U2 inyectados e indicadores para U7. Corre **dentro del Core** (hook post-commit en la ingesta), sin endpoints propios, sin red, sin UI.

**Ya decidido (NO se pregunta)**:
- **NFR-TECH-03 designa PBT para baseline calculations** — el PBT es **obligatorio** para U6 (la pregunta es el alcance, Q2); `hypothesis` dev ya presente.
- **Sin dependencias pip nuevas**: stdlib + pydantic (vía `foundation`) + `hypothesis` (dev); Python 3.11 (NFR-TECH-02).
- **Config estricta** `SENTINEL_BASELINE_*` con `ConfigError` fail-fast (FD BR-U6-02/03/04) — hereda patrón U4/U5.
- **Hook con errores tragados** (FD BR-U6-15): excepción ⇒ log, nunca rompe el `202` del ingest.
- **Reloj inyectable + funciones puras** (FD BR-U6-08/25): tests sin sleep ni red.
- **Reinicio conservador** (FD BR-U6-13): baseline parcial ⇒ re-supresión; `established` persistida ⇒ sin supresión (NFR-AVAIL-02).
- **Sin `/metrics` propio** (U6 produce valores; U7 expone) y **+3 familias** en catálogo U1 (FD BR-U6-22).
- **Non-root/SECURITY blocking** (NFR-SEC-01/02) heredados; U6 no añade superficie de red ni privilegios.
- **Sin UI** (Usability no aplica — única unidad con UI es U3).
- **CI actual**: global `--cov-fail-under=70` + gates `core/`, `gui/`, `discovery/`, `traffic/` ≥70.
- **Gate de lint/format/mypy** heredado (TS-04/05) sobre `baseline/`.

**Categorías evaluadas**:

| Categoría | Aplica a U6 | Tratamiento |
|---|---|---|
| Scalability | Parcial | Q6 (crecimiento de filas `alerts` por activación) |
| Performance | Sí | Q1 (costo síncrono del hook en el path de ingesta vs NFR-PERF-03 p95 <500 ms) |
| Availability | Sí | Q4 (fallo de persistencia en el hook), Q5 (fallo de hidratación al arrancar) |
| Security | Parcial | Q10 (superficie nueva: confirmación sin endpoints/deps/deserialización nueva); config estricta y sin secretos ya en FD |
| Tech Stack | Parcial | fijado: sin deps nuevas, Python 3.11, PBT designado (Q2 = alcance) |
| Reliability | Parcial | determinismo ya en FD BR-U6-08/12; Q4/Q5 cubren degradación |
| Maintainability | Sí | Q3 (gate `baseline/` ≥70), Q8 (eventos de log canónicos), Q9 (estrategia de tests de supresión) |
| Usability | **No aplica** | U6 sin UI |

---

## 2. Checklist del plan

- [x] Analizar Functional Design y NFR globales
- [x] Generar preguntas NFR (Q1–Q10)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-19: "Acepto todo" ⇒ Q1–Q10 = A)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; interacciones revisadas (Q1×FD BR-U6-15 hook tragado; Q4×Q5 degradación; Q2×NFR-TECH-03 designado; Q7×FD §3.1 config) ⇒ **sin FQ necesarias**
- [x] Generar `nfr-requirements/nfr-requirements.md`
- [x] Generar `nfr-requirements/tech-stack-decisions.md`
- [x] Presentar mensaje de completitud y esperar aprobación (2026-11-19T08:10:00Z)

---

## 3. Preguntas de NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Costo del hook push en el path de ingesta (Performance / NFR-PERF-03)

Contexto: FD Q2=A ejecuta `ConditionService.on_accepted` **post-commit dentro del request** de `POST /ingest` (NFR-PERF-03: Core API p95 <500 ms, no vinculante). El trabajo por observación traffic aceptada es O(1): hasta 3 `update_baseline` + 1 `evaluate` + ≤2 upserts (baseline/alerta) — milisegundos.

- **A (recomendado)**: **síncrono post-commit** (como está en el FD): simple, determinista, fresco a cadencia de ventana; añadir un test **informativo** de latencia de ingesta con hook (imprime p95, **sin gate** en CI) — misma bar informativa que U2/U5.
- **B**: síncrono sin medición alguna (fiarse del cálculo O(1)).
- **C**: diferir la evaluación (cola/worker en proceso) — añade concurrencia y rompe la determinismo simple de los tests.

[Answer]: A
### Question 2 — Alcance del PBT designado (Tech Stack / NFR-TECH-03)

Contexto: **NFR-TECH-03 obliga PBT para `baseline calculations`** (es el PBT designado de U6, junto a Nmap XML de U4 ✓ y flow normalization de U2 ✓). FD BR-U6-08 ya pide determinismo.

- **A (recomendado)**: `tests/property/test_baseline_statistics.py` con 4 propiedades: (1) media/varianza de `n` muestras == brute force con `n-1`; (2) congelada: tras 5 muestras, muestras extra no cambian μ/s²; (3) `select_threshold` monótono en `k` (`k` mayor ⇒ umbral ≥) y `measured > threshold` consistente con el fixture bajo/igual/encima; (4) la máquina de estados nunca sale del `ConditionState` de U1 y `suppressed ⇒ nunca firing`.
- **B**: mínimo — solo (1) media/varianza vs brute force.
- **C**: (1)+(2) únicamente.

[Answer]: A
### Question 3 — Gate de cobertura de `baseline/` (Maintainability)

Contexto: gates existentes ≥70% por paquete (`core/` TS-U2-10, `gui/` U3, `discovery/` TS-U4-08, `traffic/` TS-U5-09). U6 añade `src/sentinel/baseline/`.

- **A (recomendado)**: paso `Baseline coverage gate (U6, P11)` en CI: `coverage report --include='*/baseline/*' --fail-under=70` — misma bar que las unidades anteriores.
- **B**: solo el gate global 70% (diluye el gate del paquete).
- **C**: ≥90% para U6 (bar más alta que el resto de unidades).

[Answer]: A
### Question 4 — Fallo de persistencia durante la evaluación (Availability / Reliability)

Contexto: el hook (FD BR-U6-15) ya traga excepciones para no romper el `202`; pero conviene fijar qué pasa con el **estado** si `BaselineRepository.upsert`/`AlertRepository.upsert` fallan (disco lleno, BD cerrada) a mitad de la evaluación.

- **A (recomendado)**: **degradar con log**: `log event="condition_persistence_failed"` + la condición sigue viva **en memoria** (métricas/estados disponibles); la próxima ventana reintenta el upsert (el baseline/alerta se reescriben enteros ⇒ eventualmente consistentes); nunca propaga al ingest.
- **B**: abortar la evaluación completa de la ventana (estado en memoria tampoco se actualiza).
- **C**: propagar el error (rompe el 202 — contradice BR-U6-15).

[Answer]: A
### Question 5 — Fallo de hidratación al arrancar (Availability / NFR-AVAIL-02)

Contexto: `create_app` llama `BaselineRepository.list()` para hidratar (FD §3.6); si esa lectura falla (BD corrupta/transitoria), el servicio puede arrancar vacío o no arrancar.

- **A (recomendado)**: **arrancar vacío con log** `event="baseline_hydration_failed"` + causa — todas las series re-establecen con supresión conservadora (coherente BR-U6-13); el Core sigue sirviendo (la salud nunca rompe el proceso, patrón `HealthService`).
- **B**: fail-fast en `create_app` (el Core no arranca sin poder leer `baselines`).

[Answer]: A
### Question 6 — Crecimiento de filas `alerts` (Scalability)

Contexto: cada activación R-01 crea una fila nueva (`alert_id` por activación, FD BR-U6-17); una serie que oscila alrededor del umbral genera muchas filas con el tiempo. U2 no tiene retención (events/alerts tampoco); la query pagina (`page_limit`).

- **A (recomendado)**: **sin retención en MVP** — coherente con `events`/`alerts` de U2 y con NFR-OPS-05 (reportes reproducibles desde datos persistidos); cardinalidad de series acotada (interfaces × protocolos × 1 regla) y la query ya pagina; retención/VACUUM queda documentado como futuro.
- **B**: límite por serie (p. ej. conservar las últimas N activaciones) — requiere poda en U6 y complica la determinismo de fixtures.
- **C**: consolidar re-fires en la misma fila (rompe «una fila por activación» de U2 FD).

[Answer]: A
### Question 7 — Handoff Helm de los parámetros (Ops / NFR-OPS-01)

Contexto: NFR-OPS-01 exige que **todo parámetro ajustable** viva en `values.yaml`; FR-BASE-03 pide `k` Helm-configurable; FD Q5=A define 4 env (`K`, `ABSOLUTE_BPS`, `INTERVAL_SECONDS`, `COLLECTOR_TIMEOUT_SECONDS`). U9 hará el mapping values→env.

- **A (recomendado)**: los **4 parámetros** quedan documentados como handoff a U9 (`baseline.k`, `baseline.absoluteBps`, `baseline.intervalSeconds`, `baseline.collectorTimeoutSeconds`); U6 solo publica las env (patrón U4/U5: «U5 solo publica env listas para el mapeo de U9»).
- **B**: solo `k` y `absolute_bps` (los que cita FR-BASE-03 literalmente).

[Answer]: A
### Question 8 — Eventos de log del componente (Maintainability / observabilidad)

Contexto: BR-12 U1 exige logs JSON con `component`/`event` canónicos; U5 usó `arp_rate`/`sensor_export_failed`. U6 necesita eventos para operación y depuración de GT-04.

- **A (recomendado)**: eventos propios `component=baseline.*`: `baseline_established` (serie, n, μ, s²), `condition_firing` (serie, measured, threshold), `condition_resolved`, `condition_evaluation_failed` (causa), `baseline_hydration_failed` (Q5) — snake_case, sin valores de alta cardinalidad (sin IPs).
- **B**: reutilizar solo eventos de U2 (`observation_traffic` ya existe) sin eventos propios de condición.

[Answer]: A
### Question 9 — Estrategia de tests de supresión/integración (Maintainability)

Contexto: los AC ST-M5-03 exigen `tests/integration/test_baseline_suppression.py -k init_window|after_window`; FD fija reloj inyectable y repos inyectados.

- **A (recomendado)**: integración con **`TestClient` + BD temporal + reloj falso + hook real**: se ingesta una serie de `TrafficObservation` por `POST /ingest` y se verifican la fila `alerts`/`baselines` y los estados (más cerca del GT-04 real); los casos unitarios de umbral siguen siendo `test_threshold.py` puro.
- **B**: `test_baseline_suppression.py` llama directo a `ConditionService` sin `TestClient` (más rápido, menos cobertura del wiring del hook).

[Answer]: A
### Question 10 — Superficie de seguridad nueva (Security / NFR-SEC-01)

Contexto: NFR-SEC-01 = reglas SECURITY blocking como constraints. U6 añade: un hook in-process, 4 env floats, repos inyectados, 3 familias de métricas. Sin endpoints, sin deps, sin deserialización propia (el `Batch` ya lo valida U2/Pydantic), sin secretos nuevos.

- **A (recomendado)**: **confirmar que la superficie nueva es la descrita** (sin endpoints/deps/secretos/sockets; config float validada; sin labels de alta cardinalidad; SECURITY blocking hereda sin cambios) — se registra como NFR-U6-SEC-01 de «sin superficie nueva» y no se pide revisión adicional de threat model.
- **B**: pedir revisión explícita de threat model para U6 en esta etapa.

[Answer]: A
---

## 4. Fuera de alcance de este plan

- Exposición `/metrics`, `PrometheusRule` con `for` (U7/U8); alertas R-02/R-04 persistidas (Q10 FD, documented-only).
- Retención de datos, HA, multi-sensor (NFR-AVAIL-01 single-sensor cerrado globalmente).
- Usability (U6 sin UI); NFR-PERF-01/02 de otros dominios (discovery/sensor) ya tratados en U4/U5.
