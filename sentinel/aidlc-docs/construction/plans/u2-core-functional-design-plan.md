# Functional Design Plan — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — Functional Design (Parte 1: Planning)
**Fecha**: 2026-11-11
**Estado**: ARTIFACTS_GENERATED — respuestas todas A; artefactos generados; pendiente de aprobación
**Unidad**: U2 — `src/sentinel/core/` (api/, ingestion/, inventory/, export/, db/)
**Entradas**: `unit-of-work.md` (§U2), `unit-of-work-story-map.md` (ST-M4-01..07), `stories.md` (ST-M4-01..07 + AC), `requirements.md` (FR-CORE-01..05, FR-EXP-01..03, OQ-02, §4 constraints), `component-methods.md` (§1 API, §2–3, §9 repos), `services.md` (§2 flujos, §4 errores), `components.md` (C1–C4, C11), `implementation-scope.md` §2, contratos de U1 aprobados.

---

## 1. Contexto de la unidad (Step 1 — analizado)

- **Responsabilidad**: API REST/JSON interna `/api/v1`, ingesta/normalización/deduplicación de observaciones, inventario y eventos (reconciliación), SQLite sobre PVC con recuperación, identidad estable de eventos, logs JSON Lines de evidencia, export CSV/JSON bajo demanda, endpoint `/metrics` en 9108 (junto con U7), salud del Core.
- **Historias**: ST-M4-01..07 (todas implemented).
- **Frontera**: Core = único escritor de SQLite; colectores solo envían lotes por HTTP (IP2 con token de Secret); no sondea (U4), no captura (U5), no evalúa condiciones (U6), no expone GUI (U3), no escribe en activos monitorizados.
- **Depende de**: U1 (modelos, errores, logging, retry, contrato de métricas) — ya aprobado y generado.
- **Stack ya fijado por requisitos** (NO se pregunta): Python 3.11, **FastAPI** + uvicorn (NFR-TECH-02/04), **SQLite 3** en PVC (Q7=A), HTTP/JSON (Q8=B), services síncronos + single writer, jerarquía `SentinelError` de U1 (BR-24: la traducción a HTTP la hace U2).
- **Open question que esta etapa cierra**: OQ-02 — esquema SQLite exacto de events/assets/alerts/baselines (`requirements.md` §8).
- **PBT designado (EN-02)**: *flow normalization* — propiedades de normalización/dedup en U2 (`requirements.md` §5).
- **Categoría Frontend**: **no aplica** a U2 (sin UI) — sin preguntas de componentes.

---

## 2. Checklist del plan

- [x] Analizar unidad, historias y restricciones
- [x] Generar preguntas de diseño funcional (Q1–Q13)
- [x] Recoger respuestas a los `[Answer]:` (todas A, 2026-11-11)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; sin ambigüedades; sin seguimientos
- [x] Generar `business-logic-model.md`, `business-rules.md`, `domain-entities.md` en `construction/u2-core/functional-design/`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño funcional

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas.

### Question 1 — Capa de acceso a SQLite (Data Flow / Persistence)

A) stdlib `sqlite3` + repositorios SQL a mano (síncronos, WAL, conexión por request/transaction; cero dependencias extra, control total, escala de laboratorio) *(recomendado)*

B) SQLAlchemy 2.0 (Core) + Alembic para migraciones de esquema

C) `sqlite3` sin WAL (journal por defecto) y sin capa de repositorios (SQL en los servicios)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Autenticación de la ingesta (Integration Points / Security)

Contexto: IP2 (U4/U5 → U2) dice "token de Secret"; la demo no tiene auth de operador (port-forward).

A) Bearer token en `POST /api/v1/ingest` (env `SENTINEL_INGEST_TOKEN`, inyectado desde Secret por U9); endpoints de consulta sin auth (acceso solo port-forward) *(recomendado)*

B) Sin token en ingesta; aislamiento solo por NetworkPolicy (U10)

C) Token Bearer en **todos** los endpoints `/api/v1` (consulta incluida)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Identidad de evento y deduplicación (Business Rules / ST-M4-03)

Contexto: FR-CORE-04 (UUID estable por evento) + AC "mismo lote dos veces ⇒ nº de eventos sin cambio".

A) `event_id = UUIDv5(namespace fijo, hash del contenido normalizado)` calculado en la ingesta; UNIQUE + `INSERT OR IGNORE` en eventos **y** observaciones (lote reenviado ⇒ mismos hashes ⇒ idempotencia total, incluye re-normalización de MAC/IP/timestamps antes de hashear) *(recomendado)*

B) `event_id` UUIDv4 aleatorio + índice único sobre clave natural (type, asset_id, occurred_at, hash de details); el reenvío choca por la clave natural

C) Dedup solo a nivel de lote (`ingest_id`/hash del batch completo); los eventos individuales pueden duplicarse si el lote cambia levemente

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Reconciliación de inventario (Business Rules / ST-M4-04)

Contexto: AC "Asset missing after N successful cycles"; GT-03 exige grace period **configurable**; services.md: ausencias solo si el ciclo es `completed`; eventos `asset_first_seen`, `asset_missing`, `arp_mapping_changed`.

A) N configurable (`SENTINEL_MISSING_CYCLES`), **default 3** ciclos `completed` consecutivos sin ver el activo; `last_seen` se actualiza en cada observación; eventos: first_seen, missing, arp_mapping_changed *(recomendado)*

B) N configurable, **default 1** (ausente en el siguiente ciclo completed)

C) N configurable, **default 5**; además umbral de tiempo (grace period por horas) en vez de conteo de ciclos

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Correlación de observaciones con activos (Data Flow / ST-M4-04)

Contexto: AC "observaciones discovery + tráfico del mismo host aparecen correlacionadas por IP y ventana".

A) Correlación por IP al ingest: cada observación guarda `asset_id` (resuelto/upsert de `Asset` por IP observada); consultar el activo devuelve todas sus fuentes unidas por IP + ventana temporal *(recomendado)*

B) Tabla explícita `observation_links(observation_id, asset_id, linked_at)` mantenida por InventoryService

C) Sin columna en observaciones: join dinámico por IP en cada query

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Destino de los logs JSON Lines de evidencia (Data Flow / ST-M4-05)

Contexto: FR-EXP-01 "JSON Lines for real-time event logs"; AC: cada línea JSON con hora, activo/par, método, protocolo, condición, regla, umbral, valor medido, resultado, y campo tipo que distinga observación/inferencia/evento/alerta.

A) Emitir por `foundation.logging` a **stdout** (una línea JSON por evento, campos de evidencia como extras + `kind ∈ {observation, inference, event, alert}`; K8s captura stdout, un solo stream) *(recomendado)*

B) Archivo `evidence.jsonl` aparte montado en el PVC (stdout solo con logs de aplicación)

C) Ambos: stdout **y** archivo en PVC

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Export bajo demanda (Business Rules / ST-M4-06)

Contexto: AC CSV con cabecera fija `timestamp,asset_or_pair,method,protocol,condition,rule,threshold,measured_value,result`; component-methods lista `format=csv|json` con `from`/`to`; FR-EXP-03: sin push periódico.

A) `format=csv|json` + filtros `from`/`to`; respuesta en memoria (escala lab); cabecera CSV exacta del AC; sin scheduler *(recomendado)*

B) Solo `format=csv` (el JSON queda documentado como futuro)

C) `csv|json` + filtros `from`/`to`/`asset_id`/`status`

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Paginación de la API de consulta (Business Rules / ST-M4-07)

Contexto: component-methods devuelve `Page[...]` en assets/events/alerts.

A) `limit` (default 100, máx 1000) + `offset`; respuesta `{items, total, limit, offset}` *(recomendado)*

B) Cursor (`?after_id=` + `has_more`)

C) Sin paginación: devolver todo el resultado de una vez (escala lab)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 9 — Endpoints de disparo de discovery (Integration Points / frontera U2↔U4)

Contexto: `POST /api/v1/discovery` + `GET /api/v1/discovery/{run_id}` viven en la API Layer (C2, U2), pero `run_cycle` necesita el módulo de U4; ST-M10-04 (disparo desde GUI) es historia de U3; services.md exige lock único + 409.

A) U2 implementa rutas + `DiscoveryRunRepository` + lock de ejecución única e inyecta una interfaz `CycleRunner` (la implementa U4); hasta que U4 llegue, el runner no inyectado ⇒ `503` *(recomendado)*

B) U4 registra sus propias rutas en la app FastAPI del Core (U2 solo aporta repo/lock)

C) U2 implementa el trigger completo invocando nmap directamente (mezcla las fronteras U2/U4)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 10 — Endpoint `/metrics` en U2 (Integration Points / "junto con U7")

Contexto: unit-of-work U2 incluye `/metrics` en 9108 junto con U7; U7 (MetricsExporter C6) implementa `collect()`; contrato de familias vive en U1.

A) U2 crea el servidor en 9108 y renderiza las familias del contrato U1 con colectores en cero/stub; U7 implementa los cuerpos de `collect()` (mismo formato, sin cambiar rutas) *(recomendado)*

B) U2 crea el endpoint devolviendo texto vacío; U7 lo reemplaza por completo

C) U7 crea también el servidor (U2 no toca 9108)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 11 — Contenido de `GET /api/v1/health` (Business Logic)

Contexto: HealthService consolida "estado Core, último ciclo exitoso, heartbeat de colectores"; lectura de K8s es U9/U10; GT-05 necesita detectar sensor caído.

A) Solo estado del Core derivado de DB: uptime, conectividad DB, último ingest, conteo de assets/events, último ciclo registrado *(recomendado)*

B) A + heartbeat por colectores: última observación por `sensor_id` (para "sensor caído" sin K8s)

C) B + campos placeholder de estado K8s (rellenados en U9/U10)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 12 — Mapeo de errores a HTTP (Error Handling / BR-24)

Contexto: services.md §4 y component-methods §1 definen códigos (400/404/409/422/503); U2 traduce la jerarquía `SentinelError` de U1.

A) Tabla completa: `ScopeError`→400+code, payload Pydantic inválido→422, `ValidationError` de dominio→400, `IngestionError`/`StorageError`→503, recurso inexistente→404, lock ocupado→409, error no previsto→500 (logueado, sin filtrar stacktrace) *(recomendado)*

B) Mínimo: 400/422/503 solamente (404/409/500 con respuestas genéricas de FastAPI)

C) Sin mapeo propio: dejar los defaults de FastAPI

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 13 — Claves de configuración de U2 (Business Rules / config)

Contexto: BR-06 (foundation solo claves comunes); cada unidad define su loader reutilizando el patrón de `load_settings`.

A) Loader propio `core.config` con: `SENTINEL_DB_PATH` (default `/data/sentinel.db`), `SENTINEL_INGEST_TOKEN`, `SENTINEL_PAGE_LIMIT` (100), `SENTINEL_MISSING_CYCLES` (3) *(recomendado)*

B) Solo `SENTINEL_DB_PATH` y `SENTINEL_INGEST_TOKEN`; límite de página y N con constantes en código

C) Un solo esquema de config unificado para todas las unidades definido en U2

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Artefactos obligatorios (tras aprobación de respuestas)

| Artefacto | Contenido |
|---|---|
| `construction/u2-core/functional-design/business-logic-model.md` | Flujos de ingesta/dedup/normalización, reconciliación, consulta/export, salud, métricas stub, discovery trigger, manejo de errores |
| `construction/u2-core/functional-design/business-rules.md` | Reglas ST-M4-01..07 + FR-CORE/EXP con verificación (idempotencia, single writer, JSONL, cabecera CSV, paginación, códigos HTTP) |
| `construction/u2-core/functional-design/domain-entities.md` | Esquema SQLite definitivo e índices (cierra OQ-02): assets, observations, events, alerts, baselines, discovery_runs + entidades de respuesta API |

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los artefactos de Functional Design y presentaré el mensaje de completitud.

**No se genera ningún artefacto de Functional Design hasta completar este gate.**
