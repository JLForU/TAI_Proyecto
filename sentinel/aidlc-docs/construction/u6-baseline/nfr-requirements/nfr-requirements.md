# NFR Requirements — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 2: Generation)
**Fecha**: 2026-11-19
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U6 — `src/sentinel/baseline/`
**Decisiones (plan Q1–Q10)**: **A en todas** (2026-11-19).
**Entradas**: Functional Design de U6 (aprobado 2026-11-19T07:35:00Z), `requirements.md` §3/§4/§5, U1–U5 `tech-stack-decisions.md`, `implementation-scope.md` (M5).

---

## 1. Alcance

NFR **específicos de U6** (servicio de condiciones deterministas: estadística, umbrales, supresión, persistencia de `baselines`/`alerts`, indicadores hacia U7). Hereda sin cambio TS-01..11 de U1, TS-U2-01..11, TS-U3, TS-U4-01..12, TS-U5-01..13 y el stack global (Python 3.11, httpx ya presente, foundation).

**Fijados por requisito/aprobados (no se preguntaron)**:
- **NFR-TECH-03**: PBT **obligatorio** para `baseline calculations` (el PBT designado de U6; alcance en Q2=A) — `hypothesis` dev ya presente.
- NFR-SEC-01 (SECURITY blocking), NFR-SEC-02 (non-root heredado; U6 no toca imagen), NFR-SEC-03 (scan en CI global).
- NFR-AVAIL-01 (single sensor), NFR-AVAIL-02 (restart recupera de SQLite — FD §3.6/BR-U6-13).
- NFR-PERF-02 (sensor ≥10k flows/s, no vinculante, ya en U5).
- FD Q1–Q13 (push, frontera sin core/sqlite, config estricta, reloj inyectable, congelada, supresión prioritaria, repos inyectados, +3 familias U1).
- `implementation-scope.md` (ST-M5-01..04 documented-only, mínimo R-01/GT-04); **sin dependencias pip nuevas**; sin `/metrics` propio (U7 expone).

**Categorías**: Usability **no aplica** (U6 sin UI — única unidad con UI es U3).

---

## 2. Requisitos no funcionales de U6

### 2.1 Rendimiento y capacidad (Performance / Scalability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U6-PERF-01 | **Hook síncrono O(1) post-commit** en el path de `POST /ingest` (≤3 `update_baseline` + 1 `evaluate` + ≤2 upserts por observación traffic aceptada); test **informativo** de latencia de ingesta con hook (imprime p95, **sin gate** en CI) — la envolvente NFR-PERF-03 (p95 <500 ms) se valida en lab/Build & Test | Plan Q1=A, NFR-PERF-03, FD §3.2 | test informativo que imprime p95 de ingesta con hook (sin assert de duración) |
| NFR-U6-SCAL-01 | **Cardinalidad acotada**: series = interfaces × {tcp,udp,icmp,other} × 3 métricas con labels `interface`/`protocol`/`state`/`collector` (prohibidos `src_ip`/`dst_ip`/`asset_id`, BR-21 U1); **sin retención** de filas `alerts` en MVP (coherente `events`/`alerts` de U2, query pagina, NFR-OPS-05 reproducible) — retención/VACUUM documentado como futuro | Plan Q6=A, FD BR-U6-24 | `test_indicators.py -k label_cardinality`; revisión de query paginada sin cambios |

### 2.2 Disponibilidad y fiabilidad (Availability / Reliability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U6-AVAIL-01 | **Fallo de persistencia en el hook ⇒ degradar con log**: `log event="condition_persistence_failed"` + causa; la condición sigue viva en memoria (métricas/estados disponibles); el próximo upsert reescribe baseline/alerta enteros (eventualmente consistentes); **nunca** propaga al ingest (202 intacto, FD BR-U6-15) | Plan Q4=A, NFR-AVAIL-01 | `tests/unit/baseline/test_conditions.py -k persistence_failure_degrades` (repo que lanza ⇒ log + estado en memoria + sin excepción) |
| NFR-U6-AVAIL-02 | **Fallo de hidratación al arrancar ⇒ Core sigue vivo**: `BaselineRepository.list()` excepción ⇒ `log event="baseline_hydration_failed"` + causa, servicio arranca vacío, todas las series re-establecen con **re-supresión conservadora** (BR-U6-13); patrón `HealthService` (la salud nunca rompe el proceso) | Plan Q5=A, NFR-AVAIL-02, FD §3.6 | `tests/unit/baseline/test_restart.py -k hydration_failure_starts_empty` |
| NFR-U6-REL-01 | **Determinismo con reloj inyectable**: `ConditionService` acepta `Clock` (pared UTC en prod, falso en tests); funciones puras `select_threshold`/`statistics`/`collector_up` sin I/O — mismos inputs ⇒ mismos estados/alertas (FD BR-U6-08), tests **sin `sleep`** ni red | FD Q12=A, BR-U6-08/25 | `test_baseline.py -k deterministic` + revisión (cero `time.sleep` en `baseline/`) |

### 2.3 Seguridad (Security — extensión SECURITY blocking)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U6-SEC-01 | **Sin superficie nueva**: hook in-process + 4 env floats validados + repos/clock inyectados; **sin** endpoints propios, sin deps nuevas, sin secretos nuevos, sin sockets/red, sin deserialización propia (el `Batch` lo valida U2/Pydantic), sin labels de alta cardinalidad — SECURITY blocking hereda sin cambios | Plan Q10=A, NFR-SEC-01, FD §1 | revisión de imports (`httpx`/`socket` ausentes en `baseline/`); sin routers/endpoints en `baseline/` |
| NFR-U6-SEC-02 | **Config estricta**: claves `SENTINEL_BASELINE_*` desconocidas o valores inválidos (`k ≤ 0`, `absolute_bps ≤ 0`, `interval < 1`, `timeout < 1`) ⇒ `ConfigError` al arranque (typo no pasa silencioso); `ABSOLUTE_BPS` sin default numérico (PRD §3.3 sin umbrales arbitrarios) | Plan FD Q5=A, FD BR-U6-02/03/04 | `tests/unit/baseline/test_config.py -k strict_env / -k invalid_config / -k defaults` |

### 2.4 Mantenibilidad (Maintainability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U6-MNT-01 | Gate de cobertura **≥ 70% en `src/sentinel/baseline/`** en el job `test` (misma bar que `core/`, `gui/`, `discovery/`, `traffic/`) | Plan Q3=A | paso `Baseline coverage gate (U6, P11)` en CI: `coverage report --include='*/baseline/*' --fail-under=70` |
| NFR-U6-MNT-02 | **PBT designado (NFR-TECH-03)** en `tests/property/test_baseline_statistics.py`: (1) media/varianza de n muestras == brute force con `n-1`; (2) congelada: tras 5 muestras, extras no cambian μ/s²; (3) `select_threshold` monótono en `k` y `measured > threshold` consistente con fixtures bajo/igual/encima; (4) la máquina de estados nunca sale del `ConditionState` de U1 y `suppressed ⇒ nunca firing` | Plan Q2=A, NFR-TECH-03 | `pytest tests/property/test_baseline_statistics.py` en job `test` |
| NFR-U6-MNT-03 | **Eventos de log canónicos** `component=baseline.*` snake_case: `baseline_established` (serie, n, mu, sigma), `condition_firing` (serie, measured, threshold), `condition_resolved`, `condition_evaluation_failed` (causa), `baseline_hydration_failed` (causa) — sin valores de alta cardinalidad (sin IPs) | Plan Q8=A, BR-12 U1 | test de log JSON con `event`/`component` canónicos |
| NFR-U6-MNT-04 | **Tests de supresión integrados** (`tests/integration/test_baseline_suppression.py -k init_window\|after_window`): `TestClient` + BD temporal + **reloj falso + hook real** — se ingesta serie de `TrafficObservation` por `POST /ingest` y se verifican filas `alerts`/`baselines` y estados (wiring completo, camino del GT-04) | Plan Q9=A, FD re-mapeo AC | `pytest tests/integration/test_baseline_suppression.py` |
| NFR-U6-MNT-05 | `ruff check` + `ruff format --check` + `mypy` en verde sobre `baseline/` (hereda TS-04/05) | TS-04/05 | job `lint`/`typecheck` de CI |

### 2.5 Stack técnico (Tech Stack)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U6-STACK-01 | **Cero dependencias pip nuevas**: stdlib + pydantic vía `foundation` + `hypothesis` (solo dev, ya presente); Python 3.11+ (NFR-TECH-02) | Plan (fijado), NFR-TECH-01/02 | `requirements.txt` sin cambios en U6 |

### 2.6 Operaciones (Ops)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U6-OPS-01 | **Handoff Helm a U9**: los 4 parámetros quedan documentados para `values.yaml` → env (`baseline.k`, `baseline.absoluteBps`, `baseline.intervalSeconds`, `baseline.collectorTimeoutSeconds`); U6 solo publica las env `SENTINEL_BASELINE_*` (patrón U4/U5) | Plan Q7=A, NFR-OPS-01, FR-BASE-03 | sección de env en `README.md` (Code Gen) + entrada en el handoff `deployment-architecture.md` §5 |

---

## 3. Trazabilidad NFR → historias / reglas globales

| NFR-U6 | Historias / reglas |
|---|---|
| NFR-U6-PERF-01 | ST-M5-04 (publicación), NFR-PERF-03 |
| NFR-U6-SCAL-01 | ST-M5-04 (labels), BR-21 U1, NFR-OPS-05 |
| NFR-U6-AVAIL-01/02 | NFR-AVAIL-01/02, GT-05 (Core vivo), ST-M5-03 |
| NFR-U6-REL-01 | ST-M5-01 (reproducible), GT-01 |
| NFR-U6-SEC-01/02 | NFR-SEC-01, ST-M5-02 (config sin código) |
| NFR-U6-MNT-01 | gates por paquete existentes (P11) |
| NFR-U6-MNT-02 | **NFR-TECH-03** (baseline calculations) |
| NFR-U6-MNT-03 | FR-BASE-05 (operación de GT-04) |
| NFR-U6-MNT-04 | ST-M5-03 AC (`init_window`/`after_window`) |
| NFR-U6-OPS-01 | NFR-OPS-01, FR-BASE-03 |
