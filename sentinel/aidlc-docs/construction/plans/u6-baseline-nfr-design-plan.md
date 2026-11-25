# NFR Design Plan — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — NFR Design (Parte 1: Planning)
**Fecha**: 2026-11-19
**Estado**: GENERATED — respuestas todas A (2026-11-19); artefactos generados; pendiente de aprobación
**Unidad**: U6 — `src/sentinel/baseline/`
**Entradas**: `construction/u6-baseline/nfr-requirements/{nfr-requirements,tech-stack-decisions}.md` (aprobado 2026-11-19T08:20:00Z), FD U6 (aprobado 2026-11-19T07:35:00Z), precedentes NFR Design U4/U5 (`logical-components.md`, `nfr-design-patterns.md`).

---

## 1. Contexto del assessment (Step 1 — analizado)

U6 incorpora NFR-U6-* (PERF-01, SCAL-01, AVAIL-01/02, REL-01, SEC-01/02, MNT-01..05, STACK-01, OPS-01) en un servicio **en memoria + persistencia en repos U2**, evaluación por hook post-commit, sin red y sin UI. Las decisiones Q1–Q10 de NFR Requirements (todas A) y las TS-U6-01..13 fijan ya: frontera sin `core/`, push síncrono O(1), degradación con log, reloj inyectable, PBT designado, gate ≥70%, +3 familias U1, handoff Helm U9.

**Ya decidido (NO se pregunta)**:
- Push post-commit síncrono + test informativo de latencia sin gate (Q1 NFR-Req).
- Degradación con log en fallo de persistencia/hidratación; sin excepción propagada (Q4/Q5 NFR-Req; FD BR-U6-15).
- Buffer de establecimiento a 5 muestras; congelada; `t_first` efímero, re-supresión (FD Q3/Q8).
- `BaselineSettings` estricto con loader propio; sin cambios a `CoreSettings`/esquema/repos (FD Q5/Q7).
- PBT de 4 propiedades; gate `baseline/` ≥70%; eventos `component=baseline.*` (Q2/Q3/Q8 NFR-Req).
- Cero deps pip; sin endpoints; sin `/metrics` propio; Dockerfile intocado.
- **`Clock` existe como `Protocol` + `SystemClock` en `traffic/worker.py` (U5)** — U6 necesita decidir si lo reutiliza o define el suyo (Q6).

**Categorías evaluadas** (todas con pregunta justificada):

| Categoría | Aplica | Pregunta |
|---|---|---|
| Resilience Patterns | Sí | Q1 (retry/circuit-breaker en la persistencia del hook) |
| Scalability Patterns | Sí | Q2 (dónde viven las ≤5 muestras en establecimiento), Q7 (costo de `metric_samples()` por scrapeo) |
| Performance Patterns | Sí | Q3 (alcance de evaluación por observación) |
| Security Patterns | Sí | Q4 (confianza vs re-validación de la obs en la frontera del hook) |
| Logical Components | Sí | Q5 (descomposición en módulos), Q6 (propiedad del protocolo de reloj) |

---

## 2. Checklist del plan

- [x] Analizar NFR Requirements y precedentes
- [x] Generar preguntas (Q1–Q7)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-19: "Acepto todo" ⇒ Q1–Q7 = A)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; interacciones revisadas (Q1×NFR-Req AVAIL-01 sin retry; Q2×FD congelada/BR-U6-13; Q6×FD reloj inyectable) ⇒ **sin FQ necesarias**
- [x] Generar `nfr-design/nfr-design-patterns.md`
- [x] Generar `nfr-design/logical-components.md`
- [x] Presentar mensaje de completitud y esperar aprobación (2026-11-19T08:55:00Z)

---

## 3. Preguntas de NFR Design

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Patrón de resiliencia en la persistencia del hook (Resilience Patterns)

Contexto: NFR-U6-AVAIL-01 ya fija degradar con log y **reintento natural** (el próximo upsert reescribe baseline/alerta enteros); BR-U6-15 nunca propaga. Queda decidir si añadir mecanismo de reintento/aislamiento **dentro** del request.

- **A (recomendado)**: **try/log simple, sin retry ni circuit breaker** en el hook: un fallo de upsert se loguea `condition_persistence_failed` y la próxima ventana reintenta (upsert idempotente por clave) — cero estado adicional, determinista, sin alargar el `POST /ingest`.
- **B**: retry corto en el hook (p. ej. ×2 con backoff de milisegundos) antes de degradar.
- **C**: circuit breaker: tras N fallos seguidos, pausar la evaluación hasta que un upsert tenga éxito.

[Answer]: A
### Question 2 — Residencia de las muestras en establecimiento (Scalability Patterns)

Contexto: durante el establecimiento se acumulan ≤5 muestras de bytes/segundo por serie (`BASELINE_SAMPLES=5`); tras congelar, no se necesitan más. No existe tabla `samples` en el esquema (OQ-02).

- **A (recomendado)**: **buffer en memoria** en el `BaselineSeries` (`list[float]` acotado, descartado al congelar) — cardinalidad acotada por series activas en ventana; si el proceso muere, la serie re-establece (coherente con `t_first` efímero y re-supresión FD BR-U6-13); **cero cambios de esquema**.
- **B**: persistir las muestras en la BD (requiere columna/tabla nueva en U2 — rompe «OQ-02, sin cambios de esquema»).

[Answer]: A
### Question 3 — Alcance de la evaluación por observación (Performance Patterns)

Contexto: NFR-U6-PERF-01 fija el hook O(1) (≤3 `update_baseline` + 1 `evaluate` + ≤2 upserts). El hook recibe una `TrafficObservation` aceptada (3 métricas de `interface × protocol`).

- **A (recomendado)**: **evaluar solo las métricas de la serie observada** (las ≤3 claves `metric|interface|protocol` de esa observación): O(1) por métrica, sin recorrer el mapa global, sin efectos sobre otras series (cero firing espurio por re-evaluación ajena).
- **B**: reevaluar **todas** las series registradas en cada ingesta (más coste con cardinalidad y posible re-fire de series no relacionadas con la observación).

[Answer]: A
### Question 4 — Confianza en la frontera de la observación (Security Patterns)

Contexto: la obs llega del hook ya validada por U2 (Pydantic `TrafficObservation` de U1, insertada en BD). NFR-U6-SEC-01 = sin superficie nueva; patrón U4: confiar en la frontera del proveedor.

- **A (recomendado)**: **confiar en la frontera U2**: el hook lee atributos de la obs ya validada (duck-typing defensivo mínimo en la entrada del hook: `getattr` de `interface`/`protocol`/`observed_at`; sin re-validación Pydantic propia) — cero duplicación de contratos, sin ataque nuevo (la obs nace en el Core, no del exterior).
- **B**: re-validar con un modelo propio en U6 antes de evaluar (duplica el contrato U1, añade superficie de mantenimiento).

[Answer]: A
### Question 5 — Descomposición en componentes lógicos (Logical Components)

Contexto: precedente U5 = módulos pequeños (`config`, `source`, `aggregator`, `worker`, `client`) con Protocol en la frontera; FD §3 describe estadísticas, condiciones, indicadores y config.

- **A (recomendado)**: **4 módulos + tests**: `config.py` (`BaselineSettings` + loader estricto), `statistics.py` (funciones puras: media, varianza `n-1`, `select_threshold`), `conditions.py` (`ConditionService` + `Protocol` locales `BaselineRepository`/`AlertRepository`/`Clock` + máquina de estados/supresión), `indicators.py` (`metric_samples()` para U7); PBT en `tests/property/test_baseline_statistics.py`.
- **B**: monolito `baseline.py` único (menos ficheros, peor revisión por cobertura/patrocinio de tests).
- **C**: añadir `rules.py` (reglas puras R-01…) separado de `conditions.py` ahora, anticipando R-02/R-04 (más capas hoy, YAGNI).

[Answer]: A
### Question 6 — Propiedad del protocolo de reloj (Logical Components)

Contexto: U5 define `Clock` (`Protocol`) + `SystemClock` en `traffic/worker.py`; U6 necesita `now()` para supresión/`fired_at`. FD fija «reloj inyectable» sin decidir la propiedad. Importar de `traffic/` acoplaría U6→U5 (unidades hermanas).

- **A (recomendado)**: **`Clock` Protocol local en `baseline/`** (duck-typing estructural: cualquier objeto con `now() -> datetime` sirve — en tests el `FakeClock`/reloj falso de U6, en prod un `SystemClock` propio de una línea) — cero acoplamiento entre unidades, precedente de Protocol locales de U4/U5.
- **B**: importar `Clock`/`SystemClock` de `sentinel.traffic.worker` (reutiliza el código pero crea dependencia U6→U5).

[Answer]: A
### Question 7 — Costo de `metric_samples()` por scrapeo (Performance / Scalability Patterns)

Contexto: U7 expondrá los indicadores vía `/metrics` en su intervalo (p. ej. 15–30 s); `metric_samples()` materializa (nombre, labels, valor) de todas las series congeladas/estableciéndose.

- **A (recomendado)**: **cálculo bajo demanda** por llamada: recorre el mapa en memoria (O(series), series acotadas = interfaces × 3 protocolos × 3 métricas + `collector_up`) sin caché — simple, siempre fresco, coste despreciable frente al scrapeo HTTP.
- **B**: cachear muestras invalidada por escritura (estado adicional, riesgo de staleness, sin beneficio medible a esta cardinalidad).

[Answer]: A
---

## 4. Fuera de alcance de este plan

- Estructura de CI/Helm (Infrastructure Design U6); implementación y gates (Code Gen U6).
- Reglas R-02/R-04 persistidas y `/metrics`/`PrometheusRule` (U7/U8).
- Cambios de esquema, dependencias pip, Dockerfile (fijados en NFR Requirements).
