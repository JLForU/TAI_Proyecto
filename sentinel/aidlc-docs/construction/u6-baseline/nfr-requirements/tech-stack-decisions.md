# Tech Stack Decisions — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — NFR Requirements
**Fecha**: 2026-11-19
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U6 — `src/sentinel/baseline/`
**Nota**: decisiones de la **unidad**; hereda TS-01..11 de U1, TS-U2-01..11 de U2, TS-U3 de U3, TS-U4-01..12 de U4, TS-U5-01..13 de U5 y el stack global de `requirements.md` §4. Plan NFR Q1–Q10 = A.

---

## 1. Tabla de decisiones

| # | Decisión | Elegida | Alternativas descartadas | Justificación | Origen |
|---|---|---|---|---|---|
| TS-U6-01 | Ubicación y frontera | **`src/sentinel/baseline/`** con frontera U4/U5: importa solo `foundation` + stdlib; repos/clock inyectados por `create_app` con `Protocol` locales (duck-typing) — core importa baseline, nunca al revés | `baseline/` importa `sentinel.core.db.*` (acoplamiento, rompe tests puros); módulo dentro de `core/` (mezcla unidades, viola estructura `unit-of-work.md`) | FD Q1=A, precedente discovery/traffic, testabilidad sin BD | FD §3.7, BR-U6-01 |
| TS-U6-02 | Momento de evaluación | **Push síncrono post-commit** en `POST /ingest` vía hook opcional `on_accepted` de `IngestionService` (solo observaciones recién insertadas) | pull al scrapear (alerts/baselines con delay, U6 necesita lectura de BD); cola/worker en proceso (concurrencia, rompe determinismo de tests) | FD Q2=A, precedente `DiscoveryTrigger`, frescura a cadencia de ventana, idempotente por construcción (BR-U6-14) | FD §3.2, Plan NFR Q1=A |
| TS-U6-03 | Motor estadístico | **Funciones puras propias** (`statistics.py`: media, varianza muestral `n-1`, `select_threshold`) sobre `list[float]`; sin librería numérica | `statistics` de stdlib (no expone varianza `n-1` directo con el mismo control); numpy/pandas (dep pesada sin necesidad; rompe cero-deps); Welford streaming (innecesario: congelada a 5 muestras) | NFR-U6-STACK-01, FD BR-U6-06/07, PBT designado sobre estas funciones | FD §3.3, Plan Q2=A |
| TS-U6-04 | Estado de la condición | **`BaselineState` en memoria + persistencia completa en repos U2** (hidratación al arranque; `t_first` efímero ⇒ re-supresión conservadora) | todo en memoria (pierde baseline/alertas al restart, NFR-AVAIL-02); todo en BD releyendo por evaluación (lecturas por ventana, acoplamiento) | FD Q8=A, OQ-02 «los llena U6», NFR-AVAIL-02 | FD §3.6, BR-U6-13/16 |
| TS-U6-05 | Identidad de alertas | **UUIDv5**: `condition_id = uuid5("R-01\|"+metric_key)`, `alert_id = uuid5(condition_id+"\|"+fired_at)` — fila por activación | UUID aleatorio (no determinista, rompe reenvíos/tests); un solo alert_id por serie (no distingue activaciones, contradice U2 FD) | U2 FD domain-entities (alert_id), FD BR-U6-17 | FD §3.4 |
| TS-U6-06 | Config de unidad | **`BaselineSettings`** (Pydantic `frozen`, `extra="forbid"`) + loader propio `SENTINEL_BASELINE_*`, fail-fast; `ABSOLUTE_BPS` sin default; `BASELINE_SAMPLES=5` constante de dominio | campos en `CoreSettings` (rompe BR-06 U1); YAML montado (U9 llega como env); solo `k` configurable (FR-BASE-03 pide absoluto + FR-BASE-01 intervalo) | FD Q5=A, patrón `foundation.config`, Plan NFR Q7=A | FD §3.1, BR-U6-02/03 |
| TS-U6-07 | Reloj | **Protocolo de reloj inyectable** (pared UTC en prod, falso en tests) — para `now` de supresión, `fired_at`/`resolved_at` | `datetime.now` directo (tests con monkeypatch frágil o sleep); `monotonic` (no alineable con `observed_at` UTC de U5) | FD Q12=A, BR-U6-08/25, patrón U5 | FD §1/§3.4 |
| TS-U6-08 | Indicadores hacia U7 | **`metric_samples() -> list[(nombre, labels, valor)]`** (tuplas formato `Sample` de U2/U7) + **+3 familias en catálogo U1** `METRIC_FAMILIES` | U6 importa `core.metrics.collect` (rompe frontera); U7 re-implementa los nombres (deriva de contrato); familias solo en U6 sin catálogo (U7 importaría «a ciegas») | FD Q9=A, precedente U4 (familias discovery), BR-U6-22 | FD §3.5, BR-U6-23 |
| TS-U6-09 | Gate de cobertura | **≥ 70% en `src/sentinel/baseline/`** (`--include='*/baseline/*' --fail-under=70`) en CI | solo el global 70% (diluye el gate); ≥90% (bar inconsistente con U1–U5) | Plan NFR Q3=A, misma bar por paquete (P11) | Plan Q3=A |
| TS-U6-10 | PBT (NFR-TECH-03) | **`tests/property/test_baseline_statistics.py`** con 4 propiedades: estadística vs brute force, congelada, umbral monótono en `k`, invariantes de máquina de estados (`suppressed ⇒ nunca firing`, estados ⊆ `ConditionState`) | sin PBT (NFR-TECH-03 lo **designa** para baseline); solo media/varianza (deja sin cubrir umbral/estado, mitad del alcance designado) | Plan NFR Q2=A, NFR-TECH-03 | Plan Q2=A |
| TS-U6-11 | Tests de supresión | **Integración `TestClient` + BD temporal + reloj falso + hook real** (`test_baseline_suppression.py`) | solo llamadas directas a `ConditionService` (no cubre wiring del hook ni persistencia real); red real (imposible en CI) | Plan NFR Q9=A, AC ST-M5-03 | Plan Q9=A |
| TS-U6-12 | Manejo de fallos | **Degradación con log sin excepción propagada**: persistencia fallida ⇒ `condition_persistence_failed` + reintento próximo upsert; hidratación fallida ⇒ arrancar vacío (`baseline_hydration_failed`) | propagar (rompe el 202/arranque); reintentos con backoff en el hook (alarga el request; el próximo upsert ya reintenta) | Plan NFR Q4/Q5=A, patrón `HealthService` (nunca rompe), BR-U6-15 | Plan Q4/Q5=A |
| TS-U6-13 | Logging | **`foundation.logging`** con `component=baseline.*` y eventos canónicos: `baseline_established`, `condition_firing`, `condition_resolved`, `condition_evaluation_failed`, `baseline_hydration_failed` | reutilizar eventos de U2 (la operación de GT-04 necesita distinguir transiciones de condición); logs en stdout simple (viola BR-12) | Plan NFR Q8=A, BR-12 U1 | Plan Q8=A |

---

## 2. Dependencias que U6 añade

**Pip: NINGUNA** (runtime y dev). U6 usa stdlib + pydantic vía `foundation.*` + `hypothesis` (dev, ya presente desde U1) + toolchain heredada.

| Paquete | Uso en U6 | Tipo |
|---|---|---|
| *(ninguno nuevo)* | — | — |

---

## 3. Impacto en artefactos heredados

| Artefacto | Cambio requerido por U6 |
|---|---|
| `src/sentinel/foundation/metrics_contract.py` | **+3 familias** en `METRIC_FAMILIES`: `sentinel_traffic_threshold_exceeded`, `sentinel_baseline_status`, `sentinel_collector_up` (FD BR-U6-22; precedente U4) |
| `src/sentinel/core/ingestion/service.py` | Parámetro opcional `on_accepted` (post-commit, solo observaciones aceptadas; excepción ⇒ log, no propaga) — precedente U4 (edición acotada de `service.py`) |
| `src/sentinel/core/api/app.py` | Construir `BaselineSettings` + `ConditionService` (`app.state.condition`), pasar `on_accepted` a `IngestionService` — precedente `DiscoveryTrigger` |
| `.github/workflows/ci.yml` | Paso `Baseline coverage gate (U6, P11)` tras los gates existentes |
| `README.md` | Sección **Baseline & conditions** (env `SENTINEL_BASELINE_*`, run/verify) al final de U6 Code Gen |
| `Dockerfile` | **Sin cambios** (NFR-SEC-02 heredado) |
| Esquema SQLite / repos U2 | **Sin cambios** (OQ-02 ya define `baselines`/`alerts`; U6 solo los escribe) |
| `CoreSettings` (U1) | **Sin cambios** (loader propio, BR-U6-02) |
