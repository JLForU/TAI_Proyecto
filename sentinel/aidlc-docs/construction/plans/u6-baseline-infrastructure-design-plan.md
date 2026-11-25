# Infrastructure Design Plan — U6 (Baseline & deterministic conditions)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 1: Planning)
**Fecha**: 2026-11-19
**Estado**: GENERATED — respuestas todas A (2026-11-19); artefactos generados; pendiente de aprobación
**Unidad**: U6 — `src/sentinel/baseline/` (Runtime: **librería en proceso dentro del Pod `sentinel-core`** — sin workload propio)
**Entradas**: Functional Design, NFR Requirements y NFR Design de U6 (aprobados 2026-11-19), `requirements.md` §4 (K8s 1.28+, kind, Alpine) y §5, NFR-U6-OPS-01 (handoff de 4 env a U9), infra heredada de U2 (Deployment/Service/PVC/Secret/ServiceMonitor en namespace `sentinel`), precedentes Infra U4/U5.

---

## 1. Contexto del assessment (Step 1 — analizado)

U6 **no despliega nada propio**: es código dentro del proceso del Core (hook post-commit + repositorios en el mismo contenedor). Aquí se deciden los **impactos sobre el Deployment/imagen existentes** (esperados: ninguno), el efecto en **resources** del Pod, el **ciclo de vida del almacenamiento compartido** (PVC de U2), el contrato de **health** ante fallos de U6, la **observabilidad** (logs stdout + sin `/metrics` propio) y la **entrega de configuración** `SENTINEL_BASELINE_*` a U9.

**Ya decidido (NO se pregunta)**:
- Namespace `sentinel`, Service `sentinel-core:8080`, PVC, Secret, ServiceMonitor y healthcheck de U2 heredados **sin cambios de esquema** (OQ-02, FD Q7).
- Hook síncrono in-process, **sin broker/colas** (decisión de diseño #7 de U1; NFR-Req Q1).
- Sin endpoints ni puertos propios; sin `/metrics` propio (U7 lo expondrá en el Core); eventos a **stdout JSON** vía `foundation.logging` (patrón U1–U5).
- Config por **env estrictas** `SENTINEL_BASELINE_*` (FD §3.1) con handoff de los 4 parámetros a `values.yaml` (NFR-Req Q7=A / NFR-U6-OPS-01).
- Sin retención de `alerts` en MVP (NFR-Req Q6=A); imagen **non-root** sin cambios (NFR-SEC-02); Dockerfile intacto (TS-U6 stack §3); K8s 1.28+/kind en la máquina del usuario.

**Categorías evaluadas**:

| Categoría | Aplica a U6 | Tratamiento |
|---|---|---|
| Deployment Environment | Sí | Q1 (forma del despliegue: dentro del Pod Core) |
| Compute Infrastructure | Sí | Q2 (resources del Pod ante la carga O(1) del hook) |
| Storage Infrastructure | Sí | Q3 (PVC compartido: tamaño/crecimiento de `baselines`/`alerts`) |
| Messaging Infrastructure | No | **Sin pregunta**: hook síncrono in-process, sin broker/colas (decisión U1 #7; NFR-Req Q1=A) |
| Networking Infrastructure | No | **Sin pregunta**: sin Service/puerto/egress nuevo — U6 corre en el mismo contenedor que el Core; ningún tráfico cruza la red por U6 (FD §1) |
| Monitoring Infrastructure | Sí | Q4 (health/ready ante fallo de U6), Q5 (logs stdout; sin ServiceMonitor/endpoint nuevo) |
| Shared Infrastructure | Sí | Q6 (entrega de config: env desde `values.yaml`, sin ConfigMap); namespace/SA/Secret heredados de U2 (**sin pregunta**) |

---

## 2. Checklist del plan

- [x] Analizar Functional, NFR Requirements y NFR Design
- [x] Generar preguntas de infraestructura (Q1–Q6)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-19: "Acepto todo" ⇒ Q1–Q6 = A)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; interacciones revisadas (Q1×Dockerfile intacto, Q4×NFR-Req AVAIL-01/02, Q6×NFR-Req OPS-01 handoff) ⇒ **sin FQ necesarias**
- [x] Generar `infrastructure-design/infrastructure-design.md`
- [x] Generar `infrastructure-design/deployment-architecture.md`
- [x] Presentar mensaje de completitud y esperar aprobación (2026-11-19T09:40:00Z)

---

## 3. Preguntas de infraestructura

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Forma del despliegue (Deployment Environment / Compute)

Contexto: U6 es una librería en proceso (FD §3.7: `create_app` construye `ConditionService`); no hay entrypoint, binario ni contenedor nuevo; el chart lo construye U9.

- **A (recomendado)**: **Dentro del Deployment `sentinel-core` existente** — sin workload propio, sin entrypoint nuevo, sin cambios de imagen/Dockerfile (TS-U6); U6 solo añade código al proceso que ya corre en el Pod (mismo patrón que la integración de `DiscoveryTrigger` en U4, que tampoco desplegó nada propio).
- **B**: Pod/contenedor separado para el baseline (exige IPC/HTTP extra, rompe «hook post-commit in-process», añade latencia y superficie sin beneficio).
- **C**: Other (describe después de `[Answer]:`)

[Answer]: A
### Question 2 — Resources del Pod (Compute Infrastructure)

Contexto: el hook añade O(1) de CPU por observación aceptada (≤3 upserts + comparaciones) y un buffer ≤5 muestras por serie en memoria; sin hilos nuevos, sin `asyncio`.

- **A (recomendado)**: **Sin cambios a `resources.requests/limits`** del Core — la carga es despreciable frente a la ingesta/SQLite que el Pod ya maneja; el sizing lo fijó U2 y se valida en U11 (Build & Test en kind).
- **B**: Subir preventivamente `requests/limits` del Core por el baseline (headroom sin evidencia; contraria a «baseline de rendimiento sin gate» de NFR-Req Q1).
- **C**: Other (describe después de `[Answer]:`)

[Answer]: A
### Question 3 — Almacenamiento compartido (Storage Infrastructure)

Contexto: `baselines` y `alerts` viven en el **mismo SQLite y PVC** que creó U2 (OQ-02, sin esquema nuevo); el MVP no tiene retención (NFR-Req Q6=A); las filas son pequeñas (μ/s² + estados; una alerta por activación).

- **A (recomendado)**: **Sin cambios al PVC ni políticas de almacenamiento** — crecimiento marginal (series acotadas × μ/s² + alerts paginados); la revisión de tamaño/retención queda documentada como futuro en `infrastructure-design.md` (mismo tratamiento que events/alerts de U2).
- **B**: Ampliar el PVC preventivamente (capacidad sin medida; U2 ya eligió el tamaño para events/alerts del mismo orden).
- **C**: Other (describe después de `[Answer]:`)

[Answer]: A
### Question 4 — Health/readiness ante fallos de U6 (Monitoring Infrastructure / Availability)

Contexto: NFR-U6-AVAIL-01/02 fijan que U6 **nunca** rompe el Core (log + degradación); el healthcheck de U2 (`/health/live`, `/health/ready`) decide si el Pod sirve; U8 decidirá la salud con datos.

- **A (recomendado)**: **Endpoints de salud de U2 sin cambios** — un fallo de hidratación o de upsert no altera `live`/`ready` (el Core sigue sirviendo ingesta/GUI; el estado de condición es observabilidad de negocio, no de proceso — coherente con «la salud nunca rompe el proceso», patrón `HealthService`).
- **B**: Añadir un check de `ConditionService` al `ready` (si la hidratación falla, el Pod no estaría ready ⇒ reinicio en bucle sin solución al problema de BD, contradice NFR-U6-AVAIL-02).
- **C**: Other (describe después de `[Answer]:`)

[Answer]: A
### Question 5 — Observabilidad del Pod (Monitoring Infrastructure)

Contexto: U6 emite logs JSON a **stdout** (ya capturados por el stack de logging de U2/K8s); no expone puerto ni `/metrics` (U7 los añadirá en el Core); el ServiceMonitor de U2 apunta al Core.

- **A (recomendado)**: **Sin cambios de monitoring infra** — logs por el canal existente del Core; el ServiceMonitor/PodMonitor de U2 queda como está (cuando U7 exponga `/metrics`, la señal de U6 llegará por ahí); eventos `component=baseline.*` son la traza operativa de GT-04.
- **B**: Añadir ya un flujo de logs/metrics dedicado para U6 (canal nuevo sin consumidor hasta U7/U9 — complejidad prematura).
- **C**: Other (describe después de `[Answer]:`)

[Answer]: A
### Question 6 — Entrega de configuración (Shared Infrastructure)

Contexto: NFR-U6-OPS-01 fija el handoff de los 4 parámetros (`k`, `absolute_bps`, `interval`, `collector_timeout`) a `values.yaml` de U9; el loader de U6 lee **env** (`SENTINEL_BASELINE_*`); precedente U4/U5: env montadas directamente desde `values.yaml`, sin ConfigMap propio.

- **A (recomendado)**: **env desde `values.yaml` directamente** (patrón U4/U5: `baseline.*` → `SENTINEL_BASELINE_*` en el Deployment del Core); sin ConfigMap propio, sin secretos nuevos (los 4 valores no son sensibles); namespace/ServiceAccount/Secret heredados de U2 sin cambios.
- **B**: ConfigMap propio para `SENTINEL_BASELINE_*` (fichero montado que el loader tendría que parsear — rompe el loader por env estricto de FD §3.1).
- **C**: Other (describe después de `[Answer]:`)

[Answer]: A
---

## 4. Fuera de alcance de este plan

- Chart/manifests concretos, probes, NetworkPolicy y values de U9 (los consume y materializa U9/U10).
- `/metrics`, `PrometheusRule` y reglas de alerta (U7/U8); retención de datos (futuro documentado).
- Cambios de imagen, resources, PVC o esquema (fijados arriba como «sin cambios» salvo respuesta en contrario).
