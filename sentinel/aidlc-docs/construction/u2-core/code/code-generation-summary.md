# Code Generation Summary — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — Code Generation (Parte 2: Generation)
**Fecha**: 2026-11-13
**Estado**: GENERATED — validación local en verde (Step 21); pendiente de aprobación
**Plan**: `aidlc-docs/construction/plans/u2-core-code-generation-plan.md` (Steps 1–22 completados)
**Historias**: ST-M4-01..07 (implemented en story map; código + tests generados aquí)

---

## 1. Archivos creados/modificados (greenfield — sin tocar foundation ni raíz `units/`)

### Código de aplicación (`src/sentinel/core/` — 43 archivos `.py`)

| Archivo | Contenido |
|---|---|
| `config.py` | `CoreSettings` con exactamente 4 claves (`db_path`, `ingest_token`, `page_limit=100`, `missing_cycles=3`) + `load_core_settings()` fail-fast → `ConfigError` (BR-U2-41/42, Q13 FD) |
| `errors.py` | `NotFoundError` / `ConflictError` / `RunnerUnavailableError` (mapeo API FD §5) |
| `evidence.py` | `emit()` JSON Lines a stdout con los 9 campos del esquema P10, `kind ∈ {observation,inference,event,alert}` (BR-U2-25..27) |
| `__main__.py` | `python -m sentinel.core` ⇒ uvicorn `0.0.0.0:8080`, app `sentinel.core.api.app:app`, 1 worker (Q1 FD) |
| `db/schema.py` | DDL idempotente OQ-02: 7 tablas (`assets`, `asset_ips`, `observations`, `events`, `alerts`, `baselines`, `discovery_runs`) + índices (BR-U2-18/20) |
| `db/database.py` | `Database`: `read`/`write` (BEGIN/COMMIT + `threading.Lock`, P3), `startup_checks()` = `integrity_check` → DDL → stale `running→failed` (P1/P2), `close()` + `wal_checkpoint(TRUNCATE)` (P4) |
| `db/repos/{_common,assets,observations,events,alerts,baselines,discovery_runs}.py` | SQL parametrizado, `INSERT OR IGNORE` (dedup), filtros + `limit/offset`, upsert por IP; alerts/baselines = esquema + acceso básico (los llena U6) (Q9, BR-U2-06/07/11/21..24/33) |
| `inventory/service.py` | `InventoryService`: `InventoryChange` con `event_id = UUIDv5(content-hash)`, transiciones N=3, cambio de MAC ⇒ `asset_change` (BR-U2-13..17, Q4 FD) |
| `ingestion/dedup.py` | `dedup_key`/`event_id_for` = UUIDv5 sobre sha256 canónico (`OBSERVATION_NAMESPACE`, `EVENT_NAMESPACE`) — idempotencia ST-M4-03 |
| `ingestion/service.py` | `IngestionService.ingest(batch)` ⇒ `IngestResult{ingest_id, accepted, deduplicated, events_persisted}`, **una sola tx**, evidence post-commit, rollback total ante error, `reconcile_missing` solo en lotes con discovery (BR-U2-01..08/11, P6) |
| `query/service.py` | `list_assets/list_events/list_alerts` con filtros + `Page` (`limit` 1..1000 clamp, `offset`), `get_asset_detail`; `_json_obj` parsea columnas TEXT (BR-U2-21..24, Q8 FD) |
| `export/service.py` | `export(from, to, format)` ⇒ CSV con cabecera **exacta** `timestamp,asset_or_pair,method,protocol,condition,rule,threshold,measured_value,result` o JSON `[]`; `ORDER BY occurred_at, event_id` determinista; sin scheduler (BR-U2-28..31, Q7 FD) |
| `health/service.py` | `up/degraded` derivado de DB, heartbeats por sensor, conteos, último run (BR-U2-32..37, P2) |
| `discovery/trigger.py` | `CycleRunner` Protocol (U4 lo implementa), `DiscoveryTrigger.trigger(wait=)` con lock único → 409, runner ausente → 503, timeout → estado `timeout` + `DiscoveryTimeoutError`, `get_status()` para `GET /discovery/{run_id}` (Q9/Q11 FD) |
| `metrics/collect.py` | `ApiRequestCounter` + `collect()` stub con **exactamente** `METRIC_FAMILIES` del contrato U1 (IP7: U7 sustituye `collect()` sin tocar router/contrato) |
| `metrics/server.py` | `MetricsServer` (ThreadingHTTPServer, `METRICS_PORT=9108`, port 0 para tests) |
| `api/schemas.py` | `Page`, `AssetSummary/Detail`, `ObservationOut`, `EventOut`, `AlertOut`, `HealthStatus`, `DiscoveryRequest`, `DiscoveryRunStatus`, `IngestResult` |
| `api/deps.py` | `require_ingest_token`: no configurado → 403 (+warning), distinto → 401, `hmac.compare_digest` (BR-U2-01/02) |
| `api/errors.py` | Handlers: 404/409/503/503/400-scope/400-o-422 validación (`RequestValidationError` ⇒ **400 si todo es `missing`, si no 422**)/500 sin traceback/`HTTPException` (FD §5) |
| `api/app.py` | `create_app(settings, runner=, metrics_port=)` + lifespan (`startup_checks` + metrics + `close`) + middleware `ApiRequestCounter`; instancia de módulo `app` |
| `api/routes_{ingest,query,export,health,discovery}.py` | `POST /api/v1/ingest`, `GET /api/v1/{assets,events,alerts}`, `GET /api/v1/export`, `GET /api/v1/health`, `POST/GET /api/v1/discovery` — **sin** `/report` (U3) |

### Tests — **172 tests** (156 unit + 8 property + 8 integration)

| Archivo | Tests | Cubre |
|---|---|---|
| `tests/unit/core/test_config.py` · `test_database.py` · `test_repos.py` | Steps 5 | 4 claves, WAL/integrity/stale, SQL repos |
| `tests/unit/core/test_inventory.py` · `test_ingestion.py` | Step 9 | N=3, UUIDs estables, MAC mayúsculas ⇒ mismo `event_id`, rollback total |
| `tests/unit/core/test_query.py` · `test_export.py` · `test_health.py` · `test_discovery.py` | Step 13 | paginación/filtros, cabecera exacta, heartbeats, 409/503/404 |
| `tests/unit/core/test_api_{ingest,query,export,health,discovery}.py` | Step 15 | 202/400/422/401/403/404/409/500 (sin traceback), idempotencia doble POST |
| `tests/unit/core/test_query_plans.py` | Step 15 | `EXPLAIN` ⇒ `USING INDEX` (P8) |
| `tests/unit/core/test_latency_baseline.py` | Step 15 | p50/p95 informativo sin assert (P9) — ej.: `/events` p95≈50 ms |
| `tests/unit/core/test_metrics.py` | Step 16 | scrape ⇒ familias `sentinel_*` sin labels extra |
| `tests/property/test_flow_normalization.py` | Step 17 | PB-U2-01 `normalize∘normalize`, PB-U2-02 mismo `event_id` entre formatos, PB-U2-03 contadores con duplicados |
| `tests/integration/test_persistence_restart.py` | Step 18 | ST-M4-02 AC1: reinicio ⇒ datos íntegros (WAL + startup_checks) |
| `tests/integration/test_ingest_idempotency.py` | Step 18 | `-k uuid_dedup` ST-M4-03 AC1 |
| `tests/integration/test_structured_logs.py` | Step 18 | `-k jsonl_fields/source_kind` ST-M4-05 |
| `tests/integration/test_query_filters.py` | Step 18 | `-k time_range` ST-M4-07 |
| `tests/integration/test_export_on_demand.py` | Step 18 | `-k no_scheduler` ST-M4-06 |
| `tests/unit/test_correlation.py` · `test_normalization.py` | Step 18 | `-k discovery_and_traffic` (ST-M4-04), `-k mac_canonical` — **ver D-2** |
| `tests/unit/core/conftest.py` | Step 15 | fixtures `settings`/`app(metrics_port=None)`/`client`/`auth`/`sample_batch` |
| `tests/fixtures/observations.json` | Step 18 | lote de ejemplo para los AC curl |

### Artefactos y documentación

| Archivo | Contenido |
|---|---|
| `.env.example` | `SENTINEL_DB_PATH`, `SENTINEL_INGEST_TOKEN`, `SENTINEL_PAGE_LIMIT`, `SENTINEL_MISSING_CYCLES` |
| `requirements.txt` | + `fastapi==0.162.5`, `uvicorn==0.54.0`, `httpx==0.28.1` (pin exacto) |
| `README.md` | Sección Core: run (`python -m sentinel.core` / `uvicorn`), tabla de endpoints, `.env.example`, 9108, comandos de calidad con `--cov=sentinel` |
| `.github/workflows/ci.yml` *(raíz del repo)* | **Modificado (Step 20)**: job `test` ⇒ `pytest -q --maxfail=1 tests/unit tests/property tests/integration --cov=sentinel --cov-fail-under=70 --cov-report=term-missing` + `mypy src/sentinel`; etapas lint/test/build y `working-directory: sentinel` intactas |
| `fixtures` (symlink) | `fixtures → tests/fixtures` en la raíz del workspace para el AC curl de ST-M4-01 — **ver D-8** |

**No se modificó**: `src/sentinel/foundation/`, `Dockerfile`, `pyproject.toml` (excepto `mypy files` y `per-file-ignores`, ver D-4), raíz `units/`, `specs/`, `MANIFEST.sha256`, scripts de verificación.

---

## 2. Desviaciones / decisiones de implementación

| # | Desviación | Justificación |
|---|---|---|
| D-1 | `observations.asset_id` **nullable** | Ventanas de tráfico sin par/asset (sin correlación aún) deben persistirse igual (BR-U2-04/05); el link se completa al correlacionar. Esquema OQ-02 interpretado con FK opcional. |
| D-2 | `test_correlation.py` y `test_normalization.py` en **`tests/unit/`**, no `tests/integration/` (texto del Step 18) | Los AC de verificación de ST-M4-04 los invocan como `pytest tests/unit/test_correlation.py -k discovery_and_traffic` y `pytest tests/unit/test_normalization.py -k mac_canonical` (`stories.md` L303/305). La fuente de verdad para Build & Test es el AC de la historia. |
| D-3 | `GET /export`: `from`/`to` **opcionales** con defaults de rango completo | El AC curl de ST-M4-06 no pasa parámetros; sin defaults devolvería 400 y el AC fallaría. BR-U2-28..30 intactos (rango explícito sigue funcionando). |
| D-4 | `ruff.lint.per-file-ignores` `B008` para `src/sentinel/core/api/*.py` | `Depends()` en defaults de parámetro es el patrón oficial de FastAPI; B008 no aplica a la capa de rutas. Reglas `select` originales sin tocar. |
| D-5 | `MetricsServer` bindea en `start()` (lifespan), no en `create_app()`/import | El `app` de módulo no ocupa el 9108 hasta que el proceso sirve: evita `OSError: Address already in use` en la suite (varios tests crean apps en el mismo proceso) y hace seguro importar el módulo. |
| D-6 | Excepción renombrada `DiscoveryTimeout` → `DiscoveryTimeoutError` | Regla ruff `N818` (sufijo `Error`). Control interno del trigger; el estado expuesto en la API sigue siendo `timeout`. |
| D-7 | `core.evidence.emit()` emite **siempre** los 9 campos del esquema P10 (los no aplicables en `null`) | BR-U2-25 exige el esquema completo en cada línea; campos dinámicos por tipo dejarían fuera `severity`/`threshold` etc. en evidencias de inventory/event. |
| D-8 | Symlink `fixtures → tests/fixtures` en la raíz del workspace | El AC curl de ST-M4-01 usa `-d @fixtures/observations.json` relativo a `sentinel/`. Symlink de conveniencia; el JSON fuente vive en `tests/fixtures/`. |

---

## 3. Verificación (Step 21 — ejecutada en local, 2026-11-13)

| Comando | Resultado |
|---|---|
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 102 files already formatted |
| `mypy src/sentinel` | ✅ Success: no issues found in 53 source files |
| `pytest tests/unit tests/property tests/integration -q --cov=sentinel --cov-fail-under=70 --cov-report=term-missing` | ✅ **172 passed**, **coverage 95.59%** (gate 70%); core 94.5%, foundation 99.7% |
| `docker build -t sentinel:test .` | ✅ Successfully built (hereda `Dockerfile` de U1, `CMD python -m sentinel.core` sin cambios) |
| Smoke en contenedor | ✅ `GET /api/v1/health` 200 · `GET :9108/metrics` 200 · `POST /api/v1/ingest` sin token 401 / con token 202 · JSONL `{"kind": "observation"…}` en logs · shutdown limpio |
| Entrypoint local (`python -m sentinel.core`, timeout 8 s) | ✅ arranca, health 200, métricas 200, ingest 401 sin auth, SIGTERM sin errores |

Notas de cobertura: `db/repos/baselines.py` 0% (esquema + acceso básico; lo llena U6, previsto en el plan) y `__main__.py` 0% (smoke manual/contenedor, no unit-testeable sin arrancar uvicorn).

La ejecución formal completa (Build and Test stage) es la etapa posterior; aquí se verificó que lo generado es correcto.

---

## 4. Estado del repositorio (⚠️ hallazgo sin resolver — requiere decisión del usuario)

- **Mismo hallazgo que U1**: `sentinel/` no tiene `.git`; el repo padre `TAI_Proyecto` lo referencia como gitlink roto. Nada bajo `sentinel/` está bajo control de versiones.
- `.github/workflows/ci.yml` (raíz del repo padre) fue modificado en Step 20 y **tampoco está commiteado**.
- **No se hizo ningún commit** (regla: solo cuando el usuario lo pida). Opciones pendientes del resumen de U1: (a) repo propio para `sentinel/`, (b) absorberlo al repo padre, (c) restaurar submódulo con `.gitmodules`.

---

## 5. Trazabilidad final

| Historia | Steps del plan | Evidencia |
|---|---|---|
| ST-M4-01 Ingestion API | 8, 14, 15, 18 | `POST /api/v1/ingest` 202/400/422/401/403; curl AC con `fixtures/observations.json` |
| ST-M4-02 SQLite PVC + restart | 3, 5, 18 | `test_persistence_restart` (AC `helm template` → Build & Test con chart de U9) |
| ST-M4-03 Identidad/dedup | 8, 9, 18 | `test_ingest_idempotency -k uuid_dedup`; UUIDv5 content-hash |
| ST-M4-04 Normalizar/correlacionar | 7, 8, 17, 18 | `test_correlation -k discovery_and_traffic`, `test_normalization -k mac_canonical`, PB-U2-01/02/03 |
| ST-M4-05 JSON Lines | 6, 18 | `test_structured_logs -k jsonl_fields/source_kind`; `emit()` 9 campos |
| ST-M4-06 Export CSV | 11, 15, 18 | cabecera exacta + `test_export_on_demand -k no_scheduler` |
| ST-M4-07 Query API | 10, 14, 15, 18 | `test_query_filters -k time_range`, paginación, `EXPLAIN` con índice |

Sin desviaciones de contenido contra los artefactos aprobados de U2 (FD, NFR Req/Design, Infra Design) más allá de D-1..D-8, todas de implementación y documentadas.

---

## 6. Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
