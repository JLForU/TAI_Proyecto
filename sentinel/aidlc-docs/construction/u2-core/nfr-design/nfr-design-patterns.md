# NFR Design Patterns — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — NFR Design (Parte 2: Generation)
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U2 — `src/sentinel/core/`
**Decisiones (plan Q1–Q10)**: **A en todas** — integrity_check al arrancar; stale runs → failed; write-lock con espera natural; métricas solo con familias U1; EXPLAIN QUERY PLAN; warning de auth sin token; dependencias FastAPI + routers; `Database` con context manager; layering router→servicio→repo; adaptador `core.metrics` sobre el contrato U1.
**Entradas**: `nfr-requirements/*` (NFR-U2-*), Functional Design de U2, `foundation` (retry, logging, metrics_contract, errors).

---

## 1. Patrones de Resilience

### P1 — Integrity check en el arranque (→ NFR-U2-AVAIL-01/02, Q1=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | En el lifespan de arranque: `PRAGMA integrity_check` sobre `SENTINEL_DB_PATH`; `ok` ⇒ sigue; distinto ⇒ log JSON `event="db_integrity_failed"` + **exit 1 sin modificar el archivo** |
| Dónde | `core/db/database.py` → `Database.startup_checks()` invocado por el lifespan |
| Recuperación | K8s reinicia el Pod; el admin restaura desde snapshot según runbook (NFR-U2-AVAIL-01). El archivo corrupto queda intacto para diagnóstico |
| No hace | **Nunca** recrea ni renombra la DB automáticamente (la evidencia no se pierde en silencio) |
| Verificación | Test: archivo truncado/corrupto ⇒ arranque falla con exit 1 y el archivo byte a byte intacto |

### P2 — Recuperación de runs stale (→ Resilience, Q2=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Tras el integrity check: `UPDATE discovery_runs SET status='failed', error='core restarted', finished_at=now WHERE status='running'`; lock de proceso queda libre |
| Dónde | `Database.startup_checks()` (misma fase de arranque) |
| Verificación | Test: insertar run `running`, reiniciar app ⇒ run en `failed` con `error='core restarted'`; `POST /discovery` vuelve a aceptar (409 no aplica) |

### P3 — Write-lock bloqueante simple (→ NFR-U2-REL-01, Q3=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Un solo `threading.Lock` en `Database`; **cada transacción de escritura** lo adquiere con espera bloqueante (sin timeout); lecturas sin lock (WAL) |
| Por qué sin timeout | Contención en lab ≤10 lotes/min + threadpool acota la cola; un timeout rechazaría lotes válidos sin ganar nada medible |
| No hace | No prioriza, no mide espera, no degrada: la cola natural del threadpool es la política |
| Verificación | Test de concurrencia: N hilos insertando ⇒ 0 `database is locked`, todos los inserts presentes |

### P4 — Apagado ordenado (→ NFR-U2-REL-02)

| Elemento | Diseño |
|---|---|
| Mecanismo | Lifespan shutdown: `PRAGMA wal_checkpoint(TRUNCATE)` + `close()` de la conexión activa + logs finales; uvicorn gestiona SIGTERM |
| Verificación | Test: enviar SIGTERM al proceso ⇒ exit 0; reabrir la DB ⇒ datos íntegros y sin WAL residual huérfano |

### P5 — Fast-fail 503 single-owner (→ NFR-U2-REL-03)

| Elemento | Diseño |
|---|---|
| Mecanismo | Fallo de DB durante ingesta ⇒ rollback + `StorageError` ⇒ respuesta **503 inmediata** (sin retry interno); los reintentos con backoff viven en U4/U5 con `foundation.retry` |
| Analogía | Semántica de "circuit" ligero: el Core no enmascara su propio fallo; el dueño del reintento es quien puede reintentar sin duplicar efectos |
| Verificación | Test: DB cerrada a mitad de request ⇒ 503 en <200 ms, cero reintentos internos (contar intentos de escritura) |

### P6 — Transacción única por lote (→ NFR-U2-REL-04)

| Elemento | Diseño |
|---|---|
| Mecanismo | Un `BEGIN…COMMIT` por lote: observaciones + assets + eventos + inventario en la misma transacción; cualquier excepción ⇒ `ROLLBACK` total |
| No hace | No hay modo "mejor esfuerzo" parcial: o todo el lote o nada (FD BR-U2-05) |
| Verificación | Test: forzar error en la 3ª de 5 escrituras ⇒ la tabla queda como antes del request |

---

## 2. Patrón de Scalability

### P7 — Capacidad observable con contrato intacto (→ NFR-U2-SCAL-01, Q4=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Stub de `/metrics` cuenta de verdad `sentinel_api_requests_total` (labels `component`, `state` del catálogo U1) y proyecta `sentinel_collector_heartbeat_age_seconds` desde el mismo dato que `/health`; el resto de familias en cero |
| Por qué sin familias nuevas | El contrato U1 queda aprobado e inmutable (FD Q10=A); crecimiento se observa vía health (`counts`, `db` conectado) y familia `api_requests_total` |
| Umbral de revisión | Si la demo supera el envolvente PERF-01 → checklist U11 (SCAL-01), no código nuevo ahora |
| Verificación | Test: scrape del 9108 ⇒ `sentinel_api_requests_total` crece tras N requests; sin familias fuera del catálogo U1 |

---

## 3. Patrones de Performance

### P8 — Verificación de planes de query (→ NFR-U2-PERF-01, Q5=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Tests smoke: preparar dataset pequeño y ejecutar `EXPLAIN QUERY PLAN` en las queries principales (list assets por status, events por rango, events por activo, observations por activo+ventana, alerts por estado) |
| Afirmación | El plan contiene `USING INDEX idx_…` (no `SCAN` completo) en cada una |
| No hace | Sin cache, sin materialized views, sin ORM magic: los índices de `domain-entities.md` son la optimización |
| Verificación | `pytest tests/unit/core/test_query_plans.py` en job `test` |

### P9 — Baseline de latencia informativa (→ NFR-U2-PERF-02)

| Elemento | Diseño |
|---|---|
| Mecanismo | Test con `TestClient` que mide p95 de `GET /assets`, `GET /events`, `POST /ingest` (lote pequeño) y lo **imprime** (`-s`); sin `assert` de umbral |
| Por qué sin assert | NFR-PERF-03 es no vinculante; un gate de p95 en runners compartidos sería flaky (Q2=A del plan de NFR Req) |
| Verificación | Salida visible en CI como anotación; revisada en U11 si la demo muestra latencia |

---

## 4. Patrones de Security

### P10 — Telemetría de fallos de auth (→ NFR-U2-SEC-02, Q6=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Cada 401/403 ⇒ log `level=warning`, `event="ingest_auth_failed"`, campos: `ts`, `component`, `client_ip`, `path`; **prohibido** incluir el header `Authorization` o su valor |
| Dónde | Dependencia `require_ingest_token` antes de validar el payload |
| Verificación | Test: request sin token ⇒ warning emitido, cuerpo del log sin el valor del token (grep negativo) |

### P11 — Comparación constante de token (→ NFR-U2-SEC-02/03, TS-U2-07)

| Elemento | Diseño |
|---|---|
| Mecanismo | `hmac.compare_digest(presented, expected)`; ausente ⇒ 401; distinto ⇒ 401; `SENTINEL_INGEST_TOKEN` vacío en proceso ⇒ 403 "ingest token not configured" |
| No hace | Sin JWT, sin OAuth, sin rotación automática (fuera de MVP, Q4/Q5 NFR Req) |
| Verificación | Tests 401/403 + grep de repo: el token nunca aparece en logs, respuestas ni `Event` de foundation |

---

## 5. Patrón de Availability

### P12 — Backup basado en runbook (→ NFR-U2-AVAIL-01, Q6=NFR Req=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Sin CronJob de backup en MVP: el runbook (U11) documenta `kubectl snapshot`/`velero` del PVC y la restauración (`integrity_check` de P1 protege la restauración) |
| Por qué | Lab single-node; evidencia con envolvente <1 GB; automatizar añade superficie sin requerimiento |
| Verificación | Sección "Backup & Restore" presente en `docs/` al cerrar U11 |

---

## 6. Patrón de Maintainability (heredado, aplicado a U2)

### P13 — Gates de calidad en CI (→ NFR-U2-MNT-01..05)

| Elemento | Diseño |
|---|---|
| Mecanismo | Job `test` ampliado: `pytest --cov=sentinel/core --cov-fail-under=70` + property tests (`PB-U2-01..03`) + smoke `EXPLAIN` (P8); `lint`/`typecheck` sobre `core` |
| OpenAPI | `MNT-01`: app expone `/openapi.json` + `/docs` en lab (test: 200 con rutas `/api/v1/*`) |
| Retención | `MNT-05`: **cero** código de purga (la ausencia es la decisión) |

---

## 7. Mapa NFR → Patrón → Verificación

| NFR-U2 | Patrón | Verificación principal |
|---|---|---|
| PERF-01 | P7, P8 | EXPLAIN smoke + envolvente documentada |
| PERF-02 | P9 | Test informativo de p95 |
| SCAL-01 | P7 | Familias del contrato U1 + checklist U11 |
| AVAIL-01 | P1, P12 | Test integrity + runbook U11 |
| AVAIL-02 | P1, P4 | `test_persistence_restart` + shutdown test |
| AVAIL-03 | (política) | Sin alarmas de uptime (decisión) |
| SEC-01 | (infra U9/U10) | Manifiestos sin Service público |
| SEC-02 | P10, P11 | Tests 401/403 + grep de logs |
| SEC-03 | P11 | grep de repo |
| SEC-04 | (FD BR-U2-40) | Test de 500 sin traceback |
| REL-01 | P3 | Test de concurrencia |
| REL-02 | P4 | Test de SIGTERM |
| REL-03 | P5 | Test 503 rápido |
| REL-04 | P6 | Test de rollback total |
| MNT-01..05 | P13 | CI + cobertura ≥70% + PBT |
| TECH-01 | (stack) | job `test` |
