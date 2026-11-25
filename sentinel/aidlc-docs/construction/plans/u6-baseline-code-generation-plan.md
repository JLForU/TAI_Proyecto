# Code Generation Plan — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — Code Generation (Part 1: Planning)
**Fecha**: 2026-11-19
**Estado**: AWAITING_APPROVAL — pendiente de aprobación explícita del plan
**Workspace root**: `/home/jhoseph/Documents/TAI/TAI_Proyecto/sentinel` (de `aidlc-state.md`)
**Patrón**: Greenfield multi-unit (monolith) → `src/{unit-name}/` = **`src/sentinel/baseline/`**, tests = **`tests/unit/baseline/`** + **`tests/integration/`** + **`tests/property/`**
**Este plan es la única fuente de verdad de Code Generation para U6.**

---

## 1. Contexto de la unidad

- **Historias**: ST-M5-01..04 **todas `documented-only`** en el story map (M5 = «se implementa solo lo necesario para R-01», `implementation-scope.md` §3) — el código de U6 es **soporte de la unidad** para **R-01/GT-04**; FR-BASE-01..05 son la trazabilidad funcional.
  - ST-M5-01 First-5-samples initialization · ST-M5-02 Mean/variance per metric · ST-M5-03 Suppression window · ST-M5-04 Baseline indicators.
- **Diseño aprobado**: FD (flujos §3.1–3.7, BR-U6-01..27, FD Q1–Q13), NFR Requirements (NFR-U6-*, TS-U6-01..13, Q1–Q10), NFR Design (P1–P15, Q1–Q7, logical-components), Infrastructure Design (ID-U6-01..08, Q1–Q6).
- **Dependencias satisfechas**: **U1** (`foundation.*`: `Baseline`/`AlertCondition`/`ConditionState`, `ConfigError`, `get_logger`, `METRIC_FAMILIES` — **edición acotada +3 familias**, `foundation.testing.utc_datetimes`) y **U2** (`Database.read/write`, `BaselineRepository`/`AlertRepository` «los llena U6 — OQ-02», esquema `baselines`/`alerts` **intacto**, `IngestionService` — **hook opcional `on_accepted`**, `create_app` — **wiring acotado**, precedente U4 `runner=`/`scope_validator=`). **U7** consumirá `metric_samples()` después — este plan solo deja el contrato.
- **Interfaces/contratos**: env `SENTINEL_BASELINE_{K, ABSOLUTE_BPS, INTERVAL_SECONDS, COLLECTOR_TIMEOUT_SECONDS}` (loader propio estricto; `ABSOLUTE_BPS` sin default); `metric_key = "<metric>|<interface>|<protocol>"`, metric ∈ {`bytes_per_second`,`packets`,`flows`}, R-01 evalúa solo `bytes_per_second`; API C5 `ConditionService` (`on_accepted`, `update_baseline`, `evaluate`, `is_suppressed`, `collector_up`, `metric_samples`); protocols locales `BaselineStore` (`list`/`upsert`), `AlertStore` (`upsert`/`list_firing`), `Clock` (`now`).
- **Límites**: `baseline/` **nunca** importa `sentinel.core.*` ni `sqlite3` (BR-U6-01, test AST); cero cambios de esquema/`CoreSettings`/Dockerfile; sin `/metrics` propio (U7); sin deps pip nuevas (TECH-01); sin retención (NFR-Req Q6); single-sensor.
- **Toolchain**: hereda U1..U5 (ruff E,F,W,I,N,UP,B,SIM, mypy `src/sentinel`, pytest+cov, `TestClient`, `foundation.testing`, hypothesis); gates: total `--cov=sentinel ≥70` **+** `coverage report --include='*/baseline/*' --fail-under=70` (P13/Q3=A).
- **Decisión de wiring (ejecución)**: adaptadores duck-typing en **`src/sentinel/core/baseline_wiring.py`** (nuevo, pequeño — precedente: U4 creó `core/discovery/trigger.py`): traducen `Database`+repos (que exigen `conn`) a los Protocol limpios de `baseline/`; `app.py` los consume.

---

## 2. Pasos de generación (numerados, checkbox)

- [x] **Step 1 — Project structure setup**
  Crear `src/sentinel/baseline/__init__.py`, `config.py`, `statistics.py`, `conditions.py`, `indicators.py`; `tests/unit/baseline/__init__.py`; `tests/integration/test_baseline_suppression.py` (placeholder); `tests/property/test_baseline_statistics.py` (placeholder).

- [x] **Step 2 — Config estricta (FD §3.1, BR-U6-02..04, Q5 FD)**
  Crear `src/sentinel/baseline/config.py`: `BASELINE_SAMPLES = 5` (constante de dominio, FR-BASE-01); `BaselineSettings` (Pydantic `frozen`, `extra="forbid"`): `k=3.0` (>0), `absolute_bps: float | None = None` (>0 si presente; **sin default numérico**), `interval_seconds=5` (≥1), `collector_timeout_seconds=300` (≥1); `load_baseline_settings(environ=None)` ⇒ env `SENTINEL_BASELINE_*` con defaults anteriores, cualquier clave `SENTINEL_BASELINE_*` desconocida o violación ⇒ `ConfigError` (fail-fast); `CoreSettings` intacto (BR-U6-02).

- [x] **Step 3 — Unit tests: config (MNT-02)**
  `tests/unit/baseline/test_config.py`: `-k defaults` (k=3.0/interval=5/timeout=300/absolute None), `-k strict_env` (clave `SENTINEL_BASELINE_FOO` ⇒ `ConfigError`), `-k invalid_config` (k=0, interval=0, absolute=-1 ⇒ `ConfigError`), `-k absolute_optional` (ausente ⇒ None; presente ⇒ float >0), `-k samples_constant` (`BASELINE_SAMPLES == 5`).

- [x] **Step 4 — Estadística pura (FR-BASE-02/03, BR-U6-06..10, P15)**
  Crear `src/sentinel/baseline/statistics.py`: `mean(xs) -> float`; `sample_variance(xs) -> float` (`n-1`; `n<2 ⇒ 0.0`); `select_threshold(mu, sigma, k, absolute: float | None) -> float | None` (establecida ⇒ `mu + k*sigma`; no establecida ⇒ `absolute` si está, si no `None`); puro, sin I/O, solo stdlib.

- [x] **Step 5 — Unit tests: statistics (MNT-02, blanco PBT)**
  `tests/unit/baseline/test_statistics.py`: `-k mean_values`, `-k variance_sample` (n-1: [1,2,3] ⇒ 1.0), `-k variance_single` (n=1 ⇒ 0.0), `-k threshold_relative` (μ+k·s), `-k threshold_absolute_fallback`, `-k threshold_none` (sin absolute y no establecida ⇒ None), `-k strict_comparison` (helper/comparación `>` estricto: igual ⇒ no dispara).

- [x] **Step 6 — ConditionService: dominio + protocols + orquestador (FD §3.2–3.6, BR-U6-08..18, P1/P4/P6/P11, Q1–Q6 NFR-Design)**
  Crear `src/sentinel/baseline/conditions.py`:
  - `Protocol` locales: `BaselineStore` (`list() -> list[dict]`, `upsert(b) -> None`), `AlertStore` (`upsert(a) -> None`, `list_firing() -> list[dict]`), `Clock` (`now() -> datetime`); `SystemClock` (UTC, una línea — la inyecta `create_app`).
  - `@dataclass(slotted)`: `BaselineState` (metric_key, samples list, mean, variance, established, t_first datetime|None, interval_seconds), `TrafficWindow` (window_start/end, interface, protocol, bytes_per_second, packets, flows, sensor_id), `Condition` (rule `Literal["R-01"]`, metric_key, state `ConditionState`, measured_value, threshold, suppressed, interface, protocol, sensor_id, window_start).
  - `ConditionService.__init__(*, baselines, alerts, settings, clock=None, logger=...)`: `states: dict[str, BaselineState]`, `active: dict[condition_id, alert]`; hidratación `hydrate()` (list baselines → estados; `list_firing` → alertas activas; **no lanza** — llamado por wiring en try).
  - `update_baseline(metric_key, sample, now)`: n<5 append + stats interim; n=5 congelar (s² con n-1) + `log event=baseline_established`; n>5 **no-op** (P6); primera muestra ⇒ `t_first`.
  - `is_suppressed(metric_key, now)`: `now < t_first + N*interval` (prioritaria, Q7 FD).
  - `evaluate(window) -> Condition`: supresión ⇒ `baseline_establishing` (sin alerta); `select_threshold` con estado; `None` ⇒ `no_data`; `measured > threshold` estricto ⇒ `firing` | `resolved`.
  - `on_accepted(observations)`: **try/except global ⇒ log, nunca propaga** (P1/BR-U6-15); filtra `TrafficObservation` (ignora discovery/arp); por obs: para las 3 métricas ⇒ `metric_key` + `update_baseline` + persist `BaselineStore.upsert` (Q3: solo la serie observada); para `bytes_per_second`: `evaluate` ⇒ upsert alerta (`condition_id = uuid5(NS, "R-01|"+metric_key)`, `alert_id = uuid5(NS, condition_id+"|"+fired_at)` con `NS = uuid5(NAMESPACE_DNS, "sentinel.baseline.condition")` — patrón U5; fila por activación, re-fire ⇒ fila nueva, `resolved` actualiza la vigente, BR-U6-17) + `log condition_firing/condition_resolved`; baseline upsert fallo ⇒ `log condition_persistence_failed` + continúa.
  - `collector_up(traffic_last_seen) -> int`: pura, `0/1` por `now - last <= settings.collector_timeout_seconds` (R-04 indicador).
  - `metric_samples() -> list[tuple[str, dict[str, str], float]]` delegando a `indicators.py`.

- [x] **Step 7 — Unit tests: conditions (MNT-02, AC ST-M5-01..03, P1/P4)**
  `tests/unit/baseline/test_conditions.py` (stores fake en memoria + `FakeClock`): `-k first_five_samples` (ST-M5-01), `-k interim_stats` (media interim, var 0 en n=1), `-k freeze_after_five` (congelada: extra ⇒ no-op), `-k suppression_window` (ST-M5-03: dentro de `t_first+5×interval` ⇒ establishing, **sin fila**; supresión prioritaria sobre absolute), `-k threshold_firing` (fuera de ventana, `>` ⇒ firing + fila), `-k threshold_equal_no_fire` (igual ⇒ no fire, estricto), `-k resolved_transition` (bajo umbral ⇒ resolved en la fila vigente), `-k no_data_without_absolute` (no establecida y sin absolute ⇒ no_data), `-k alert_ids_stable` (BR-U6-17: mismos inputs ⇒ mismos ids; re-fire ⇒ fila nueva), `-k dedup_no_double_sample` (solo obs aceptadas — BR-U6-11, simulado), `-k persistence_failure_degrades` (store que lanza ⇒ `condition_persistence_failed` + estado en memoria + sin excepción), `-k collector_up_timeout`, `-k hydration_loads_states`, `-k persisted_roundtrip` (BR-U6-16: lo escrito por los fakes tiene las columnas del esquema).

- [x] **Step 8 — Indicadores (FD §3.5, BR-U6-22/23, Q7/Q9 NFR-Design)**
  Crear `src/sentinel/baseline/indicators.py`: `metric_samples(states, active_alerts, ...) -> list[Sample]` — proyección pura: `sentinel_traffic_threshold_exceeded{interface,protocol}` 1/0 por serie R-01, `sentinel_baseline_status{state}` (`establishing`/`available` por serie), `sentinel_baseline_established` (1 si establecida), `sentinel_collector_up{collector="traffic"}`; **sin labels prohibidos** (`src_ip`/`dst_ip`/`asset_id` — BR-21).

- [x] **Step 9 — Unit tests: indicators (MNT-02)**
  `tests/unit/baseline/test_indicators.py`: `-k label_cardinality`, `-k no_forbidden_labels`, `-k values_follow_state` (firing ⇒ 1, resolved/establishing ⇒ 0), `-k collector_flag`.

- [x] **Step 10 — Test de arquitectura: frontera de imports (BR-U6-01)**
  `tests/unit/baseline/test_boundaries.py` (AST): `baseline/*` importa solo `sentinel.foundation.*` + stdlib + typing; **nunca** `sentinel.core.*` ni `sqlite3`; `scapy` = 0 en `src/`.

- [x] **Step 11 — Foundation: +3 familias de métricas (BR-U6-22, precedente U4)**
  Editar `src/sentinel/foundation/metrics_contract.py`: añadir a `METRIC_FAMILIES` `sentinel_traffic_threshold_exceeded`, `sentinel_baseline_status`, `sentinel_collector_up` (las 3 nuevas; las existentes — p. ej. `sentinel_baseline_established` — intactas). `collect()` de U2 las emitirá en cero por su garantía de catálogo (sin edición de `collect.py`).

- [x] **Step 12 — Unit tests: familias nuevas (MNT-02)**
  Ampliar `tests/unit/foundation/test_metrics_contract.py`: las 3 familias presentes, `metric_name()` válido para ellas y `assert_labels` acepta `{interface, protocol, state, collector}`.

- [x] **Step 13 — U2 edit: hook `on_accepted` en IngestionService (FD §3.2, BR-U6-14/15)**
  Editar `src/sentinel/core/ingestion/service.py`: parámetro opcional `on_accepted: Callable[[list[Observation]], None] | None = None` en `__init__`; **post-commit** (tras cerrar `db.write()` y antes/aquí con los `accepted_obs`): `if self._on_accepted and accepted_obs: try: self._on_accepted([i for i,_,_ in accepted_obs]) except Exception: log event=ingestion_hook_failed` — jamás rompe el 202.

- [x] **Step 14 — Unit tests: hook de ingesta**
  Ampliar/crear en `tests/unit/core/test_ingestion_hook.py`: `-k hook_receives_accepted_only` (deduplicadas no llegan), `-k hook_exception_swallowed` (lanza ⇒ 202 + log, sin 500), `-k hook_none_default` (sin hook ⇒ comportamiento idéntico al actual — regresión U2).

- [x] **Step 15 — U2 edit: adaptadores + wiring (ID-U6-01, P11, FD §3.6/3.7)**
  Crear `src/sentinel/core/baseline_wiring.py`: `BaselineStore(db)` (`list`/`upsert` con `db.read()/write()` + `BaselineRepository`), `AlertStore(db)` (`upsert`, `list_firing` vía `AlertRepository.list(state="firing", limit=…)`), `build_condition_service(db, settings, clock) -> ConditionService` con hidratación en **try/except** (`event=baseline_hydration_failed` + servicio vacío — P2/NFR-Req Q5=A).

- [x] **Step 16 — U2 edit: `create_app` wiring (FD §3.7, ID-U6-01/07)**
  Editar `src/sentinel/core/api/app.py`: parámetros opcionales `baseline_settings=None` y `condition_clock=None` (seams de test, precedente `runner=`); por defecto `load_baseline_settings()` (fail-fast `ConfigError` ⇒ arranque fallido, como discovery) + `SystemClock`; `app.state.condition = build_condition_service(...)`; `IngestionService(..., on_accepted=app.state.condition.on_accepted)`.

- [x] **Step 17 — Unit tests: wiring**
  `tests/unit/core/test_baseline_wiring.py`: `-k hydration_ok` (filas en BD ⇒ estados cargados), `-k hydration_failure_starts_empty` (repo que lanza ⇒ log + servicio vacío + app sirve), `-k adapters_roundtrip` (upsert/list con BD temporal), `-k create_app_wires_hook` (`app.state.condition` presente; `ingestion._on_accepted` enlazado).

- [x] **Step 18 — Integration: supresión init/after window (AC ST-M5-03, GT-04)**
  `tests/integration/test_baseline_suppression.py` (`TestClient` + BD temporal + `condition_clock=FakeClock` + env baseline): `-k init_window` (5 obs en la ventana ⇒ `baselines` con `established=0/1`, **sin fila `alerts`**); `-k after_window` (reloj avanza `> t_first+5×interval`, obs con `bytes_per_second` alto ⇒ fila `alerts` firing con `rule=R-01` + evidence completa).

- [x] **Step 19 — Integration: ciclo de vida de alerta (BR-U6-17, GT-04)**
  Mismo archivo o `test_alert_lifecycle.py`: `-k fire_resolve_refire` (firing ⇒ resolved en la misma fila ⇒ nueva activación ⇒ **fila nueva** con `alert_id` distinto); `-k evidence_fields` (claves exactas: measured_value, threshold, k, mu, sigma, window_start, interface, protocol, sensor_id).

- [x] **Step 20 — PBT: baseline calculations (NFR-TECH-03 designado, Q2 NFR-Req=A, P12)**
  `tests/property/test_baseline_statistics.py` (hypothesis + `foundation.testing.utc_datetimes`): (1) media/varianza `n-1` == brute force; (2) congelada: muestras extra no cambian μ/s²; (3) `select_threshold` monótono en `k` + `measured > threshold` consistente con fixtures bajo/igual/encima; (4) la máquina de estados solo emite `ConditionState` U1 y `suppressed ⇒ nunca firing`.

- [x] **Step 21 — CI: gate de cobertura de baseline (P13/Q3=A, TS-U6-09)**
  Editar `.github/workflows/ci.yml` (workspace root): paso nuevo tras el gate de traffic: `- name: Baseline coverage gate (U6, P11)` → `coverage report --include='*/baseline/*' --fail-under=70`; mantener gates total, GUI, discovery y traffic.

- [x] **Step 22 — README + docs de la unidad**
  Añadir sección **Baseline & conditions** en `README.md`: env `SENTINEL_BASELINE_*` con defaults (`ABSOLUTE_BPS` obligatorio en values), flujo (5 muestras → 25 s supresión → `μ+k·s` estricto), eventos `component=baseline.*`, handoff `values.yaml` a U9 (ID-U6-07), nota ST-M5-01..04 documented-only (mínimo R-01/GT-04).

- [x] **Step 23 — Validación local**
  Ejecutar: `ruff check .` · `ruff format --check .` · `mypy src/sentinel` · `pytest tests/unit tests/property tests/integration -q --cov=sentinel --cov-fail-under=70` + `coverage report --include='*/baseline/*' --fail-under=70` — todo en verde.

- [x] **Step 24 — Resumen de generación**
  Crear `aidlc-docs/construction/u6-baseline/code/code-generation-summary.md`: archivos creados/modificados (ediciones acotadas: `metrics_contract.py`, `service.py`, `app.py`, `ci.yml`, `README.md`; nuevo `core/baseline_wiring.py`), verificación de frontera (AST, scapy=0), desviaciones D-U6-*, cobertura total y de `baseline/`, historias ST-M5-01..04 documented-only + soporte generado, estado del repo (sin `.git`).

---

## 3. Trazabilidad historias/diseño → pasos

| Elemento | Pasos |
|---|---|
| ST-M5-01 first-5 / FR-BASE-01 | 6, 7 (`first_five_samples`), 18 |
| ST-M5-02 mean/variance / FR-BASE-02 | 4, 5, 6, 20 |
| ST-M5-03 suppression / FR-BASE-04 | 6, 7 (`suppression_window`), 18 |
| ST-M5-04 indicators / FR-BASE-05 (R-01) | 8, 9, 11, 12 |
| FR-BASE-03 umbral k + absoluto | 2, 4, 5, 6 |
| R-01/GT-04 (alerta persistida) | 6, 7, 13–19 |
| BR-U6-01 frontera | 10 |
| BR-U6-14/15 hook | 13, 14 |
| BR-U6-16/17 persistencia/ids | 6, 7, 19 |
| NFR-TECH-03 PBT | 20 |
| P13 gate / TS-U6-09 | 21 |
| NFR-U6-OPS-01 handoff | 22 |
| ID-U6-01/05/07 wiring/health/env | 15, 16, 17 |

## 4. Fuera de alcance (documentado, sin código)

- R-02/R-04 como alerta persistida, rolling window, re-establecimiento por gaps (FD §5).
- `/metrics` real, `PrometheusRule` con `for`, retención de datos (U7/U8/U9+).
- Helm values/manifests (U9), captura real (U5), cualquier cambio de esquema/Dockerfile/`CoreSettings`.
