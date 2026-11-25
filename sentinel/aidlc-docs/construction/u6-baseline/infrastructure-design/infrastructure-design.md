# Infrastructure Design — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 2: Generation)
**Fecha**: 2026-11-19
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U6 — `src/sentinel/baseline/` (Runtime: **librería en proceso dentro del Pod `sentinel-core`** — sin workload propio)
**Decisiones (plan Q1–Q6)**: **A en todas** — dentro del Deployment `sentinel-core` existente (sin workload/entrypoint nuevos); Dockerfile **sin cambios**; resources del Core **sin cambios**; PVC **sin cambios** (crecimiento marginal, retención como futuro); health `live`/`ready` de U2 **sin cambios** ante fallos de U6; observabilidad solo logs stdout por el canal existente (ServiceMonitor intacto; `/metrics` llega con U7); config solo env desde `values.yaml` (sin ConfigMap, sin secretos nuevos).
**Entradas**: FD, NFR Requirements y NFR Design de U6 (aprobados 2026-11-19), infra heredada de U2 (ID-U2-01..09), TS-U6-01..13, `requirements.md` §4/§5, precedentes Infra U4/U5.

---

## 1. Mapeo componente lógico → infraestructura real

| Componente lógico (NFR Design) | Infraestructura real | Notas |
|---|---|---|
| `ConditionService` + hook `on_accepted` | **Dentro del proceso uvicorn del Pod `sentinel-core`** (mismo contenedor, mismo worker) | Post-commit en el request de `POST /ingest`; sin hilo/cola/sidecar (Q1=A, P4/P5) |
| `BaselineSettings` + loader env | **env `SENTINEL_BASELINE_*`** inyectadas por U9 desde `values.yaml` (Q6=A) | Sin ConfigMap; fail-fast `ConfigError` si valor inválido |
| `statistics.py` / `conditions.py` (puras) | Sin infraestructura — cómputo en memoria del proceso Core | Buffer ≤5 en memoria; sin caché externa (P6) |
| Protocolos `BaselineRepository`/`AlertRepository` | **SQLite en el PVC existente de U2** (`/data/sentinel.db`, tablas `baselines`/`alerts` ya definidas en OQ-02) | Sin esquema nuevo, sin segunda BD, sin migración (FD Q7) |
| `indicators.metric_samples()` (→ U7) | Se materializará en el **endpoint `/metrics` del Core que agregará U7** (mismo Pod/Service 9108) | U6 no expone nada hoy (Q5=A; MNT-04) |
| Logs `component=baseline.*` | **stdout JSON del Pod `sentinel-core`** (`kubectl logs deploy/sentinel-core`) | Canal ya capturado por el stack de logging (Q5=A) |
| Health `live`/`ready` | **Idénticos a U2** — U6 no añade checks (Q4=A) | Fallo de hidratación/upsert ⇒ log, Core sigue ready (NFR-Req AVAIL-01/02) |
| Dockerfile / imagen | **Sin cambios** (misma imagen `sentinel:test`, non-root) | TS-U6 stack §3; sin deps pip nuevas (Q1=A implícito) |
| Objetos K8s (Deployment/Service/PVC/Secret/ServiceMonitor) | **Ninguno nuevo por U6**; el chart lo construye U9 | Namespace `sentinel` y SA heredados de U2 |

**No aplican a U6** (con justificación):
- **Messaging**: hook síncrono in-process, sin broker/colas/eventos (decisión de diseño #7 de U1; NFR-Req Q1=A).
- **Networking**: sin Service, puerto, probe ni egress nuevo — U6 corre en el mismo contenedor que el Core y no genera tráfico de red propio (FD §1; Q1/Q5=A).
- **ConfigMap / Secret nuevos**: config por env no sensible (Q6=A); token de ingesta sigue siendo el de U2.
- **`shared-infrastructure.md`**: U6 no introduce infraestructura compartida multi-unidad nueva (el PVC/Service/Secret ya existen desde U2).

---

## 2. Decisiones y justificación

| # | Decisión | Por qué |
|---|---|---|
| ID-U6-01 | **Sin workload propio**: U6 corre dentro del Deployment `sentinel-core` (uvicorn existente); sin entrypoint, command ni contenedor nuevos | La evaluación es un hook en el request de ingesta (FD §3.2); un Pod separado exigiría IPC/HTTP extra, rompería el post-commit in-process y añadiría latencia sin beneficio (Q1=A; precedente: `DiscoveryTrigger` de U4 tampoco desplegó nada propio) |
| ID-U6-02 | Dockerfile **sin cambios** en Code Gen U6 | TS-U6 + tech-stack §3: sin deps pip nuevas, imagen non-root existente, sin binario propio (Q1=A) |
| ID-U6-03 | Resources del Core **sin cambios** (los fijó U2: requests 100m/128Mi → limits 500m/512Mi) | El hook añade O(1) de CPU por observación aceptada + un buffer ≤5 muestras por serie en memoria; sin hilos nuevos — el sizing se valida en U11 (Build & Test en kind) y se sube solo si hay evidencia (Q2=A) |
| ID-U6-04 | PVC **sin cambios**; crecimiento de `baselines`/`alerts` documentado como **marginal y con revisión futura** (sin retención en MVP) | Filas pequeñas (μ/s² + estados; una alerta por activación), series acotadas (interfaces × 3 protocolos × 3 métricas), query paginada; la revisión de tamaño/retención queda como futuro en `deployment-architecture.md` §5 (Q3=A; coherente NFR-Req Q6=A) |
| ID-U6-05 | Health `live`/`ready` de U2 **sin cambios**: fallos de U6 (hidratación, upsert) no alteran los probes | NFR-U6-AVAIL-01/02: el Core nunca deja de servir por U6; exponer U6 en `ready` provocaría reinicios en bucle sin solución (la BD sigue caída) y contradeciría el patrón `HealthService`; la salud con datos la decidirá U8 (Q4=A) |
| ID-U6-06 | Observabilidad **solo logs stdout** por el canal existente; **sin** endpoint, puerto ni objetos de monitoring nuevos; el ServiceMonitor de U2 queda intacto | U6 no expone `/metrics` (MNT-04): cuando U7 agregue el endpoint en el Core, la señal de U6 saldrá por el mismo Service 9108/ServiceMonitor ya definido (Q5=A) |
| ID-U6-07 | Config **solo por env**: `values.yaml` (`baseline.k`, `baseline.absoluteBps`, `baseline.intervalSeconds`, `baseline.collectorTimeoutSeconds`) → `SENTINEL_BASELINE_*` en el Deployment del Core (handoff NFR-U6-OPS-01) | Loader estricto por env de FD §3.1; patrón U4/U5 (env literales desde values, sin ConfigMap); los 4 valores no son sensibles ⇒ sin Secret nuevo; namespace/SA/Secret heredados de U2 sin cambios (Q6=A) |
| ID-U6-08 | **Cero objetos K8s nuevos por U6**; manifiestos = especificación aquí, YAML en el chart de U9 | FD §4: sin ediciones de U6 a objetos; patrón ID-U2-09/ID-U5-10 (spec ahora, chart en U9) |

---

## 3. Especificación de manifiestos (entradas para U9)

### 3.1 Deployment `sentinel-core` — solo env nuevas de U6 (Q6=A)

```yaml
spec:
  template:
    spec:
      containers:
        - name: core
          # command/args, image, resources, probes, securityContext: SIN CAMBIOS (ID-U6-01/03/05)
          env:
            # … env existentes de U2 (SENTINEL_API_BASE, SENTINEL_INGEST_TOKEN, …) …
            # + handoff U6 (values.yaml → env, patrón U4/U5):
            - { name: SENTINEL_BASELINE_K,                       value: "3.0" }            # baseline.k
            - { name: SENTINEL_BASELINE_ABSOLUTE_BPS,            value: "1000000" }        # baseline.absoluteBps (sin default en código)
            - { name: SENTINEL_BASELINE_INTERVAL_SECONDS,        value: "5" }              # baseline.intervalSeconds
            - { name: SENTINEL_BASELINE_COLLECTOR_TIMEOUT_SECONDS, value: "300" }          # baseline.collectorTimeoutSeconds
          # ports/probes/resources: SIN CAMBIOS (Q2/Q4/Q5)
      # volumes/PVC: SIN CAMBIOS (ID-U6-04)
```

> Nota: los literales son defaults de referencia; en el chart de U9 provienen de `values.yaml` (`baseline.*`). `ABSOLUTE_BPS` **no tiene default en el código** (FD BR-U6-03) ⇒ el valor en `values.yaml` es obligatorio.

### 3.2 Manifiestos de U2 — sin cambios de objeto

Deployment `sentinel-core`, Service, PVC, Secret, ServiceMonitor, probes y resources **idénticos** a los de U2/U9 actuales; U6 no añade puertos ni volúmenes.

### 3.3 Fuera del MVP (documentado, sin código)

- Retención/VACUUM de `baselines`/`alerts` (revisión de tamaño del PVC) — futuro (ID-U6-04).
- Cualquier cambio de `resources` del Core por evidencia de U11 — solo si el Build & Test lo justifica (ID-U6-03).

---

## 4. Trazabilidad decisiones → NFR / FD

| Decisión | NFR / FD |
|---|---|
| ID-U6-01/02 | FD §3.2/§3.7, TS-U6-01/STACK-01, Q1 NFR-Req |
| ID-U6-03 | NFR-U6-PERF-01, Q1/Q2 Infra |
| ID-U6-04 | NFR-U6-SCAL-01 (sin retención MVP), Q3 Infra |
| ID-U6-05 | NFR-U6-AVAIL-01/02, patrón `HealthService`, Q4 Infra |
| ID-U6-06 | NFR-U6-MNT-03/04 (logs; sin `/metrics` propio), Q5 Infra |
| ID-U6-07 | NFR-U6-OPS-01 (handoff U9), FD §3.1, Q6 Infra |
| ID-U6-08 | FD §4, precedentes ID-U2-09/ID-U5-10 |
