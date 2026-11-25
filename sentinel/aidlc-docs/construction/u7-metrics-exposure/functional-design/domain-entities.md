# Domain Entities — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-24
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U7 — `src/sentinel/core/metrics/` + `deploy/monitoring/servicemonitor.yaml`
**Traza**: ST-M6-01..03, FR-CORE-02, FR-OBS-01/02; plan Q1–Q11 = Acepto todo; **U7 no crea tablas ni modelos de dominio nuevos** — opera sobre contratos U1 (ampliados), entidades U2/U5/U6 existentes y un manifiesto Kubernetes.

---

## 1. Contrato U1 ampliado (`foundation/metrics_contract.py`, Q3=C + Q10=B)

### 1.1 `METRIC_FAMILIES` (v2 — 14 elementos)

```text
# existentes (12)
sentinel_discovery_cycles_total          sentinel_discovery_cycles_failed_total
sentinel_flows_total                     sentinel_bytes_per_second
sentinel_arp_messages_total              sentinel_alerts_firing
sentinel_baseline_established            sentinel_traffic_threshold_exceeded
sentinel_baseline_status                 sentinel_collector_up
sentinel_collector_heartbeat_age_seconds sentinel_api_requests_total
# nuevas U7 (2, Q3=C)
sentinel_assets_total                    sentinel_asset_changes_total
```

Invariante: catálogo **cerrado** — `collect()` emite exactamente este conjunto (BR-U7-01); añadir familias exige actualizar el tuple y sus tests de contrato.

### 1.2 `ALLOWED_LABELS_DEFAULT` (v2 — 7 elementos, Q10=B)

```text
component  protocol  interface  rule  state  collector  metric
# └── U2/U7 ─┘  └─ U6/U5 ─┘        └ U6 ─┘  └── U6 ──┘
```

- `FORBIDDEN_LABELS = {src_ip, dst_ip, mac, asset_id}` **sin cambios** (BR-21, denylist).
- Nueva función **`assert_allowed(labels)`**: `ValueError` si contiene un prohibido **o** uno fuera de la allowlist (BR-U7-03). `assert_labels` (solo denylist) permanece para U6 y consumidores existentes.

### 1.3 `Sample` (sin cambios)

```text
Sample = tuple[str, dict[str, str], float]   # (familia, labels, valor)
```
Espejado por U6 (`baseline/indicators.Sample`) — misma forma, sin cambios.

---

## 2. Entidades en proceso (`core/metrics/collect.py`)

### 2.1 Contadores existentes (U2, sin cambios de forma)

| Entidad | Operaciones | Notas |
|---|---|---|
| `ApiRequestCounter` | `inc(state)`, `snapshot()`, `total()` | familia `api_requests_total` |
| `CycleCounter` | `record(status)`, `snapshot()`, `failed_total()` | `failed`/`timeout` ⇒ `cycles_failed_total` |

### 2.2 `ObservationCounters` (nueva, U7 — Q2=A)

```python
class ObservationCounters:
    def on_accepted(self, observations: Sequence[Observation]) -> None: ...
    def snapshot(self) -> dict[str, int]:   # {"flows": n, "arp_messages": m}
```

| Campo | Tipo | Regla de incremento |
|---|---|---|
| `flows` | `int` | `+= int(obs.flows)` por cada `TrafficObservation` aceptada (BR-U7-11) |
| `arp_messages` | `int` | `+= 1` por cada `ArpObservation` aceptada |

Invariantes: solo incrementa (monótono en proceso); no persiste (BR-U7-13); reset a 0 en nueva instancia; tipo de familia `*_total` ⇒ `TYPE counter`.

### 2.3 `collect()` — firma v2 (Q1/Q5/Q8=A)

```python
def collect(
    *,
    api_requests: ApiRequestCounter | None = None,
    cycles: CycleCounter | None = None,
    heartbeats: Mapping[str, str] | None = None,
    condition_service: ConditionServiceLike | None = None,   # Q5=A: metric_samples()
    db: DatabaseLike | None = None,                          # gauges SQLite
    obs_counters: ObservationCounters | None = None,         # Q2=A
    now: float | None = None,
) -> list[Sample]: ...
```

- `ConditionServiceLike` = Protocol local con `metric_samples() -> list[Sample]` (duck-typing, precedente U6 — sin import circular de `baseline` en el type-check estricto; el runtime pasa el objeto real de `app.state.condition`).
- `DatabaseLike` = Protocol con `query(...)`/equivalente para los COUNTs y la última observación (la implementación concreta usa el `Database` de U2 — mismo patrón de repos).
- Todos opcionales ⇒ `collect()` bare sigue devolviendo las 14 familias en cero (BR-U7-06).

### 2.4 Dict `HELP` (nuevo, Q11=A)

```python
HELP: dict[str, str] = { familia: "texto descriptivo real", ... }   # 14 entradas
```

- Sin «(U2 stub)»; familias nuevas documentan su fuente (p. ej. `sentinel_assets_total` → «Number of assets in inventory»).
- `render_prometheus` usa `HELP.get(family, …)` con fallback defensivo; `TYPE` sigue en `_type_of()` (sufijo `_total` ⇒ counter).

---

## 3. Entidades consumidas (sin cambios — frontera)

| Entidad | Dueño | Uso en U7 |
|---|---|---|
| `MetricsServer` | U2 `core/metrics/server.py` | **intacto** (Q8=A: sin clase nueva; el servidor ya delega en `collect_fn`) |
| `ConditionService.metric_samples()/collector_up()` | U6 `baseline/conditions.py` | llamados en el scrape (BR-U7-18/19); U7 no replica estados ni umbrales |
| `HealthService.sensor_heartbeats` | U2 `core/health/service.py` | edad del heartbeat (familia existente) |
| `IngestionService.on_accepted` (slot único) | U2 `core/ingestion/service.py` | compuesto por `_compose_hooks` en `create_app` (BR-U7-12); servicio sin ediciones |
| `TrafficObservation`, `ArpObservation` | U1/U5 `foundation/models.py` | fuente del hook (solo lectura de `flows`, tipo) |
| `EventType` (4 tipos de cambio) | U1 `foundation/events.py` | filtro de `asset_changes_total` (`asset_first_seen`, `asset_missing`, `arp_mapping_changed`, `port_service_changed`) |
| Tablas `assets`, `alerts`, `events`, `observations` | U2 esquema | solo `COUNT`/`ORDER BY` al scrape — **sin esquema nuevo** |

---

## 4. Entidad externa: `ServiceMonitor` (manifiesto, Q7=A)

| Campo | Valor | Regla |
|---|---|---|
| `apiVersion` | `monitoring.coreos.com/v1` | CRD de kube-prometheus-stack (SN-031) |
| `kind` | `ServiceMonitor` | BR-U7-21 |
| `metadata.name` / `namespace` | `sentinel-core` / `sentinel` | ST-M6-03 AC (`kubectl get servicemonitor -n sentinel`) |
| `metadata.labels.release` | `monitoring` | selector por defecto del stack (`helm release` name) |
| `spec.selector.matchLabels` | `app.kubernetes.io/name: sentinel-core` | ST-M6-03 AC (jsonpath de selección) |
| `spec.namespaceSelector.matchNames` | `[sentinel]` | el SM vive en `sentinel` pero debe seleccionar el Service homónimo |
| `spec.endpoints[0]` | `port: metrics`, `path: /metrics` | SN-032 (`port: metrics` ⇒ Service `metrics:9108`), pull model |

Archivo único: `deploy/monitoring/servicemonitor.yaml`. U7 no lo aplica (requiere CRD + clúster); lo validan tests estructurales sin PyYAML (BR-U7-21) y, en U9/U11, `kubectl apply`/GT.

---

## 5. Diagrama de relaciones

```mermaid
classDiagram
    class METRIC_FAMILIES { <<contract U1 v2>> +tuple 14 familias }
    class ALLOWED_LABELS { <<contract U1 v2>> +tuple 7 labels }
    class assert_allowed { +validate(labels) }
    class ObservationCounters { +flows int +arp_messages int +on_accepted() +snapshot() }
    class collect { +optional providers +Sample list }
    class HELP { +dict 14 }
    class ConditionService { <<U6 consumido>> +metric_samples() +collector_up() }
    class ServiceMonitor { <<externo>> deploy/monitoring/ }
    METRIC_FAMILIES --> collect : catálogo cerrado
    ALLOWED_LABELS --> assert_allowed : allowlist v2
    assert_allowed --> collect : por sample
    assert_allowed --> HELP : render por sample
    ObservationCounters --> collect : provider
    ConditionService --> collect : provider (scrape)
    HELP --> collect : render
    ServiceMonitor ..> MetricsServer : scrape a :9108/metrics
```

---

## 6. Resumen de cambios de contrato (aprobados por el plan)

| Artefacto U1 | Antes | Después (U7) | Pregunta |
|---|---|---|---|
| `METRIC_FAMILIES` | 12 | **14** (+`sentinel_assets_total`, +`sentinel_asset_changes_total`) | Q3=C |
| `ALLOWED_LABELS_DEFAULT` | 5 | **7** (+`collector`, +`metric`) | Q10=B |
| `assert_allowed()` | — | **nueva** (denylist + allowlist por sample) | Q10=B |
| `assert_labels()` | denylist | **sin cambios** | Q10=B |
| `metric_name()` / `FORBIDDEN_LABELS` | — | **sin cambios** | — |

> Nada más cambia en foundation; `CoreSettings`, esquema SQLite y `specs/backlog.md` quedan intactos.
