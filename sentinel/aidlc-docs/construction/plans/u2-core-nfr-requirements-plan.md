# NFR Requirements Plan — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 1: Planning)
**Fecha**: 2026-11-11
**Estado**: ARTIFACTS_GENERATED — respuestas todas A; artefactos generados; pendiente de aprobación
**Unidad**: U2 — `src/sentinel/core/`
**Entradas**: `construction/u2-core/functional-design/*` (aprobado 2026-11-11T19:45:00Z), `requirements.md` §3 NFR + §4 constraints + §5 extensiones, U1 `tech-stack-decisions.md` (TS-01..11), `implementation-scope.md`.

---

## 1. Contexto del assessment (Step 1 — analizado)

U2 es el primer componente **con I/O**: API HTTP, SQLite en PVC, auth de ingesta, export. Sus NFR tocan capacidad/latencia del API, modelo de concurrencia del writer único, seguridad del transporte/abuso, disponibilidad del almacenamiento de evidencia y mantenibilidad (tests, cobertura, OpenAPI).

**Ya decidido (NO se pregunta)**: TS-01..11 de U1 (Python 3.11, Pydantic, ruff+mypy, pytest+cov≥70% foundation, GitHub Actions lint/test/build, JSON logging, pinning+Dependabot, SAST documentado como deuda); FastAPI+uvicorn (NFR-TECH-02/04); SQLite WAL single-writer (FD Q1=A); Bearer token en ingest (FD Q2=A); MAX_BATCH_ITEMS=1000; PBT de flow normalization (FD §13).

**Categorías evaluadas**:

| Categoría | Aplica a U2 | Tratamiento |
|---|---|---|
| Scalability | Sí | Q1 (envolvente de capacidad), Q7 (retención/crecimiento) |
| Performance | Sí | Q2 (latencia p95 de queries) |
| Availability | Sí | Q6 (backup de evidencia), Q13 (SLO del Core) |
| Security | Sí | Q4 (transporte/TLS), Q5 (abuso/rate limit); auth ya en FD |
| Tech Stack | Parcial | Stack fijado; Q10/Q11 (estrategia de tests) |
| Reliability | Sí | Q3 (concurrencia writer), Q8 (shutdown), Q12 (reintentos 503) |
| Maintainability | Sí | Q9 (OpenAPI/docs), Q10 (gate de cobertura core) |
| Usability | No | **Sin pregunta**: sin UI en U2 (usabilidad de GUI = U3, NFR-TECH-04) |

---

## 2. Checklist del plan

- [x] Analizar Functional Design y NFR globales
- [x] Generar preguntas NFR (Q1–Q13)
- [x] Recoger respuestas a los `[Answer]:` (todas A, 2026-11-11)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; sin ambigüedades; sin seguimientos
- [x] Generar `nfr-requirements/nfr-requirements.md`
- [x] Generar `nfr-requirements/tech-stack-decisions.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas.

### Question 1 — Envolvente de capacidad (Scalability)

Contexto: lab de defensa (10–50 activos, ventanas de 5 s, ~10 lotes/min por colector); NFR-PERF-01..03 no vinculantes.

A) Diseñar para el envolvente de lab documentado como supuesto de capacidad (10–50 activos, ≤1000 obs/lote, ≤10 lotes/min, DB <1 GB); sin sharding, réplicas ni cache *(recomendado)*

B) Exigir benchmark de throughput de ingesta en CI (`tests/perf/`) con umbral numérico

C) Diseñar desde ya para 100+ sensores/nodos (excede el MVP single-sensor)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Latencia de la API de consulta (Performance)

Contexto: NFR-PERF-03 "Core API p95 <500ms" marcado como *not binding* en requirements.

A) Mantener no vinculante; test informativo de latencia en entorno de test (registra p95, no bloquea CI) *(recomendado)*

B) Convertir p95<500ms en gate de CI sobre los endpoints de query (flaky en runners compartidos)

C) Sin medición alguna de latencia (solo tests funcionales)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Modelo de concurrencia del writer (Reliability / Scalability)

Contexto: FastAPI sync endpoints corren en threadpool; WAL permite lecturas concurrentes pero **un solo escritor** (BR-U2-18).

A) Un solo worker uvicorn; escrituras serializadas con `threading.Lock` en proceso alrededor de cada transacción de escritura; lecturas concurrentes vía WAL sin lock *(recomendado)*

B) Cola en proceso: un consumidor único escribe en SQLite (desacople todo I/O)

C) `uvicorn --workers 1` sin lock explícito (confiar en el GIL y el retry de sqlite3)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Seguridad del transporte (Security)

Contexto: NFR-SEC-01 (extensión SECURITY blocking); demo con port-forward; NetworkPolicy default-deny llega en U10.

A) HTTP plano en lab: exposición solo vía `kubectl port-forward` + NetworkPolicy default-deny (U10); TLS documentado como fuera de MVP (runbook) *(recomendado)*

B) TLS auto-firmado dentro del Core (cert en Secret, U9 lo genera)

C) Exigir TLS en Ingress (excede el alcance del MVP / kind)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Protección contra abuso de la ingesta (Security)

Contexto: Bearer token + `MAX_BATCH_ITEMS` ya decididos (FD Q2/A, BR-U2-04).

A) Sin rate limiter: token + límite de tamaño de lote + NetworkPolicy como capas; riesgo residual documentado en el threat model de U9/U10 *(recomendado)*

B) Rate limit simple en proceso (p. ej. ≤60 lotes/min por proceso) con respuesta 429

C) Middleware de rate limiting completo (slowapi/limits) en todos los endpoints

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Backup de la evidencia (Availability)

Contexto: la evidencia (events/observations) no debe perderse; ST-M4-02 ya exige recuperación tras reinicio.

A) Persistencia en PVC + **runbook** documentando snapshots del volumen (velero/CRI-O snapshot como procedimiento manual del admin); sin backup automatizado en MVP *(recomendado)*

B) CronJob en K8s que ejecuta `sqlite3 .backup` periódicamente a un segundo archivo en el PVC

C) Solo confiar en el PVC sin documentación de recuperación

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Retención de datos (Maintainability / Security)

Contexto: lab con DB <1 GB; sin requerimiento de purga.

A) Retención **ilimitada** en el MVP (sin prunes); crecimiento acotado por el envolvente de Q1 *(recomendado)*

B) Retención configurable (`SENTINEL_RETENTION_DAYS`, default 90) con purga al arrancar

C) Purga fija de 30 días sin configuración

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Apagado ordenado (Reliability)

Contexto: NFR-AVAIL-02 (recuperar estado tras reinicio); WAL.

A) Lifespan handler de FastAPI: al SIGTERM cerrar conexiones activas + `PRAGMA wal_checkpoint(TRUNCATE)` antes de salir *(recomendado)*

B) Sin manejo especial: dejar que K8s mate el proceso (WAL se recupera igual)

C) Dump completo a JSON en el shutdown además del checkpoint

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 9 — Documentación de la API (Maintainability)

Contexto: U3 consume `/api/v1`; demo; NFR-OPS-03 (docs en Markdown).

A) OpenAPI autogenerado de FastAPI habilitado: `/openapi.json` + `/docs` en el lab (acelera U3 y la demo) *(recomendado)*

B) `/docs` deshabilitado; OpenAPI solo como artefacto exportado en CI

C) Sin OpenAPI; documentación solo en Markdown

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 10 — Gate de cobertura para `core` (Maintainability)

Contexto: U1 fijó ≥70% en `foundation` (TS-06).

A) ≥70% en `src/sentinel/core/` (mismo bar, job `test` falla por debajo) *(recomendado)*

B) 60% en `core` (menor presión en código I/O)

C) 80% en todo `src/` (más estricto que U1)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 11 — Estrategia de tests de integración (Tech Stack / Testing)

A) FastAPI `TestClient` + archivo SQLite temporal por test (sin servidor vivo); tests HTTP de todos los endpoints + transacciones; el servidor vivo y los 5 GT se validan en Build and Test *(recomendado)*

B) Levantar uvicorn real en los tests (puerto efímero) para todo

C) Solo tests unitarios de servicios mockeando repositorios (sin DB real)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 12 — Propiedad de los reintentos ante 503 (Reliability)

Contexto: U1 aporta `foundation.retry`; los colectores reintentan (services.md §2.1).

A) **Single owner**: el Core devuelve 503 rápido (sin retry interno de DB); los reintentos con backoff viven en los colectores U4/U5 usando `foundation.retry` *(recomendado)*

B) El Core reintenta internamente operaciones de DB antes de responder 503

C) Ambos (Core reintenta y colectores también)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 13 — Disponibilidad esperada del Core (Availability)

Contexto: NFR-AVAIL-01 (sin HA en el MVP); K8s reinicia el Pod.

A) Best-effort con restart automático de K8s + recuperación desde PVC (BR-U2-19); **sin SLO formal** documentado *(recomendado)*

B) Definir y medir SLO 99% en el lab (requiere mediciones y alertas de uptime desde U7)

C) Exigir HA activo/pasivo (excede el MVP single-node)

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Artefactos obligatorios (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `construction/u2-core/nfr-requirements/nfr-requirements.md` | NFR específicos de U2 con métricas/verificabilidad, trazabilidad a NFR globales |
| `construction/u2-core/nfr-requirements/tech-stack-decisions.md` | Decisiones de stack de U2 (incluye las heredadas de TS-01..11 y las nuevas de este plan) |

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los artefactos de NFR Requirements y presentaré el mensaje de completitud.

**No se genera ningún artefacto de NFR Requirements hasta completar este gate.**
