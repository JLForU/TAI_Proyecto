# NFR Requirements Plan — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 1: Planning)
**Fecha**: 2026-11-24
**Estado**: Q1–Q7 = Acepto todo (2026-11-24); artefactos NFR generados; pendiente de aprobación
**Unidad**: U7 — `src/sentinel/core/metrics/` + `foundation/metrics_contract.py` (v2) + `deploy/monitoring/servicemonitor.yaml`
**Entradas**: `construction/u7-metrics-exposure/functional-design/*` (aprobado 2026-11-24T05:54:38Z), `requirements.md` §3 NFR + §4 constraints + §5, U1 `tech-stack-decisions.md` (TS-01..11), U2 (TS-U2-01..11, «cuerpos reales de `collect()` en 9108 → U7»), U3–U6 (TS-U3, TS-U4-01..12, TS-U5-01..13, TS-U6-01..13), `implementation-scope.md` (M6), `unit-of-work.md` §U7.

---

## 1. Contexto del assessment (Step 1 — analizado)

U7 es el **exporter real de métricas**: pipeline de scrape en proceso (contadores + gauges SQLite + `ConditionService.metric_samples()`), contrato U1 v2 (14 familias, allowlist 7 con `assert_allowed`), hook O(1) post-commit y manifiesto ServiceMonitor. Corre en el **hilo daemon de `MetricsServer` (9108)** — separado del path de la API — más un hook de incremento en el request de ingesta. Sin UI, sin endpoints nuevos, sin secretos.

**Ya decidido (NO se pregunta)**:
- **FD Q1–Q11 aprobados** (híbrido contadores/gauges, 500 en error de scrape sin caché, `assert_allowed` por sample, HELP dict, SM en `deploy/monitoring/`, sin clase nueva, sin `server.py`).
- **Sin dependencias pip nuevas** (NFR-TECH-01/02): PyYAML **ausente** ⇒ validación del manifiesto por aserciones estructurales sin parser (FD BR-U7-21); Python 3.11.
- **NFR-TECH-03 NO designa PBT para metrics export** (designado: Nmap XML ✓, flow normalization ✓, baseline calculations ✓) — el PBT aquí es opcional (Q4).
- **NFR-SEC-01/02/03** (SECURITY blocking, non-root, scan): U7 no toca imagen ni añade deps ni secretos; manifiesto SM sin credenciales.
- **NFR-AVAIL-01/02**: single-sensor; restart ⇒ contadores de proceso en cero (aceptado FD BR-U7-13, Prometheus absorbe resets) y gauges se reconstruyen desde SQLite.
- **NFR-PERF-03** (API p95 <500 ms): el scrape **no** está en el path de la API; el hook añade 2 incrementos O(1) por lote aceptado (test informativo de ingesta de U6 sigue cubriendo el hook completo).
- **Índices ya existentes**: `idx_obs_source ON observations(source, observed_at)` (query de última ventana) y `idx_events_type ON events(type, occurred_at)` (COUNT de cambios) ⇒ sin cambio de esquema.
- **CI actual**: global `--cov-fail-under=70` + gates `gui/`, `discovery/`, `traffic/`, `baseline/` ≥70 — **no hay gate por paquete para `core/` ni `foundation/`** (U1/U2 nunca lo añadieron).
- **Usability no aplica** (sin UI; dashboards Grafana son U8).

**Categorías evaluadas**:

| Categoría | Aplica a U7 | Tratamiento |
|---|---|---|
| Scalability | Sí | Q1 (coste de las 4–5 lecturas SQLite por scrape conforme crecen `observations`/`events`) |
| Performance | Sí | Q1 (query acotada por índice) + Q2 (test informativo de latencia de scrape) |
| Availability | Parcial | fijado por FD Q9 (500 ⇒ target down); Q7 (auto-instrumentación de errores de scrape) |
| Security | Sí | Q3 (auth del puerto 9108) — manifiesto sin secretos y sin deps ya están en FD |
| Tech Stack | Fijado | sin deps nuevas; Q4 = PBT opcional (no designado por NFR-TECH-03) |
| Reliability | Parcial | hook aislado y 500 ya en FD; Q7 cubre señal de fallo del exporter |
| Maintainability | Sí | Q5 (gate de cobertura), Q6 (documentación README) |
| Usability | **No aplica** | U7 sin UI |

---

## 2. Checklist del plan

- [x] Analizar Functional Design y NFR globales (Step 1)
- [x] Generar preguntas NFR Q1–Q7 (Steps 2–3)
- [x] Guardar plan en `aidlc-docs/construction/plans/u7-metrics-exposure-nfr-requirements-plan.md` (Step 4)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-24: "Acepto todo" por precedente ⇒ Q1–Q7 = A)
- [x] Analizar respuestas y resolver ambigüedades — interacciones revisadas (Q1×FD «sin esquema nuevo» ⇒ índice futuro documentado; Q3×SEC-01 bloqueante sin conflicto; Q4×NFR-TECH-03 no designado ⇒ PBT opcional; Q5×gates existentes sin solapamiento; Q7×FD Q9=500 sin familia nueva) ⇒ **sin FQ necesarias**
- [x] Generar `nfr-requirements/nfr-requirements.md` (Step 6)
- [x] Generar `nfr-requirements/tech-stack-decisions.md` (Step 6)
- [ ] Presentar mensaje de completitud y esperar aprobación (Steps 7–8)
- [ ] Registrar aprobación en `audit.md` y marcar etapa en `aidlc-state.md` (Step 9)

---

## 3. Preguntas de NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas **todas las recomendaciones**, responde `Acepto todo` (se aplicará la opción recomendada de cada pregunta).

### Question 1 — Coste de las lecturas SQLite por scrape (Scalability / Performance)

Contexto: cada scrape hace ≤5 lecturas: `COUNT alerts`, `COUNT assets`, `COUNT events WHERE type IN (4)`, última obs `traffic` por serie (`WHERE source='traffic' ORDER BY observed_at DESC`), más `HealthService.health()`. Los índices `idx_events_type` y `idx_obs_source` ya cubren esas rutas; en el laboratorio las tablas son de cientos/miles de filas. La cadencia la decide Prometheus (default del stack ≈30 s).

- **A (recomendado)**: **queries como están, acotadas por índice**, con `LIMIT` razonable en la query de últimas observaciones (p. ej. basta recorrer las N más recientes para tomar una por serie) y un **test informativo** de latencia de scrape (Q2); documentar «si `observations`/`events` crecen mucho ⇒ revisar retención/VACUUM (futuro global, U6 ya lo anotó) o índice adicional» sin tocar esquema en U7.
- **B**: añadir **ya** un índice nuevo en `observations` (p. ej. parcial) — cambio de esquema que rompe la frontera «sin esquema nuevo» del FD y solo ayuda si las tablas crecen fuera del laboratorio.
- **C**: caché en proceso de los gauges (refresh por TTL) — complica invalidación y frescura; contradice «gauges al scrape» de FD Q1=A.

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 2 — Test de latencia de scrape (Performance / NFR-PERF-03)

Contexto: precedente U6 = test **informativo** que imprime p50/p95 sin assert de duración (envolvente se valida en lab/Build & Test). El scrape no compite con la API (hilo/puerto distintos), pero su coste sí importa operacionalmente.

- **A (recomendado)**: test **informativo** `GET /metrics` con DB sembrada (activos + obs + alertas + estados U6): imprime p50/p95 de N scrapes, **sin gate** en CI; Build & Test lo ejecuta con `-s` para el registro.
- **B**: sin medición (fiarse de que son COUNTs indexados).
- **C**: gate estricto de latencia de scrape en CI (p. ej. p95 < 50 ms) — falsos positivos en runners cargados.

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 3 — Autenticación del puerto de métricas 9108 (Security / NFR-SEC-01)

Contexto: el endpoint existe desde U2 (ST-M6-01) sin auth — modelo pull in-cluster; PRD pide que Prometheus scrape (SN-032) y que el dashboard muestre agregados (SN-033); U8 aplicará NetworkPolicy en el namespace. NFR-SEC-01 es SECURITY **blocking** (no se introducen credenciales débiles ni superficie nueva).

- **A (recomendado)**: **confirmar sin autenticación en MVP**: 9108 es pull interno, restringido por NetworkPolicy (U8) y visible solo in-cluster; el contenido son agregados sin IPs/hostnames (BR-21/allowlist). Documentar la decisión en el NFR (no es un olvido).
- **B**: bearer token simple (env `SENTINEL_METRICS_TOKEN`, header `Authorization`) exigido por el handler — añade config, handoff Helm y complejidad a Prometheus (scrape con `authorization`), fuera del alcance M6.
- **C**: bind a `127.0.0.1` — rompe el scrape de Prometheus desde otro pod (imposible en k8s).

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 4 — PBT opcional para el exporter (Tech Stack / NFR-TECH-03)

Contexto: NFR-TECH-03 **no** designa PBT para metrics export (los tres designados ya están cubiertos); `hypothesis` dev ya está presente; precedente U5 añadió PBT **adicional** (Q8=A) por lógica central. U7 tiene invariantes baratos de propiedad: cualquier `Sample` válido ⇒ render sin excepción, sin labels fuera de allowlist, TYPE correcto y families exactas.

- **A (recomendado)**: **PBT ligero adicional** `tests/property/test_metrics_render.py`: (1) generador de samples con labels del catálogo ⇒ `render_prometheus` termina y todo sample aparece una vez; (2) inyección de labels prohibidos/fuera de allowlist ⇒ `ValueError` en `assert_allowed`; (3) zero-fill ⇒ conjunto de familias == `METRIC_FAMILIES` exacto.
- **B**: sin PBT en U7 — solo tests unitarios parametrizados (FD ya los exige); el alcance designado está completo y U7 es mayormente wiring.

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 5 — Gate de cobertura de U7 (Maintainability)

Contexto: CI tiene gate global ≥70 y gates por paquete para `gui/`, `discovery/`, `traffic/`, `baseline/` — **no** para `core/` ni `foundation/` (U1/U2 no lo pidieron). U7 edita `core/metrics/` (dentro de `core/`) y `foundation/metrics_contract.py`; no crea paquete nuevo.

- **A (recomendado)**: **sin gate nuevo**: el global ≥70 cubre `core/metrics/` y `foundation/`; los tests dedicados de U7 (unit + integration + property) sostienen la cobertura; coherente con U1/U2 (que tampoco añadieron gate de `foundation`/`core`).
- **B**: añadir paso `Metrics coverage gate (U7)` con `coverage report --include='*/core/metrics/*' --fail-under=70` — simetría con los gates por paquete, pero abre precedente de gates por subpaquete.
- **C**: añadir gate `foundation/` ≥70 — toca el contrato compartido por todas las unidades (barra más amplia que U7; decisión de repo, no de la unidad).

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 6 — Documentación de U7 (Maintainability / NFR-OPS-03)

Contexto: NFR-OPS-03 pide documentación Markdown en repo; U2 documentó `/metrics` brevemente; U6 añadió sección README en su codegen. U7 añade 2 familias, cambia el contrato y crea `deploy/monitoring/` — operador necesita saber qué expone, cómo aplicar el SM y cómo verificar el scrape.

- **A (recomendado)**: sección **README «Metrics & monitoring»** al final del codegen de U7: tabla de 14 familias (tipo/labels/fuente), `curl localhost:9108/metrics`, `kubectl apply -f deploy/monitoring/servicemonitor.yaml` (requiere stack instalado) y nota de cardinalidad/allowlist.
- **B**: solo docstrings/comentarios en código (el README ya menciona el puerto 9108).
- **C**: README + runbook operativo aparte (`operations/`) — excede el alcance M6 (runbooks globales son U11/EN-03).

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)

### Question 7 — Señal de fallo del exporter (Reliability / Availability)

Contexto: FD Q9=A ⇒ error de scrape ⇒ 500 + log `metrics_error`; Prometheus marca el target `down` (señal que U8 alertará). No hay contador de errores de scrape en proceso.

- **A (recomendado)**: **sin familia nueva**: la señal ya es doble (HTTP 500 = target down + log `metrics_error`); un `scrape_errors_total` sería redundante y añadiría una 15.ª familia al contrato recién cerrado.
- **B**: añadir `sentinel_metrics_scrape_errors_total` (counter en proceso, labels `component=metrics`) incrementado antes de responder 500 — visibilidad en el propio endpoint, pero el endpoint está caído cuando el contador subiría (el scrape que falla no puede leerse a sí mismo de forma fiable en el mismo request; el valor se vería en el scrape siguiente si el proceso sigue vivo).

[Answer]: A (2026-11-24, "Acepto todo" por precedente de la sesión)
