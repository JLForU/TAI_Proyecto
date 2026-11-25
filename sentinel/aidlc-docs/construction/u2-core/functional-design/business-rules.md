# Business Rules & Validation — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U2 — `src/sentinel/core/`
**Traza**: ST-M4-01..07, FR-CORE-01..05, FR-EXP-01..03, OQ-02; plan Q1–Q13 = A; `requirements.md` §5 (PBT: flow normalization).

---

## 1. Ingesta y autenticación (ST-M4-01)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-01 | `POST /api/v1/ingest` con lote válido ⇒ **202** + `IngestResult` con contadores | ST-M4-01 AC1, FR-CORE-01 | `curl ... -d @fixtures/observations.json` ⇒ 202 |
| BR-U2-02 | Lote con campo obligatorio faltante ⇒ **400** con el campo inválido; sin persistencia parcial | ST-M4-01 AC2, services.md §4 | `curl ... -d '{}'` ⇒ 400 |
| BR-U2-03 | Ingesta protegida por Bearer `SENTINEL_INGEST_TOKEN`; sin/incorrecto ⇒ **401**; token no configurado en proceso ⇒ **403** | Q2=A, IP2 | test: requests sin/ con token |
| BR-U2-04 | Tamaño de lote ≤ `MAX_BATCH_ITEMS` (1000, U1); excede ⇒ 400 | U1 Batch | test de lote 1001 |
| BR-U2-05 | Transacción única por lote: error de DB ⇒ **503** y rollback total (nada persistido a medias) | business-logic §3.1 | test con DB forzada a fallar |

## 2. Identidad y deduplicación (ST-M4-03, FR-CORE-04)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-06 | `event_id` = `UUIDv5(NAMESPACE_FIJO, sha256(contenido_normalizado))`; PK/UNIQUE; **36 hex+guiones** | FR-CORE-04, Q3=A | `jq test("^[0-9a-f-]{36}$")` ⇒ 0 |
| BR-U2-07 | Mismo lote dos veces ⇒ el nº de eventos/observaciones **no cambia** en la segunda ingesta (`INSERT OR IGNORE`) | ST-M4-03 AC1 | `pytest tests/.../test_ingest_idempotency.py -k uuid_dedup` |
| BR-U2-08 | El hash se calcula **después** de normalizar (MAC/IP/timestamps canónicos): reenvíos con distinto formato ⇒ mismos UUIDs | Q3=A, business-logic §4 | test: mismo evento con MAC en mayúsculas ⇒ mismo `event_id` |
| BR-U2-09 | Namespace UUIDv5 es constante de código; no configurable | Q3=A | revisión de código |

## 3. Normalización y correlación (ST-M4-04, FR-CORE-05)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-10 | MAC canónica minúsculas `^([0-9a-f]{2}:){5}[0-9a-f]{2}$` en todas las fuentes; IP tipada; timestamps UTC tz-aware | ST-M4-04 AC2, U1 models | `pytest tests/.../test_normalization.py -k mac_canonical` |
| BR-U2-11 | Toda observación persiste `asset_id` resuelto por IP (upsert de `Asset`); es la **columna de correlación** | Q5=A | test: observación nueva ⇒ fila `asset_ips` + `assets` |
| BR-U2-12 | Al consultar el activo, descubrimiento y tráfico del mismo host aparecen unidos por IP + ventana | ST-M4-04 AC1 | `pytest tests/.../test_correlation.py -k discovery_and_traffic` |

## 4. Reconciliación de inventario (ST-M4-04)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-13 | IP vista por primera vez ⇒ `status=present`, `first_seen`, evento `asset_first_seen` | services.md §2.3 | test de lote nuevo |
| BR-U2-14 | Ausencia solo tras `SENTINEL_MISSING_CYCLES` (default **3**) ciclos `completed` sin observación; transición ⇒ `status=absent` + evento `asset_missing` (una vez) | Q4=A, ST-M4-04 | test: 2 completed sin ver ⇒ sigue present; 3º ⇒ absent |
| BR-U2-15 | Ciclos `partial`/`timeout`/`failed` **no** incrementan el contador de ausencia | services.md §2.2 | test con ciclo timeout |
| BR-U2-16 | `last_seen` se actualiza en cada observación; al rever el activo ⇒ `present` y `miss_count=0` | Q4=A | test de reaparición |
| BR-U2-17 | Cambio de IP↔MAC en activo conocido ⇒ evento `arp_mapping_changed` + UPDATE de `mac` | ST-M4-04, PRD M4 | test: misma IP, otra MAC |

## 5. Persistencia y recuperación (ST-M4-02, FR-CORE-03)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-18 | SQLite en modo **WAL**; Core = **único escritor**; conexión/transaction por request | Q1=A, services.md §3 | test concurrente de solo-escritor |
| BR-U2-19 | Tras reinicio del proceso con el mismo `SENTINEL_DB_PATH`, todo lo persistido sigue consultable | ST-M4-02 AC1, NFR-AVAIL-02 | `pytest tests/integration/test_persistence_restart.py` |
| BR-U2-20 | DDL idempotente al arrancar (CREATE TABLE IF NOT EXISTS + índices); esquema exacto en `domain-entities.md` (cierra **OQ-02**) | OQ-02 | test de arranque doble |

## 6. Consulta paginada (ST-M4-07)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-21 | `GET /assets?status=missing` devuelve **solo** activos en ese estado; mismos filtros para `from`/`to` en events/alerts | ST-M4-07 AC | `curl .../assets?status=missing \| jq ...` ⇒ vacío |
| BR-U2-22 | Consulta por rango temporal devuelve **solo** eventos dentro del rango (inclusivo) | ST-M4-07 AC2 | `pytest tests/.../test_query_filters.py -k time_range` |
| BR-U2-23 | Paginación `limit` (default `SENTINEL_PAGE_LIMIT`=100, máx 1000) + `offset`; respuesta `{items, total, limit, offset}` | Q8=A | test: página de 2 con limit=2 |
| BR-U2-24 | Recurso inexistente (`asset_id`, `run_id`) ⇒ **404** | Q12=A | test curl id inexistente |

## 7. Evidencia JSON Lines (ST-M4-05, FR-EXP-01)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-25 | Cada evento se emite como **una línea JSON válida** a stdout con: hora, activo/par, método, protocolo, condición, regla, umbral, valor medido, resultado | ST-M4-05 AC1, FR-EXP-01 | `pytest tests/.../test_structured_logs.py -k jsonl_fields` |
| BR-U2-26 | Campo `kind ∈ {observation, inference, event, alert}` distingue el tipo de línea | ST-M4-05 AC2, Q6=A | `pytest ... -k source_kind` |
| BR-U2-27 | Evidencia por `foundation.get_logger` (JSON por línea, ISO 8601 UTC) — reutiliza BR-09..12 de U1 | Q6=A | test de parseo de stdout |

## 8. Export bajo demanda (ST-M4-06, FR-EXP-02/03)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-28 | `GET /export?format=csv` ⇒ CSV con cabecera **exacta** `timestamp,asset_or_pair,method,protocol,condition,rule,threshold,measured_value,result` | ST-M4-06 AC1 | `curl ... \| head -1 \| grep -c ...` ⇒ 1 |
| BR-U2-29 | `format=csv\|json` + filtros `from`/`to`; `format` desconocido ⇒ 400 | Q7=A, FR-EXP-02 | test de parámetro inválido |
| BR-U2-30 | Export **solo bajo demanda**: sin scheduler, timer ni push periódico | FR-EXP-03, ST-M4-06 AC2 | `pytest tests/.../test_export_on_demand.py -k no_scheduler` |
| BR-U2-31 | Sin eventos en el rango ⇒ CSV con solo cabecera / JSON `[]` (sin inventar filas) | services.md §4 | test con DB vacía |

## 9. Discovery trigger (frontera U2↔U4, Q9=A)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-32 | Un solo ciclo manual a la vez: lock adquirido ⇒ `202 DiscoveryRun`; ya en curso ⇒ **409** | services.md §2.2, component-methods | test de doble POST simultáneo |
| BR-U2-33 | `GET /discovery/{run_id}` ⇒ `running\|completed\|timeout\|failed`; inexistente ⇒ 404 | component-methods | test curl |
| BR-U2-34 | `CycleRunner` inyectado (U4); sin runner ⇒ **503** "discovery runner not available" | Q9=A | test sin inyectar runner |
| BR-U2-35 | Host fuera de alcance en trigger ⇒ **400** `scope_violation` (la ejecución no arranca) | services.md §4 | test con scope inválido |

## 10. Salud y métricas (Q10=A, Q11=B)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-36 | `/health` deriva **solo de DB**: uptime, conectividad, último ingest global, último por `sensor_id`, conteos, último ciclo; sin API de K8s | Q11=B, FR-GUI-05 | test con DB simulada |
| BR-U2-37 | Sin observación reciente de un `sensor_id` ⇒ el health lo reporta como caído (no "red sin activos") | GT-05, services.md §2.6 | test de heartbeat |
| BR-U2-38 | Servidor `/metrics` en **9108** con **todas** las familias del contrato U1 en cero/stub; U7 reemplaza `collect()` sin cambiar familias/rutas | Q10=A, FR-CORE-02, IP7 | test: scrape devuelve familias `sentinel_*` |

## 11. Errores HTTP (Q12=A, BR-24 de U1)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-39 | Tabla de mapeo completa (business-logic §5): 401/403/400/404/409/422/503/500 según el tipo de error | Q12=A | test por cada fila de la tabla |
| BR-U2-40 | Error no previsto ⇒ 500 genérico; el stacktrace **solo** en log, jamás en la respuesta | Q12=A, security | test: excepción ⇒ cuerpo sin traceback |

## 12. Configuración (Q13=A, BR-06 de U1)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U2-41 | `core.config` define exactamente: `SENTINEL_DB_PATH`, `SENTINEL_INGEST_TOKEN`, `SENTINEL_PAGE_LIMIT`, `SENTINEL_MISSING_CYCLES` (fail-fast en inválidas) | Q13=A | test: campos de `CoreSettings` |
| BR-U2-42 | No se añaden claves `scope.*`/`discovery.*`/`traffic.*`/`gui.*` en U2 (BR-06 sigue vigente) | BR-06 U1 | revisión de config |

## 13. Property-Based Testing designado (EN-02 parcial — flow normalization)

| ID | Propiedad | Generadores | Verificación |
|---|---|---|---|
| PB-U2-01 | `normalize(normalize(x)) == normalize(x)` (idempotente) | MAC/IP/timestamps arbitrarios | hypothesis |
| PB-U2-02 | Normalizar no cambia la identidad lógica: mismo contenido en distinto formato ⇒ **mismo** `event_id` | pares (formato_a, formato_b) del mismo hecho | hypothesis |
| PB-U2-03 | Cualquier lote ⇒ `len(INSERT OR IGNORE aplicados) + duplicados == len(lotes)` (conserva contadores) | lotes aleatorios con duplicados | hypothesis |

## 14. Anti-requisitos de la unidad

- No escribe en activos monitorizados; no sondea; no evalúa condiciones (U6); no renderiza GUI (U3); no crea el reporte (U3).
- No hay push programado de export; no hay autenticación de operador en la demo (port-forward); no hay cola/bus de eventos (services.md §5).
