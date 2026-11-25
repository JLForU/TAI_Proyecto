# Domain Entities — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-19
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U6 — `src/sentinel/baseline/`
**Traza**: ST-M5-01..04 (documented-only, mínimo R-01/GT-04), FR-BASE-01..05; plan Q1–Q13 = A; **U6 escribe `baselines`/`alerts` vía repos U2 (OQ-02)** — sus entidades de dominio son puras y se proyectan a los contratos U1 (`Baseline`, `AlertCondition`, `ConditionState`) y al esquema de U2 sin cambios.

---

## 1. Entidades de dominio (`baseline/`, sin I/O)

### 1.1 `BaselineSettings` (`baseline/config.py`)

Modelo Pydantic `frozen` con `extra="forbid"` (patrón `foundation.config`):

| Campo | Env | Default | Validación |
|---|---|---|---|
| `k` | `SENTINEL_BASELINE_K` | `3.0` | float > 0 (BR-U6-04) |
| `absolute_bps` | `SENTINEL_BASELINE_ABSOLUTE_BPS` | `None` | ausente ⇒ `None` (sin default numérico, BR-U6-03); presente ⇒ float > 0 |
| `interval_seconds` | `SENTINEL_BASELINE_INTERVAL_SECONDS` | `5` | entero ≥ 1 |
| `collector_timeout_seconds` | `SENTINEL_BASELINE_COLLECTOR_TIMEOUT_SECONDS` | `300` | entero ≥ 1 (alineado `HEARTBEAT_STALE_SECONDS` BR-U3-17) |

Constante de dominio (no env): `BASELINE_SAMPLES = 5` (FR-BASE-01/ST-M5-01).

> `CoreSettings` (U1) no se modifica (BR-U6-02). Claves `SENTINEL_BASELINE_*` desconocidas ⇒ `ConfigError`.

### 1.2 `MetricKey` y muestra (valores de serie)

```text
metric_key = f"{metric}|{interface}|{protocol}"
  metric    ∈ {bytes_per_second, packets, flows}     # Q4=A
  interface ∈ str                                     # p. ej. "eth0"
  protocol  ∈ {tcp, udp, icmp, other}                 # Protocol U1
```

- `Sample = float` (valor de la métrica en la ventana): `bytes_per_second` (rate U5), `packets` (conteo por ventana), `flows` (conteo por ventana).
- Condición R-01 se evalúa **solo** para `bytes_per_second` (BR-U6-20); `packets`/`flows` mantienen baseline + `baseline_status`.

### 1.3 `BaselineState` (estado interno por serie)

Estado **en memoria** hidratado desde `BaselineRepository` (Q8=A):

| Campo | Tipo | Notas |
|---|---|---|
| `metric_key` | `str` | PK lógico |
| `samples` | `list[float]` | primeras ≤ 5 muestras (congeladas al establecer) |
| `mean` / `variance` | `float` | `s²` con denominador `n-1` (0 si `n=1`) |
| `established` | `bool` | `n ≥ 5` (BR-U6-06/07) |
| `interval_seconds` | `int` | de settings |
| `t_first` | `datetime` | primera muestra (memoria; ver BR-U6-13) |
| `last_alert_state` | `firing \| None` | transiciones de alerta (memoria, reconstruido al arranque) |

Invariantes: `established ⇒ len(samples) == 5` y `variance ≥ 0`; `update_baseline` no-op si `established` (Q6=A); sin timestamps de muestra en el esquema (OQ-02 fijo) — `t_first` es efímero.

### 1.4 `TrafficWindow` (vista de entrada a `evaluate`)

Adaptador interno con la forma de una `TrafficObservation` (honor a `component-methods.md` §4 `evaluate(window: TrafficWindow)`):

| Campo | Origen en `TrafficObservation` (U1) |
|---|---|
| `window_start`, `window_end` | `window_start`, `window_end` |
| `interface`, `protocol` | `interface`, `protocol` |
| `bytes_per_second`, `packets`, `flows` | homónimos |
| `sensor_id` | `sensor_id` (para `evidence`) |

### 1.5 `Condition` (resultado de `evaluate`)

| Campo | Tipo | Notas |
|---|---|---|
| `rule` | `Literal["R-01"]` | único implementado (BR-U6-19) |
| `metric_key` | `str` | serie evaluada |
| `state` | `ConditionState` (U1) | `baseline_establishing \| firing \| resolved \| no_data` |
| `measured_value` | `float \| None` | bytes/s medido |
| `threshold` | `float \| None` | `μ+k·s` o absoluto; `None` ⇒ `no_data` |
| `suppressed` | `bool` | `is_suppressed` en el momento de evaluar |
| `interface`, `protocol`, `sensor_id`, `window_start` | — | para labels/`evidence` |

### 1.6 API de `ConditionService` (C5, component-methods §4)

```python
class ConditionService:
    def __init__(self, *, baselines: BaselineStore, alerts: AlertStore,
                 settings: BaselineSettings, clock: Clock | None = None) -> None: ...
    def update_baseline(self, metric_key: str, sample: float, now: datetime) -> BaselineState: ...
    def evaluate(self, window: TrafficWindow) -> Condition: ...
    def is_suppressed(self, metric_key: str, now: datetime) -> bool: ...
    def on_accepted(self, observations: Sequence[Observation]) -> None: ...   # hook push (Q2=A)
    def collector_up(self, traffic_last_seen: datetime | None) -> int: ...    # R-04 (Q10=A)
    def metric_samples(self) -> list[tuple[str, dict[str, str], float]]: ...  # para U7 (Q9=A)
```

- `Protocol` locales `BaselineStore`/`AlertStore`/`Clock` viven en `baseline/`; las implementaciones concretas (`BaselineRepository`, `AlertRepository`, `SystemClock`) las inyecta `create_app` (Q1=A — `baseline/` no importa `core`).
- `clock` inyectable (patrón U5) ⇒ tests sin sleep/red.

## 2. Proyección a contratos U1 (sin modelos nuevos en foundation)

| Entidad U6 | Contrato U1 | Mapeo |
|---|---|---|
| `BaselineState` | `Baseline` | `metric_key`, `samples` (≤ `MAX_BATCH_ITEMS`), `mean`, `variance` (≥0), `established`, `interval_seconds` — serializado en `BaselineRepository.upsert` |
| `Condition` (firing/resolved) | `AlertCondition` | `condition_id`/`alert_id` UUIDv5 (BR-U6-17), `rule="R-01"`, `state`, `measured_value`, `threshold`, `fired_at`, `resolved_at`, `evidence: dict[str, str\|int\|float]` |
| estados de `Condition` | `ConditionState` | Literal U1 `["baseline_establishing","firing","resolved","no_data"]` (BR-U6-18) — **sin cambios en U1** |

`evidence` (claves fijas): `measured_value`, `threshold`, `k`, `mu`, `sigma`, `window_start`, `interface`, `protocol`, `sensor_id`.

## 3. Persistencia (esquema U2 OQ-02 — sin cambios)

### 3.1 `baselines` (escrita por U6 vía `BaselineRepository`)

| Columna | Origen |
|---|---|
| `metric_key` (PK) | `BaselineState.metric_key` |
| `interval_seconds` | `BaselineSettings.interval_seconds` |
| `samples` (JSON) | primeras ≤ 5 muestras |
| `mean`, `variance` | estadísticos (congelados al establecer) |
| `established` | 0/1 |
| `updated_at` | ISO del último upsert |

### 3.2 `alerts` (escrita por U6 vía `AlertRepository`)

| Columna | Origen |
|---|---|
| `alert_id` (PK) | `uuid5(condition_id + "\|" + fired_at_iso)` — fila por activación (BR-U6-17) |
| `condition_id` | `uuid5("R-01\|" + metric_key)` |
| `rule` | `"R-01"` |
| `metric_key` | serie |
| `asset_id` | `NULL` (condición de tráfico, no por activo) |
| `state` | `firing` \| `resolved` (estados de fila; `baseline_establishing`/`no_data` **no** crean fila) |
| `measured_value`, `threshold` | de la evaluación |
| `fired_at` / `resolved_at` | ISO UTC (clock inyectado) |
| `evidence` (JSON) | dict de §2 |
| `updated_at` | ISO del upsert |

> **No** se crean filas para `baseline_establishing`/`no_data` (BR-U6-11/18): la GUI (`GET /api/v1/alerts`) solo ve firing/resolved — coherente con «sin alertas durante establecimiento».

## 4. Indicadores producidos (salida hacia U7)

| Familia (U1 `METRIC_FAMILIES`) | Labels | Valor | Origen de estado |
|---|---|---|---|
| `sentinel_traffic_threshold_exceeded` | `interface`, `protocol` | `1` iff R-01 `firing` para la serie; `0` en otro caso | memoria `ConditionService` |
| `sentinel_baseline_status` | `state` (`establishing`\|`available`) | `1` solo para el estado vigente de la serie | `BaselineState.established` |
| `sentinel_baseline_established` (ya en catálogo) | `interface`, `protocol` | `1` si `established` | `BaselineState` |
| `sentinel_collector_up` | `collector="traffic"` | `1`/`0` según `collector_up(...)` | heartbeat de U5 (leído por U7) + timeout |

`metric_samples()` devuelve tuplas `(nombre_completo, labels, valor)` — formato `Sample` de `core/metrics/collect.py` (U7 las insertará sin traducir; U6 no importa `core`).

## 5. Entidades fuera de U6 (referencia)

| Entidad | Dueño | Relación |
|---|---|---|
| `TrafficObservation` | U1 (modelo) / U5 (productor) | fuente de muestras vía push |
| `HealthStatus.sensor_heartbeats` | U2 | entrada de `collector_up` (la consume U7 al exponer) |
| `Event` / `E-06 SensorUnavailable` | U2/U8 | documented-only en U6 (Q10=A) |
| `AlertOut` (API) | U2 | proyecta filas `alerts` de U6 hacia GUI/report |
