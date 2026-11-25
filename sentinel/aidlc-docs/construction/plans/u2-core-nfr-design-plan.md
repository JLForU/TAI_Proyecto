# NFR Design Plan — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — NFR Design (Parte 1: Planning)
**Fecha**: 2026-11-11
**Estado**: ARTIFACTS_GENERATED — respuestas todas A; artefactos generados; pendiente de aprobación
**Unidad**: U2 — `src/sentinel/core/`
**Entradas**: `construction/u2-core/nfr-requirements/*` (aprobado 2026-11-11T20:12:00Z: NFR-U2-PERF/AVAIL/SEC/REL/MNT/TECH, TS-U2-01..11), Functional Design de U2 (aprobado), `nfr-design` U1 (patrones `foundation.retry`).

---

## 1. Contexto del assessment (Step 1 — analizado)

Cómo incorporar los NFR aprobados de U2 en **patrones de diseño y componentes lógicos** concretos: cómo se comporta el Core ante fallos de DB, contención de lock, reinicios con ciclos a medias; qué observabilidad de capacidad; cómo se compone la capa HTTP/DB interna.

Ya decidido en etapas previas (NO se pregunta): write-lock + WAL (REL-01), lifespan shutdown (REL-02), 503 fast-fail single-owner (REL-03), transacción única (REL-04), token con `compare_digest` (TS-U2-07), TestClient+SQLite temporal (TS-U2-04), DDL idempotente (TS-U2-03), familias de métricas = contrato U1 intacto (FD Q10=A), evidencia por `foundation.logging` (FD Q6=A).

**Categorías evaluadas**:

| Categoría | Aplica a U2 | Tratamiento |
|---|---|---|
| Resilience Patterns | Sí | Q1 (integridad de DB al arrancar), Q2 (ciclos stale), Q3 (política del lock) |
| Scalability Patterns | Sí | Q4 (observabilidad de capacidad sin romper contrato U1) |
| Performance Patterns | Sí | Q5 (verificación de planes de query) |
| Security Patterns | Sí | Q6 (observabilidad de fallos de auth) |
| Logical Components | Sí | Q7 (composición API), Q8 (componente DB), Q9 (layering), Q10 (adaptador de métricas) |

---

## 2. Checklist del plan

- [x] Analizar NFR requirements aprobados
- [x] Generar preguntas de diseño NFR (Q1–Q10)
- [x] Recoger respuestas a los `[Answer]:` (todas A, 2026-11-11)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; sin ambigüedades; sin seguimientos
- [x] Generar `nfr-design/nfr-design-patterns.md`
- [x] Generar `nfr-design/logical-components.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas.

### Question 1 — Integridad de la DB al arrancar (Resilience Patterns)

Contexto: evidencia en PVC; NFR-U2-AVAIL-02 (recuperación tras reinicio).

A) Al arrancar ejecutar `PRAGMA integrity_check`; si falla ⇒ log de error claro + **exit 1 sin tocar el archivo** (K8s reinicia; runbook de restauración desde snapshot) *(recomendado)*

B) Si la DB está corrupta, renombrarla a `.corrupt` y crear una nueva vacía (arranca siempre, pero pierde evidencia en silencio)

C) Sin comprobar: abrir y fallar en la primera query

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Ciclos de discovery stale tras reinicio (Resilience Patterns)

Contexto: `discovery_runs` puede quedar en `running` si el Core muere a mitad de ciclo; lock de proceso perdido.

A) Al arrancar, marcar como `failed` (con `error="core restarted"`) todo run en `running` heredado; el lock queda libre *(recomendado)*

B) Dejarlos en `running` indefinidamente (el status endpoint los mostraría colgados)

C) Job periódico que los cierra tras un timeout configurable

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Política de adquisición del write-lock (Resilience / Performance)

Contexto: REL-01 (lock por transacción de escritura); hasta 10 lotes/min + lecturas GUI; threadpool de FastAPI.

A) Espera **bloqueante natural** del hilo (sin timeout): la contención en lab es rara y el threadpool acota la cola; ninguna petición pierde su escritura *(recomendado)*

B) Timeout de 500 ms en el lock ⇒ **503** (acota latencia, pero puede rechazar lotes válidos bajo picos)

C) Cola FIFO explícita con métrica de tiempo de espera (más piezas, beneficio solo si el lab crece)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Observabilidad de capacidad (Scalability Patterns)

Contexto: NFR-U2-SCAL-01 (crecimiento revisable en U11); contrato de familias de U1 intacto (FD Q10=A); familia `sentinel_api_requests_total` ya existe.

A) Usar **solo familias existentes** del contrato U1: `sentinel_api_requests_total` (stub con contadores reales desde U2) y `sentinel_collector_heartbeat_age_seconds` (desde health); sin nuevas familias *(recomendado)*

B) Añadir familias nuevas `sentinel_core_*` (db size, query duration) al contrato de U1 (requiere re-aprobar U1)

C) Sin métricas de capacidad: solo el `/health` para observar crecimiento

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Verificación de planes de query (Performance Patterns)

Contexto: PERF-01 (escala lab, sin cache); esquema con 7 tablas e índices definidos en `domain-entities.md`.

A) Tests smoke con `EXPLAIN QUERY PLAN` que afirman el uso de índices en las queries principales (assets/events/alerts por rango y por activo); **sin cache** *(recomendado)*

B) Cache en memoria de los listados (invalidación al escribir) para "asegurar" p95

C) Sin verificación de planes (confiar en los índices escritos)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Observabilidad de fallos de auth (Security Patterns)

Contexto: SEC-02 (token); 401/403 en la ingesta.

A) Log **warning** por cada 401/403 con timestamp + IP de origen + endpoint; **jamás** el valor del token *(recomendado)*

B) Solo la respuesta HTTP, sin log (menos ruido)

C) Log a nivel debug (apagado por defecto)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Composición de la capa HTTP (Logical Components)

Contexto: dependencias `require_ingest_token`, `pagination_params`, manejo de errores por router.

A) **Dependencias FastAPI** (inyección por ruta) + **módulos router por área** (`api/routes_ingest.py`, `routes_query.py`, …); sin middleware global de auth *(recomendado)*

B) Middleware ASGI global que intercepta todo `/api/v1` (auth + errores centralizados)

C) Decoradores por handler (estilo Flask, sin inyección)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Componente de acceso a DB (Logical Components)

Contexto: REL-01 (lock), REL-02 (cierre en lifespan), conexión por request (FD Q1=A).

A) Clase **`Database`** con `connect()` como context manager (una conexión por request/transaction), `write_lock` interno, y `close()` invocado por el lifespan *(recomendado)*

B) Pool de conexiones (sqlite3 no gana nada con pool en un solo proceso)

C) Conexión global de módulo compartida entre hilos (sin lock explícito)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 9 — Layering interno (Logical Components)

Contexto: component-methods define servicios y repos; FD §2 componentes.

A) **Router (HTTP/schemas) → Servicio (lógica) → Repositorio (SQL delgado)**; cero SQL en routers; servicios sin conocer FastAPI *(recomendado)*

B) Routers con SQL directo (menos capas, más rápido de escribir, peor testeable)

C) Unit-of-Work + interfaces/gateways abstractos por repositorio (más ceremonia que valor en lab)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 10 — Adaptador de métricas en 9108 (Logical Components)

Contexto: FD Q10=A (servidor stub U2, U7 implementa `collect()`); contrato U1 (`metrics_contract`).

A) Módulo **`core.metrics`** que reutiliza nombres/labels/`render_prometheus` de `foundation.metrics_contract` y rellena familias con zeros/contadores stub; U7 sustituye las funciones de recolección sin tocar el router ni el contrato *(recomendado)*

B) Integrar `prometheus_client` como dependencia (multilínea, formato propio, duplica el contrato)

C) Ensamblar texto Prometheus a mano dentro del router `/metrics`

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Artefactos obligatorios (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `construction/u2-core/nfr-design/nfr-design-patterns.md` | Patrones aplicados por NFR (resilience, scalability, performance, security) con mecanismo concreto y verificación |
| `construction/u2-core/nfr-design/logical-components.md` | Componentes lógicos nuevos/afectados (Database, routers, servicios, repos, metrics adapter, evidence helper) con responsabilidades y relaciones |

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los artefactos de NFR Design y presentaré el mensaje de completitud.

**No se genera ningún artefacto de NFR Design hasta completar este gate.**
