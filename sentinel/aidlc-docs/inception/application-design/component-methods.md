# Component Methods — Sentinel

**Fase**: INCEPTION — Application Design
**Fecha**: 2026-11-07
**Estado**: GENERATED — pendiente de aprobación
**Nivel de detalle**: alto nivel (Q8=A). Las reglas de negocio finas se definen en Functional Design (CONSTRUCTION).

> Las firmas usan una notación tipo Python solo como contrato conceptual. No es código de producción.

---

## 1. API Layer (C2) — contratos HTTP

| Método | Ruta | Entrada | Salida | Propósito |
|---|---|---|---|---|
| POST | `/api/v1/ingest` | `IngestBatch` | `202 IngestResult` | Ingesta de observaciones de discovery/tráfico/ARP |
| GET | `/api/v1/assets` | filtros de consulta | `Page[AssetSummary]` | Inventario paginado |
| GET | `/api/v1/assets/{asset_id}` | `asset_id` | `AssetDetail` | Detalle de activo |
| GET | `/api/v1/events` | `from`, `to`, `asset_id`, `rule`, `severity` | `Page[Event]` | Eventos y alertas |
| GET | `/api/v1/alerts` | `from`, `to`, `state` | `Page[Alert]` | Alertas con estado firing/resolved |
| GET | `/api/v1/health` | — | `HealthStatus` | Estado del Core, ciclos y colectores |
| GET | `/api/v1/export` | `format=csv\|json`, `from`, `to` | `File` | Exportación de evidencia |
| POST | `/api/v1/discovery` | `DiscoveryRequest` | `202 DiscoveryRun` | Disparo manual de discovery |
| GET | `/api/v1/discovery/{run_id}` | `run_id` | `DiscoveryRunStatus` | Estado del discovery manual |
| GET | `/api/v1/report` | `from`, `to`, `format=md\|pdf` | `ReportArtifact` | Reporte de red bajo demanda |
| GET | `/metrics` | — | `text/plain; version=0.0.4` | Exposición Prometheus (puerto 9108) |

**Códigos de error**: `400` validación/alcance, `404` recurso inexistente, `409` ciclo de discovery ya en ejecución, `422` esquema inválido, `503` dependencia no disponible.

---

## 2. IngestionService (C3)

```python
def ingest_discovery(batch: DiscoveryBatch) -> IngestResult: ...
def ingest_traffic(batch: TrafficBatch) -> IngestResult: ...
def ingest_arp(batch: ArpBatch) -> IngestResult: ...
def deduplicate(observations: list[Observation]) -> list[Observation]: ...
def normalize(observation: Observation) -> Observation: ...
```

- **`ingest_*`**: valida el lote, normaliza, deduplica y persiste vía repositorios; devuelve contadores y `ingest_id`.
- **`deduplicate`**: aplica la identidad estable de evento (UUID) para idempotencia.
- **`normalize`**: unifica formato de MAC, timestamps e IP; marca el origen (observado/inferido/declarado/desconocido).

## 3. InventoryService (C4)

```python
def reconcile(cycle: DiscoveryCycle) -> list[InventoryChange]: ...
def list_assets(filters: AssetFilters) -> Page[AssetSummary]: ...
def get_asset(asset_id: str) -> AssetDetail: ...
def mark_absent(asset_id: str, grace_period: timedelta) -> InventoryChange: ...
```

- **`reconcile`**: compara el ciclo con el inventario previo; solo evalúa ausencias si el ciclo es completo y exitoso.
- **`list_assets` / `get_asset`**: consultas para la GUI y el reporte.
- **`mark_absent`**: aplica el periodo de gracia configurado.

## 4. ConditionService (C5)

```python
def update_baseline(metric_key: MetricKey, sample: Sample) -> BaselineState: ...
def evaluate(window: TrafficWindow) -> list[Condition]: ...
def is_suppressed(metric_key: MetricKey, now: datetime) -> bool: ...
```

- **`update_baseline`**: mantiene las primeras N muestras por métrica (subconjunto de M5).
- **`evaluate`**: compara contra `μ + k·s` o umbral absoluto de fallback.
- **`is_suppressed`**: evita alertas durante la ventana de establecimiento.

## 5. MetricsExporter (C6)

```python
def collect() -> list[MetricFamily]: ...
def render_prometheus(families: list[MetricFamily]) -> str: ...
```

- **`collect`**: agrega inventario, tráfico, ARP, ciclos y salud de colectores; sin labels de alta cardinalidad.
- **`render_prometheus`**: produce el formato de exposición de Prometheus.

## 6. ReportService (C7)

```python
def generate(date_from: datetime, date_to: datetime, fmt: ReportFormat) -> ReportArtifact: ...
def build_inventory_section(rows: list[AssetSummary]) -> str: ...
def build_changes_section(changes: list[InventoryChange]) -> str: ...
def build_top_talkers_section(range: DateRange) -> str: ...
def build_alerts_section(alerts: list[Alert]) -> str: ...
def render_pdf(markdown: str) -> bytes: ...
```

- **`generate`**: orquesta las secciones y devuelve Markdown o PDF de forma determinista.
- **`build_top_talkers_section`**: devuelve `sin datos` si no hay telemetría de tráfico, sin inventar valores.

## 7. DiscoveryService (C9 — ejecución manual en Core)

```python
def trigger(request: DiscoveryRequest, timeout_seconds: int) -> DiscoveryRun: ...
def status(run_id: str) -> DiscoveryRunStatus: ...
def acquire_single_run_lock() -> bool: ...
def run_cycle(hosts: list[str], timeout_seconds: int) -> DiscoveryResult: ...
```

- **`trigger`**: valida alcance, adquiere el lock de ejecución única y lanza el ciclo acotado por timeout.
- **`status`**: devuelve `running`, `completed`, `timeout` o `failed`.
- **`run_cycle`**: invoca el mismo módulo que usa el CronJob y envía observaciones al Core.

## 8. Scope & Config Validator (C12)

```python
def validate_scope(mode: ScopeMode, hosts: list[str], cidrs: list[str]) -> ValidationResult: ...
def validate_ports(ports: list[int]) -> ValidationResult: ...
def validate_target(target: str) -> ValidationResult: ...
```

- Devuelve `ok` o `scope_violation` con motivo; nunca permite objetivos fuera de la lista autorizada.

## 9. Repositorios (C11)

```python
class AssetRepository:
    def upsert(self, asset: Asset) -> None: ...
    def list(self, filters: AssetFilters) -> Page[AssetSummary]: ...
    def get(self, asset_id: str) -> AssetDetail | None: ...

class EventRepository:
    def save(self, events: list[Event]) -> None: ...
    def list(self, filters: EventFilters) -> Page[Event]: ...

class TrafficRepository:
    def save_windows(self, windows: list[TrafficWindow]) -> None: ...
    def aggregate(self, date_range: DateRange) -> list[TrafficAggregate]: ...

class AlertRepository:
    def upsert(self, alerts: list[Alert]) -> None: ...
    def list(self, filters: AlertFilters) -> Page[Alert]: ...

class DiscoveryRunRepository:
    def save(self, run: DiscoveryRun) -> None: ...
    def get(self, run_id: str) -> DiscoveryRunStatus | None: ...
```

- Todos son síncronos y comparten la conexión SQLite del Core (un solo escritor).

## 10. GUI handlers (C8)

```python
def get_assets_page(filters) -> HTMLResponse: ...
def get_asset_detail_page(asset_id: str) -> HTMLResponse: ...
def get_events_page(filters) -> HTMLResponse: ...
def get_alerts_page(filters) -> HTMLResponse: ...
def get_health_page() -> HTMLResponse: ...
def post_trigger_discovery(request: DiscoveryRequest) -> HTMLResponse: ...
def get_report_page() -> HTMLResponse: ...
def download_report(date_from, date_to, fmt) -> FileResponse: ...
```

- Renderizan Jinja + HTMX; validan y delegan toda la lógica en los servicios del Core.
- No acceden a SQLite ni ejecutan sondeos por sí mismos.

## 11. Colectores (C9/C10)

```python
def run_discovery(scope: ScopeConfig, timeout_seconds: int) -> DiscoveryBatch: ...
def run_sensor(feed: FeedConfig, window_seconds: int, fallback: bool) -> TrafficBatch: ...
def post_batch(core_url: str, token: str | None, batch: IngestBatch) -> IngestResult: ...
```

- **`post_batch`**: reintenta con backoff simple hasta obtener respuesta del Core.
- **`run_sensor`**: si `fallback=True` o no hay feed, carga fixtures reproducibles para la demo.

---

## 12. Notas para Functional Design

- Reglas exactas de reconciliación, baseline y supresión.
- Esquema SQLite definitivo e índices.
- Contratos Pydantic completos y validaciones de borde.
- Estrategia de idempotencia y límites de lote.
