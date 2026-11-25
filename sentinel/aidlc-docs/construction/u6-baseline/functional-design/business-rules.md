# Business Rules & Validation — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-19
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U6 — `src/sentinel/baseline/`
**Traza**: ST-M5-01..04 (documented-only, mínimo R-01/GT-04), FR-BASE-01..05, FR-OBS-02, PRD §3.3/§3.4; plan Q1–Q13 = A; `component-methods.md` §4, `implementation-scope.md` M5, contratos U1/U2.

---

## 1. Configuración y arranque (fail-fast)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U6-01 | `baseline/` importa solo `foundation` + stdlib; **nunca** `sentinel.core.*` ni `sqlite3`; repos/clock inyectados por `create_app` con duck-typing (`Protocol` local) — core importa baseline, nunca al revés | Q1=A, precedente U4/U5 | `pytest tests/unit/baseline/test_boundaries.py` (ast de imports) |
| BR-U6-02 | Loader propio `load_baseline_settings` desde `SENTINEL_BASELINE_*`; clave desconocida o valor inválido ⇒ `ConfigError` al arranque; `CoreSettings` de U1 **no cambia** | Q5=A, BR-07 U1 | `tests/unit/baseline/test_config.py -k invalid_config` + `-k strict_env` |
| BR-U6-03 | Defaults: `K=3.0` (>0), `INTERVAL_SECONDS=5` (≥1), `COLLECTOR_TIMEOUT_SECONDS=300` (≥1, alineado BR-U3-17); `ABSOLUTE_BPS` **sin default** (ausente ⇒ fallback no disponible) — sin umbrales arbitrarios | Q5=A, PRD §3.3, FR-BASE-03 | `test_config.py -k defaults` + `-k absolute_optional` |
| BR-U6-04 | `ABSOLUTE_BPS` presente ⇒ float > 0; `K` presente ⇒ float > 0; violación ⇒ `ConfigError` | Q5=A, ST-M5-02 | `test_config.py -k invalid_config` |

## 2. Estadística de la línea base (FR-BASE-01/02, ST-M5-01)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U6-05 | Serie por `metric_key = "<metric>\|<interface>\|<protocol>"` con `metric ∈ {bytes_per_second, packets, flows}` (condición R-01 solo sobre `bytes_per_second`) | Q3/Q4=A, ST-M5-04 AC | `tests/unit/baseline/test_baseline.py -k metric_key_format` |
| BR-U6-06 | **`n < 5`** ⇒ `establishing`: acumula muestra; media aritmética; varianza muestral `s² = Σ(xᵢ−μ)²/(n−1)` (`n=1` ⇒ `s²=0`); `established=false` — estado reportado `establishing` (ST-M5-01 AC2) | FR-BASE-01/02, ST-M5-01 AC1/AC2 | `test_baseline.py -k five_samples` (5 muestras ⇒ media exacta, `n-1=4`) + `-k establishing_below_five` |
| BR-U6-07 | **`n = 5`** ⇒ fija `mean`/`variance` (`denominador 4`) y `established=true`; **`n > 5`** ⇒ congelada: `update_baseline` es no-op (sin recálculo ni append — PRD «primeras cinco muestras») | Q6=A, FR-BASE-01 | `test_baseline.py -k frozen_after_five` |
| BR-U6-08 | **Determinismo**: mismas muestras + mismos settings ⇒ mismos `mean`/`variance`/estados (reloj inyectable; sin I/O ni red) | Q12=A, criterio frontera unit-of-work §U6 | `test_baseline.py -k deterministic` (dos corridas ⇒ iguales) |

## 3. Umbral y selección (FR-BASE-03, ST-M5-02)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U6-09 | `select_threshold`: baseline **establecida** ⇒ `μ + k·s` (`s = √s²`, `k` de config); no establecida ⇒ `ABSOLUTE_BPS` si está configurado; si no ⇒ `None` (→ `no_data`) | FR-BASE-03, ST-M5-02 AC1/AC2 | `tests/unit/baseline/test_threshold.py -k mu_plus_k_sigma` (k=3 ⇒ `μ+3s`) + `-k absolute_fallback` |
| BR-U6-10 | Comparación **estricta**: `measured > threshold` ⇒ `firing`; `measured == threshold` ⇒ **no** dispara; `measured < threshold` ⇒ `resolved` (o sin fila) | Q12=A, GT-04 «when >» | `test_threshold.py -k below_equal_above` (fixtures bajo/igual/encima) |

## 4. Supresión durante establecimiento (FR-BASE-04, ST-M5-03)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U6-11 | `is_suppressed(metric_key, now) = now < t_first + N·interval` (N=5; ≈25 s @ 5 s) — **la supresión tiene prioridad**: mientras dure, `evaluate` ⇒ `baseline_establishing`, métrica `0`, **sin alerta**, aunque el absoluto o `μ+k·s` se superen | Q7=A, FR-BASE-04, ST-M5-03 AC1, PRD §3.3 | `tests/integration/test_baseline_suppression.py -k init_window` |
| BR-U6-12 | Baseline `established` **y** fuera de ventana ⇒ evaluación normal: supera `μ+k·s` ⇒ condición publicada (`firing`) | ST-M5-03 AC2 | `test_baseline_suppression.py -k after_window` |
| BR-U6-13 | `t_first` se reinicia al cargar una baseline **parcial** tras restart (re-supresión conservadora — sin falsos positivos post-restart); baseline `established` persistida carga sin supresión | Q8=A + determinismo | `tests/unit/baseline/test_restart.py -k partial_reestablishes` + `-k established_kept` |

## 5. Push, idempotencia y persistencia (Q2/Q8=A, OQ-02)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U6-14 | El hook `on_accepted` solo recibe observaciones **recién insertadas** (post-commit, tras `insert_ignore`); un lote reenviado **deduplicado no repite muestras** de la línea base | Q2=A, BR-U2-07 | `tests/integration/test_ingest_idempotency.py` (sin regresión) + `tests/unit/baseline/test_conditions.py -k dedup_no_double_sample` (mismo lote 2× ⇒ n=1) |
| BR-U6-15 | Excepción en el hook ⇒ `log event="condition_evaluation_failed"` y **no** propaga: el `202` de la ingesta ya se ganó (la condición no puede romper el ingest) | Q2=A, NFR-AVAIL-01 | `test_conditions.py -k hook_error_swallowed` |
| BR-U6-16 | Baseline se persiste con `BaselineRepository.upsert` (columnas OQ-02: `metric_key, interval_seconds, samples, mean, variance, established, updated_at`); alertas con `AlertRepository.upsert` (`alert_id, condition_id, rule, metric_key, state, measured_value, threshold, fired_at, resolved_at, evidence`) — **sin cambiar el esquema** | Q8=A, OQ-02 | `test_conditions.py -k persisted_roundtrip` (lee lo escrito con los repos) |
| BR-U6-17 | `condition_id = uuid5("R-01\|" + metric_key)`; `alert_id = uuid5(condition_id + "\|" + fired_at_iso)` — una fila por activación; re-fire ⇒ fila nueva; `firing→resolved` actualiza la fila vigente | U2 FD domain-entities (alert_id UUIDv5) | `test_conditions.py -k alert_ids_stable` (mismo contenido ⇒ mismos ids) |

## 6. Evaluación y estados (ST-M5-02/03/04, GT-04)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U6-18 | `ConditionState`: suprimido ⇒ `baseline_establishing`; con threshold y `measured > threshold` ⇒ `firing`; bajo el umbral con alerta previa ⇒ `resolved`; sin threshold (no establecido, sin absoluto, fuera de ventana) ⇒ `no_data` — los 4 valores del Literal U1 | Q7/Q12=A, U1 `ConditionState` | `test_threshold.py -k state_machine` |
| BR-U6-19 | Solo R-01 genera `AlertCondition` persistida (`rule="R-01"`); R-02/R-03/R-04 **sin fila** (diseño documentado, consumidor U7/U8) | Q10=A, implementation-scope M5 | `test_conditions.py -k only_r01_persisted` |
| BR-U6-20 | Solo `bytes_per_second` evalúa condición; `packets`/`flows` mantienen baseline y estado (`baseline_status`) sin alerta | Q4=A, FR-BASE-02 | `test_baseline.py -k three_metrics_condition_bytes_only` |
| BR-U6-21 | `collector_up(traffic_last_seen, now, timeout)`: `None` o `now − last_seen > timeout` ⇒ `0`; dentro del plazo ⇒ `1` (función pura; U7 la llamará con el heartbeat de U2) | ST-M5-04 AC2, R-04, BR-U3-17 | `tests/unit/baseline/test_collector_up.py -k stale_sensor_down` + `-k fresh_sensor_up` |

## 7. Indicadores (ST-M5-04, Q9=A)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U6-22 | Familias nuevas añadidas al catálogo U1 `METRIC_FAMILIES`: `sentinel_traffic_threshold_exceeded`, `sentinel_baseline_status`, `sentinel_collector_up` (precedente U4); sin labels de alta cardinalidad (`interface`/`protocol`/`state`/`collector`/`component` permitidos) | Q9=A, BR-20..22 U1 | `test_indicators.py -k families_in_catalog` + revisión `assert_labels` |
| BR-U6-23 | `metric_samples()` produce tuplas `(nombre, labels, valor)` deterministas: `sentinel_traffic_threshold_exceeded{interface,protocol} ∈ {0,1}`; `sentinel_baseline_status{state} = 1` solo para el estado vigente por serie; `sentinel_collector_up{collector="traffic"} ∈ {0,1}` | ST-M5-04 AC1/AC2, FR-OBS-02 | `test_indicators.py -k threshold_exceeded_value` + `-k baseline_status_establishing` |
| BR-U6-24 | Valores **por serie** con labels `interface`+`protocol` (cardinalidad baja: interfaces del sistema × {tcp,udp,icmp,other}); prohibido `src_ip`/`dst_ip`/`asset_id` | Q3=A, BR-21 U1 | `test_indicators.py -k label_cardinality` |

## 8. Frontera y no-funcionales

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U6-25 | Sin red en los cálculos: `statistics`/`evaluate`/`select_threshold`/`collector_up` son funciones puras o usan reloj inyectado — tests sin sockets ni sleep | criterio frontera unit-of-work §U6, MNT-02 | revisión de imports (`httpx`/`socket` ausentes en `baseline/`) |
| BR-U6-26 | U6 no escribe `events` ni inventario, no modifica observaciones, no expone endpoints ni `/metrics` (solo produce valores); sin acciones automáticas ni canales externos | unit-of-work §U6 «Qué NO hace» | `test_boundaries.py` + revisión |
| BR-U6-27 | GT-04: con serie establecida y un spike `bytes_per_second > μ+k·s` llegado por ingesta ⇒ alerta `R-01` persistida + `sentinel_traffic_threshold_exceeded = 1` (fixtures, sin red real) | GT-04, R-01, demo-plan | `tests/integration/test_gt04_threshold.py -k high_traffic_fires` |

## 9. Re-mapeo de verificación de AC (Q13=A, precedente D-U5-04)

| AC original (stories.md) | Ruta re-mapeada |
|---|---|
| `pytest tests/unit/test_baseline.py -k five_samples` | `pytest tests/unit/baseline/test_baseline.py -k five_samples` |
| `curl …/metrics \| grep sentinel_baseline_status \| grep -c establishing` | `pytest tests/unit/baseline/test_indicators.py -k baseline_status_establishing` (valor que U7 expondrá; el `curl` literal se verifica en U7/Build & Test) |
| `pytest tests/unit/test_threshold.py -k mu_plus_k_sigma` | `pytest tests/unit/baseline/test_threshold.py -k mu_plus_k_sigma` |
| `pytest tests/unit/test_threshold.py -k absolute_fallback` | `pytest tests/unit/baseline/test_threshold.py -k absolute_fallback` |
| `pytest tests/integration/test_baseline_suppression.py -k init_window` | `pytest tests/integration/test_baseline_suppression.py -k init_window` (misma ruta, ya en estructura por unidad) |
| `pytest tests/integration/test_baseline_suppression.py -k after_window` | `pytest tests/integration/test_baseline_suppression.py -k after_window` |
| `curl …/metrics \| grep '^sentinel_traffic_threshold_exceeded 1'` | `pytest tests/unit/baseline/test_indicators.py -k threshold_exceeded_value` (+ `curl` en U7) |
| `curl …/metrics \| grep '^sentinel_collector_up{collector="traffic"} 0'` | `pytest tests/unit/baseline/test_collector_up.py -k stale_sensor_down` (+ `curl` en U7) |
