# Infrastructure Design Plan — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 1: Planning)
**Fecha**: 2026-11-11
**Estado**: ARTIFACTS_GENERATED — respuestas todas A; artefactos generados; pendiente de aprobación
**Unidad**: U2 — `src/sentinel/core/` (Runtime: Deployment/Service/PVC/Secret del Core)
**Entradas**: Functional Design y NFR Design de U2 (aprobados), `requirements.md` §4 (K8s 1.28+, kind, Alpine), NFR-U2-SEC-01 (HTTP plano/port-forward), TS-U2-01..11, `unit-of-work.md` §U2, nota de despliegue del usuario ("Todo el Proyecto se va a desplegar en mi máquina").

---

## 1. Contexto del assessment (Step 1 — analizado)

U2 es el **primer componente que se despliega de verdad**: el Core necesita Deployment, Service, PVC (SQLite), Secret (token) y las piezas de red/sondeo que U9 consolidará en el chart. Aquí se deciden los **valores y patrones** que U9 llevará a `values.yaml` (OQ-03 se cierra en U9 con estas respuestas).

Ya decidido (NO se pregunta): kind local en la máquina del usuario (Q1 U1); HTTP plano + port-forward + NetworkPolicy (NFR-U2-SEC-01); token desde Secret (FD Q2); sin broker; familia de métricas del contrato U1 en 9108; DDL/DB_PATH `/data/sentinel.db` (FD).

**Categorías evaluadas**:

| Categoría | Aplica a U2 | Tratamiento |
|---|---|---|
| Deployment Environment | Sí | Q1 (modo de dev/run durante Code Gen y tests) |
| Compute Infrastructure | Sí | Q2 (resources del Pod Core) |
| Storage Infrastructure | Sí | Q3 (PVC de SQLite) |
| Messaging Infrastructure | No | **Sin pregunta**: sin broker/colas (decisión de diseño #7; HTTP síncrono único) |
| Networking Infrastructure | Sí | Q4 (Services/puertos), Q5 (scrape de métricas) |
| Monitoring Infrastructure | Sí | Q5 (ServiceMonitor vs anotaciones), Q6 (probes) |
| Shared Infrastructure | Sí | Q7 (Secret en dev local vs K8s), Q8 (namespace/aislamiento) |

---

## 2. Checklist del plan

- [x] Analizar Functional y NFR Design
- [x] Generar preguntas de infraestructura (Q1–Q8)
- [x] Recoger respuestas a los `[Answer]:` (todas A, 2026-11-11)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; sin ambigüedades; sin seguimientos
- [x] Generar `infrastructure-design/infrastructure-design.md`
- [x] Generar `infrastructure-design/deployment-architecture.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de infraestructura

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas.

### Question 1 — Modo de ejecución durante desarrollo/tests (Deployment Environment)

Contexto: Code Generation y Build & Test corren en la máquina del usuario; la demo usa kind.

A) **Dev/test local**: `uvicorn` en proceso + archivo SQLite temporal/directo; **contenedor** (`docker build` de U1 + imagen) solo para Build & Test y la demo en kind *(recomendado)*

B) Siempre en contenedor (docker compose incluso para unit tests)

C) kind desde el primer día (ciclo de dev lento)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Resources del Pod Core (Compute Infrastructure)

Contexto: kind en máquina local; lab 10–50 activos; envelope PERF-01.

A) `requests: 100m CPU / 128Mi` · `limits: 500m CPU / 512Mi` — ajustables desde `values.yaml` en U9 *(recomendado)*

B) Sin resources (defaults de Kubernetes)

C) Solo requests (sin limits, sin riesgo de OOM-kill pero sin techo)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — PVC para SQLite (Storage Infrastructure)

Contexto: DB <1 GB (envelope PERF-01); `SENTINEL_DB_PATH=/data/sentinel.db`; ST-M4-02 exige persistencia; OQ-03 (values) se cierra en U9 con este valor.

A) **2 Gi**, `ReadWriteOnce`, storageClass default de kind, `mountPath: /data`; reciclaje: Retain *(recomendado)*

B) 1 Gi (ajustado al envelope, margen mínimo)

C) 10 Mucho para lab (prematura)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Topología de Services (Networking Infrastructure)

Contexto: API en 8080 (FR-GUI/FR-CORE-01) y métricas en 9108 (FR-CORE-02); exposición solo port-forward.

A) **Un solo Service** `sentinel-core` (ClusterIP) con dos puertos: `http-api` (8080) y `http-metrics` (9108) *(recomendado)*

B) Dos Services (`sentinel-core`, `sentinel-core-metrics`)

C) NodePort para ambos (exposición en la red del nodo)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Scrape de Prometheus (Monitoring Infrastructure)

Contexto: proyecto ya usa `kube-prometheus-stack` (requirements §4); ServiceMonitor es su CRD.

A) **ServiceMonitor** `sentinel-core` con `port: http-metrics`, selector hacia el Service, namespace del stack *(recomendado)*

B) Anotaciones `prometheus.io/scrape: "true"` en el Pod (funciona sin CRD, menos integrado)

C) Dejarlo sin definir aquí (U9 lo decide en el chart)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Probes del Pod (Monitoring / Reliability)

Contexto: `/api/v1/health` deriva estado de DB (Q11 FD); readiness debe evitar tráfico si la DB no responde.

A) **liveness** = TCP en 8080 (proceso vivo) · **readiness** = `GET /api/v1/health` (DB conectada) · **startupProbe** en 8080 con tolerancia al DDL del arranque *(recomendado)*

B) liveness y readiness idénticos en `/health` (más simple, un fallo de DB reinicia el Pod)

C) Solo liveness (sin readiness)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Gestión del token de ingesta (Shared / Security)

Contexto: `SENTINEL_INGEST_TOKEN`; SEC-03 (sin secretos en repo); U9 inyecta Secret.

A) **Dev local**: archivo `.env` (gitignored) o variable de shell · **K8s**: Secret `sentinel-core` → `env` en el Deployment (creado por U9 desde values) *(recomendado)*

B) Token fijo hardcodeado para el lab (rápido, viola SEC-03)

C) Sin token en dev (solo presente en K8s) — rompe los tests 401/403 locales

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Namespace y aislamiento (Shared Infrastructure)

Contexto: U10 hará NetworkPolicy/RBAC; OQ-04 (policies) es de U9/U10.

A) Core en el namespace **`sentinel`** del proyecto (single-tenant); aislamiento fino (default-deny, SA separada) = U10 *(recomendado)*

B) Namespace propio `sentinel-core` (aislamiento por namespace desde ya)

C) namespace `default` (sin aislamiento)

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Artefactos obligatorios (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `construction/u2-core/infrastructure-design/infrastructure-design.md` | Mapeo componente→infra (Deployment, Service, PVC, Secret, probes, resources, scrape), entradas para `values.yaml` de U9 |
| `construction/u2-core/infrastructure-design/deployment-architecture.md` | Arquitectura de despliegue: diagrama de topología (kind, Core, PVC, Prometheus, port-forward), flujo de arranque, puertos y flujos de red |

> `shared-infrastructure.md` **no** aplica: no hay infraestructura compartida multi-unidad más allá del namespace `sentinel` (decidido en Q8, consolidado en U9).

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los artefactos de Infrastructure Design y presentaré el mensaje de completitud.

**No se genera ningún artefacto de Infrastructure Design hasta completar este gate.**
