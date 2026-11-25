# Code Generation Plan — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — Code Generation (Part 1: Planning)
**Fecha**: 2026-11-11
**Estado**: AWAITING_APPROVAL — plan listo; esperando aprobación explícita para generar código
**Workspace root**: `/home/jhoseph/Documents/TAI/TAI_Proyecto/sentinel` (de `aidlc-state.md`)
**Patrón**: Greenfield multi-unit (monolith) → `src/{unit-name}/` = **`src/sentinel/core/`**, tests = **`tests/unit/core/`** + **`tests/integration/`** + **`tests/property/`**
**Este plan es la única fuente de verdad de Code Generation para U2.**

---

## 1. Contexto de la unidad

- **Historias**: ST-M4-01..07 (todas `implemented` en el story map; aquí se materializa el código).
  - ST-M4-01 Ingestion API · ST-M4-02 SQLite en PVC + recuperación · ST-M4-03 identidad/dedup · ST-M4-04 normalizar/correlacionar · ST-M4-05 JSON Lines · ST-M4-06 export CSV · ST-M4-07 query API.
- **Diseño aprobado**: Functional Design (flujos §3, BR-U2-01..42, esquema OQ-02 de 7 tablas), NFR Requirements (NFR-U2-*, TS-U2-01..11), NFR Design (P1–P13, componentes), Infrastructure Design (ID-U2-01..09, manifiestos spec).
- **Dependencias**: **U1** (satisfecha): `foundation.{models,errors,events,logging,retry,metrics_contract,testing,config}`. U4 (runner) llega después → `CycleRunner` inyectado con `503` hasta entonces. U3 consume la API (IP3); U6 escribe alerts/baselines (esquema creado aquí); U7 sustituye `collect()` (IP7).
- **Interfaces/contratos**: `POST/GET /api/v1/*` (sin `/report`), servidor 9108 con familias del contrato U1, esquema SQLite, `SENTINEL_*` (4 claves).
- **Entidades DB propias**: `assets`, `asset_ips`, `observations`, `events`, `alerts`, `baselines`, `discovery_runs` (OQ-02).
- **Límites**: Core = único escritor; sin K8s client, sin scapy/nmap, sin Jinja (GUI=U3), sin scheduler de export.
- **Toolchain**: hereda U1 (ruff, mypy, pytest+cov **≥70% en `sentinel/core`**, hypothesis); añade `fastapi`, `uvicorn`, `httpx` (pin exacto en `requirements.txt`).

---

## 2. Pasos de generación (numerados, checkbox)

- [x] **Step 1 — Project structure setup**
  Crear `src/sentinel/core/__init__.py`, paquetes `api/`, `db/`, `ingestion/`, `inventory/`, `query/`, `export/`, `health/`, `discovery/`, `metrics/` con `__init__.py`; `tests/unit/core/__init__.py`, `tests/integration/__init__.py`. Añadir a `requirements.txt` (pines exactos): `fastapi`, `uvicorn`, `httpx` (dev). Crear `.env.example` (`SENTINEL_DB_PATH`, `SENTINEL_INGEST_TOKEN`, `SENTINEL_PAGE_LIMIT`, `SENTINEL_MISSING_CYCLES`).

- [x] **Step 2 — Core config (Q13 FD, BR-U2-41/42)**
  Crear `src/sentinel/core/config.py`: `CoreSettings` Pydantic con exactamente 4 campos (`db_path`, `ingest_token`, `page_limit=100`, `missing_cycles=3`) + `load_core_settings()` fail-fast con `ConfigError`.

- [x] **Step 3 — Database + schema (P1/P2/P3/P4, OQ-02, BR-U2-18/20)**
  Crear `src/sentinel/core/db/schema.py` (DDL idempotente de las 7 tablas + índices según `domain-entities.md` §1) y `src/sentinel/core/db/database.py` (`Database`: context manager por request/tx, `write_lock` (P3), `startup_checks()` = `integrity_check` → exit-intent + stale runs `running→failed` (P1/P2), `close()` + `wal_checkpoint(TRUNCATE)` (P4)).
  *Historias: ST-M4-02.*

- [x] **Step 4 — Repositorios (Q9 FD/NFR, BR-U2-06/07/11/21..24/33)**
  Crear `src/sentinel/core/db/repos/{assets,observations,events,alerts,baselines,discovery_runs}.py`: SQL **parametrizado** con INSERT OR IGNORE (dedup), filtros + `limit/offset`, upsert por IP (`asset_ips`), conteos. Alerts/Baselines: solo esquema + acceso básico (los llena U6).

- [x] **Step 5 — Unit tests: config + database + repos (`tests/unit/core/`)**
  `test_config.py` (4 claves, env inválida), `test_database.py` (DDL idempotente ×2, write-lock concurrente sin `database is locked`, integrity_check con archivo corrupto ⇒ raise sin tocar, stale runs ⇒ failed, checkpoint en close), `test_repos_*.py` (upsert IP, OR IGNORE, filtros, paginación, 404 None).
  *Historias: ST-M4-02, ST-M4-03 (repos).*

- [x] **Step 6 — Evidence helper (P10 base, BR-U2-25..27)**
  Crear `src/sentinel/core/evidence.py`: `emit(kind, event_type, *, asset, method, protocol, condition, rule, threshold, measured_value, result, **extra)` → 1 línea JSON vía `foundation.get_logger` con `kind ∈ {observation, inference, event, alert}` + campos de evidencia.

- [x] **Step 7 — InventoryService (BR-U2-13..17, Q4 FD)**
  Crear `src/sentinel/core/inventory/service.py`: `reconcile()` — first_seen, last_seen, present/absent con `missing_cycles` (solo ciclos completed), `arp_mapping_changed`, emisión de eventos de inventario.
  *Historia: ST-M4-04.*

- [x] **Step 8 — IngestionService (BR-U2-01..08/11, P6, Q3/Q5 FD)**
  Crear `src/sentinel/core/ingestion/service.py`: validación (modelos U1, MAX_BATCH_ITEMS) → normalización (MAC/IP/UTC) → `dedup_key = uuid5(sha256(contenido normalizado))` → transacción única (observations + assets + events + reconcile) → `IngestResult{ingest_id, accepted, deduplicated, events_persisted}` → evidence emit.
  *Historias: ST-M4-01, ST-M4-03, ST-M4-04.*

- [x] **Step 9 — Unit tests: inventory + ingestion (`tests/unit/core/`)**
  `test_inventory.py` (N=3 con ciclos completed/timeout, transiciones, MAC change), `test_ingestion.py` (mismo lote ⇒ mismos UUIDs y contadores, MAC en mayúsculas ⇒ mismo `event_id`, rollback total ante error, correlación `asset_id`, lote inválido ⇒ error sin escritura).
  *Historias: ST-M4-03, ST-M4-04.*

- [x] **Step 10 — QueryService (BR-U2-21..24, Q8 FD)**
  Crear `src/sentinel/core/query/service.py`: `list_assets/list_events/list_alerts` con filtros + `limit/offset` (`Page`), `get_asset_detail` con observaciones de todas las fuentes por IP+ventana y eventos recientes.

- [x] **Step 11 — ExportService (BR-U2-28..31, Q7 FD)**
  Crear `src/sentinel/core/export/service.py`: `export(from, to, format)` → CSV con cabecera **exacta** `timestamp,asset_or_pair,method,protocol,condition,rule,threshold,measured_value,result` o JSON `[]`; sin scheduler.

- [x] **Step 12 — HealthService + Discovery trigger (BR-U2-32..37, P2, Q9/Q11 FD)**
  Crear `src/sentinel/core/health/service.py` (uptime, db_connected, last_ingest, heartbeats por sensor, conteos, último run) y `src/sentinel/core/discovery/trigger.py` (`CycleRunner` Protocol, lock único → 409, runner ausente → 503, run_id → 404, `DiscoveryRunRepository`).

- [x] **Step 13 — Unit tests: query + export + health + discovery (`tests/unit/core/`)**
  `test_query.py` (status/ventana/paginación), `test_export.py` (cabecera exacta, format inválido ⇒ 400, vacío), `test_health.py` (heartbeats, sensor caído), `test_discovery_trigger.py` (409 doble trigger, 503 sin runner, 404, 400 scope).

- [x] **Step 14 — API layer (P10/P11, Q7 NFR, BR-U2-01/02/03/24/39/40)**
  Crear `src/sentinel/core/api/`: `schemas.py` (IngestResult, Page, AssetSummary/Detail, EventOut, AlertOut, HealthStatus, DiscoveryRequest/RunStatus), `deps.py` (`require_ingest_token` 401/403 + warning sin token + `compare_digest`; `pagination_params`), `errors.py` (handlers → tabla FD §5, sin traceback), `app.py` (`create_app` + lifespan = startup_checks + shutdown checkpoint), `routes_{ingest,query,export,health,discovery}.py` (rutas de `component-methods.md` §1 **sin** `/report`).
  *Historias: ST-M4-01, ST-M4-07.*

- [x] **Step 15 — API tests con TestClient (TS-U2-04, P8/P9)**
  Crear `tests/unit/core/test_api_*.py` (TestClient + SQLite temporal): 202/400/422 ingest, 401/403 token, idempotencia doble POST, filtros + paginación, export cabecera, health, discovery 409/503/404, 500 sin traceback; `test_query_plans.py` (EXPLAIN ⇒ USING INDEX, P8); `test_latency_baseline.py` (informativo, imprime p95, sin assert, P9).

- [x] **Step 16 — Metrics adapter 9108 (P7, Q10 FD, IP7)**
  Crear `src/sentinel/core/metrics/{collect,server}.py`: `collect()` stub con familias del contrato U1 (`api_requests_total` con contadores reales del proceso, `collector_heartbeat_age_seconds` desde health, resto en cero) + `render_prometheus` de foundation; servidor HTTP 9108 simple. Test: scrape ⇒ familias `sentinel_*` sin extra.
  *Nota IP7: U7 sustituye `collect()` sin tocar router/contrato.*

- [x] **Step 17 — Property tests flow normalization (PB-U2-01..03, EN-02, NFR-U2-MNT-04)**
  Crear `tests/property/test_flow_normalization.py`: (PB-01) `normalize∘normalize == normalize`; (PB-02) distinto formato ⇒ mismo `event_id`; (PB-03) contadores conservados en lote con duplicados. Usa `foundation.testing.generators`.

- [x] **Step 18 — Integration tests (ACs de historias, AVAIL-02, NFR-U2-PERF-02)**
  Crear en `tests/integration/`: `test_persistence_restart.py` (ST-M4-02 AC1), `test_ingest_idempotency.py -k uuid_dedup` (ST-M4-03 AC1), `test_structured_logs.py` (`jsonl_fields`, `source_kind` — ST-M4-05), `test_query_filters.py` (`time_range` — ST-M4-07), `test_export_on_demand.py` (`no_scheduler` — ST-M4-06), `test_correlation.py` (`discovery_and_traffic` — ST-M4-04) + `test_normalization.py` (`mac_canonical`).
  *Nota: `helm template` AC de ST-M4-02 se valida en Build & Test (chart de U9).*

- [x] **Step 19 — Deployment artifacts + entrypoint (ID-U2, Q1 FD)**
  Crear `src/sentinel/core/__main__.py` (`python -m sentinel.core` ⇒ uvicorn 0.0.0.0:8080, app `sentinel.core.api.app:app`, 1 worker); verificar `Dockerfile` heredado de U1 (COPY src incluye core; PYTHONPATH ok) sin modificarlo salvo si hace falta entrypoint comentado. Actualizar `README.md` (sección Core: run, endpoints, `.env.example`, 9108).

- [x] **Step 20 — CI + cobertura (NFR-U2-MNT-02/03, TS-U2-10)**
  Modificar `.github/workflows/ci.yml` job `test`: `pytest tests/unit tests/property tests/integration -q --cov=sentinel --cov-fail-under=70` + mypy sobre `src/sentinel` (gate total ≥70% paquete; foundation aporta 99%). Mantener etapas lint/test/build y `working-directory: sentinel`.

- [x] **Step 21 — Validación local**
  Ejecutar: `ruff check .` · `ruff format --check .` · `mypy src/sentinel` · `pytest tests/unit tests/property tests/integration -q --cov=sentinel --cov-fail-under=70` — todo en verde.

- [x] **Step 22 — Resumen de generación**
  Crear `aidlc-docs/construction/u2-core/code/code-generation-summary.md` (archivos creados/modificados, desviaciones D-* si las hay, cobertura, historias ST-M4-01..07 marcadas `[x]` en el plan, estado del repo).

---

## 3. Historias y trazabilidad

| Historia | Steps | Verificación principal | Estado |
|---|---|---|---|
| ST-M4-01 Ingestion API | 8, 14, 15, 18 | 202 / 400 (curl AC) | [x] |
| ST-M4-02 SQLite PVC + restart | 3, 5, 18 | `test_persistence_restart` (helm AC → Build&Test) | [x] |
| ST-M4-03 Identidad/dedup | 8, 9, 18 | `test_ingest_idempotency -k uuid_dedup` | [x] |
| ST-M4-04 Normalizar/correlacionar | 7, 8, 17, 18 | `test_correlation`, `test_normalization`, PB-01/02 | [x] |
| ST-M4-05 JSON Lines | 6, 18 | `test_structured_logs -k jsonl_fields/source_kind` | [x] |
| ST-M4-06 Export CSV | 11, 15, 18 | cabecera exacta + `no_scheduler` | [x] |
| ST-M4-07 Query API | 10, 14, 15, 18 | filtros + `time_range` + paginación | [x] |

*Estado `[x]` = código + tests generados y en verde en la validación local (Step 21). La verificación formal de los AC (incluido `helm template` de ST-M4-02) se ejecuta en el stage Build and Test.*

---

## 4. Fuera de alcance de este plan

- `/api/v1/report` (U3), cuerpos reales de `collect()` (U7), `CycleRunner` real (U4), escritura de alerts/baselines (U6), chart/values YAML (U9), NetworkPolicy/RBAC (U10), runbook backup (U11), push de imagen (futuro).

---

## 5. Gate de aprobación

1. Revisa los 22 steps y la trazabilidad.
2. Responde **`Aprobado`** (o pide cambios) para iniciar Part 2: Generation.
3. Cada step se marcará `[x]` al completarse; desviaciones se registrarán como `D-*` en el resumen.

**No se genera ningún código hasta esta aprobación.**
