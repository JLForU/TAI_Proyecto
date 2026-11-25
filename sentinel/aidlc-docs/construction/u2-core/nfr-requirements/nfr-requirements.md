# NFR Requirements — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 2: Generation)
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U2 — `src/sentinel/core/`
**Decisiones (plan Q1–Q13)**: **A en todas** (2026-11-11).
**Entradas**: Functional Design de U2 (aprobado 2026-11-11T19:45:00Z), `requirements.md` §3/§4/§5, U1 `tech-stack-decisions.md` (TS-01..11), `implementation-scope.md`.

---

## 1. Alcance

NFR **específicos de la unidad U2** (API HTTP + SQLite + export). Hereda sin cambio TS-01..11 de U1. Los NFR de runtime K8s (U9), capabilities/imagen (U10) y pipeline extendido se evalúan en sus unidades; aquí se registran los que imponen restricciones verificables sobre el Core.

---

## 2. Requisitos no funcionales de U2

### 2.1 Rendimiento y capacidad (Performance / Scalability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U2-PERF-01 | **Envolvente de lab** como supuesto de capacidad: 10–50 activos, ≤1000 observaciones/lote, ≤10 lotes/min, DB <1 GB; sin sharding, réplicas ni cache | Plan Q1=A | Supuesto documentado en README/runbook; sin gate de throughput en CI |
| NFR-U2-PERF-02 | Latencia p95 de query **no vinculante** (NFR-PERF-03); test **informativo** que registra p95 de `/assets`,`/events` sin bloquear CI | Plan Q2=A | `tests/.../test_latency_baseline.py` (marca `--runxfail`-like, imprime p95) |
| NFR-U2-SCAL-01 | Si la demo supera PERF-01 (más activos/lotes), el crecimiento se revisa en U11 con métricas reales; decisión de escalado explícita, no implícita | Plan Q1=A | Checklist de U11 |

### 2.2 Disponibilidad (Availability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U2-AVAIL-01 | Evidencia persiste en **PVC** (SQLite WAL); **runbook** documenta snapshots del volumen como procedimiento manual; sin backup automatizado en MVP | Plan Q6=A, ST-M4-02 | Sección de backup en `docs/` (U11) |
| NFR-U2-AVAIL-02 | Recuperación tras reinicio: todo lo persistido consultable con el mismo `SENTINEL_DB_PATH` (global NFR-AVAIL-02) | FD BR-U2-19 | `pytest tests/integration/test_persistence_restart.py` |
| NFR-U2-AVAIL-03 | Disponibilidad **best-effort** con restart automático de K8s; **sin SLO formal** ni mediciones de uptime en el MVP | Plan Q13=A | Sin alarmas de uptime; documentado como no exigido |

### 2.3 Seguridad (Security — extensión SECURITY blocking)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U2-SEC-01 | **Transporte**: HTTP plano; exposición solo vía `kubectl port-forward` + NetworkPolicy default-deny (U10); TLS **fuera de MVP**, documentado en runbook | Plan Q4=A, NFR-SEC-01 | Manifiestos U9/U10 sin Service público; runbook |
| NFR-U2-SEC-02 | **Abuso de ingesta**: Bearer token (Secret U9) + `MAX_BATCH_ITEMS=1000` + NetworkPolicy; **sin rate limiter**; riesgo residual documentado en threat model de U9/U10 | Plan Q5=A, FD Q2/BR-04 | Tests 401/403/400; sección de threat model |
| NFR-U2-SEC-03 | **Sin secretos en el repo**: el token solo llega por env (`SENTINEL_INGEST_TOKEN`) inyectado desde Secret; nunca en logs ni respuestas | Reglas de seguridad, FD §6 | Revisión de código + grep en CI manual |
| NFR-U2-SEC-04 | Errores **nunca** filtran stacktrace ni detalle interno al cliente (500 ⇒ cuerpo genérico, traza solo en log) | FD BR-U2-40 | Test: excepción forzada ⇒ respuesta sin traceback |

### 2.4 Fiabilidad (Reliability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U2-REL-01 | **Writer único serializado**: 1 worker uvicorn; cada transacción de escritura bajo `threading.Lock` en proceso; lecturas concurrentes vía WAL sin lock | Plan Q3=A, BR-U2-18 | Test concurrente: N hilos escribiendo ⇒ 0 `database is locked` |
| NFR-U2-REL-02 | **Apagado ordenado**: lifespan de FastAPI cierra conexiones y ejecuta `PRAGMA wal_checkpoint(TRUNCATE)` en SIGTERM | Plan Q8=A | Test de shutdown: proceso exit 0 + DB íntegra al reabrir |
| NFR-U2-REL-03 | **Reintentos single-owner**: el Core responde 503 rápido (sin retry interno de DB); los colectores U4/U5 reintentan con backoff vía `foundation.retry` | Plan Q12=A, services.md §2.1 | Test: DB caída ⇒ 503 inmediato; retry testado en U4/U5 |
| NFR-U2-REL-04 | Transacción única por lote: rollback total ante error (sin escrituras parciales) | FD BR-U2-05 | Test con fallo forzado a mitad de lote |

### 2.5 Mantenibilidad (Maintainability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U2-MNT-01 | **OpenAPI habilitado** en lab: `/openapi.json` + `/docs` (acelera U3 y la demo) | Plan Q9=A | `curl /openapi.json` ⇒ 200 con rutas `/api/v1/*` |
| NFR-U2-MNT-02 | Cobertura **≥ 70%** en `src/sentinel/core/`; por debajo el job `test` falla | Plan Q10=A | `pytest --cov=sentinel/core --cov-fail-under=70` |
| NFR-U2-MNT-03 | `ruff check` + `ruff format --check` + `mypy` gradual en verde sobre `core` (hereda TS-04/05) | TS-04/05 | job `lint`/`typecheck` |
| NFR-U2-MNT-04 | **PBT de flow normalization** en CI (`PB-U2-01..03`: idempotencia de normalize, estabilidad de `event_id`, conservación de contadores) | NFR-TECH-03, FD §13 | `pytest tests/property` en job `test` |
| NFR-U2-MNT-05 | **Retención ilimitada** en MVP (sin prunes); crecimiento acotado por PERF-01; purga queda como decisión futura explícita | Plan Q7=A | Sin código de purga; documentado |

### 2.6 Stack técnico (Tech Stack)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U2-TECH-01 | Web framework **FastAPI + uvicorn** (fijado por NFR-TECH-02/04); worker único (REL-01); Pydantic para payloads (TS-02) | requirements §4, Plan Q3=A | Importación en `core.api`; job `test` |

---

## 3. Trazabilidad con NFR globales

| NFR global | Contribución de U2 |
|---|---|
| NFR-PERF-01..03 (no vinculantes) | PERF-01/02: envolvente documentada + baseline informativo |
| NFR-AVAIL-01 (sin HA) | AVAIL-03: best-effort, sin SLO |
| NFR-AVAIL-02 (recuperación PVC) | AVAIL-02 (verificable por test) |
| NFR-SEC-01 (SECURITY blocking) | SEC-01..04 (controles de diseño: token, límites, sin leaks, transporte acotado) |
| NFR-OPS-03 (docs Markdown) | MNT-01 (OpenAPI) + runbook de AVAIL-01 |
| NFR-TECH-02 (Python/FastAPI) | TECH-01 |
| NFR-TECH-03 (PBT designado: flow normalization) | MNT-04 (PB-U2-01..03) |
| NFR-OPS-02 (pipeline CI) | MNT-02/03 dentro de lint/test/build heredado |

---

## 4. Criterios de aceptación del assessment

- [x] Las 13 preguntas del plan respondidas sin ambigüedad (todas A).
- [x] Categorías evaluadas con justificación de omisión (Usability: sin UI en U2).
- [x] Todo NFR tiene forma de verificación (ninguno "estándar/típico" sin medición).
- [x] Sin contradicción con `implementation-scope.md`, FD de U2 ni TS-01..11.
- [x] Q5=A registrado explícitamente: ausencia de rate limiter = decisión, no omisión.

---

## 5. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
