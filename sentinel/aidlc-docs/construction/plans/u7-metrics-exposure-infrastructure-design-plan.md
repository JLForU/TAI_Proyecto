# Infrastructure Design Plan — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 1: Planning)
**Fecha**: 2026-11-24
**Estado**: Q1–Q6 = Acepto todo (2026-11-24); artefactos generados; pendiente de aprobación
**Unidad**: U7 — `src/sentinel/core/metrics/` (librería en proceso dentro del Pod `sentinel-core`) + `deploy/monitoring/servicemonitor.yaml` (manifiesto estático)
**Entradas**: Functional Design, NFR Requirements y NFR Design de U7 (aprobados 2026-11-24), `requirements.md` §4 (K8s 1.28+, kind) y §5, NFR-U7-OPS-01/SEC-01, precedentes Infra U4/U5/U6, PRD SN-031 (instalación del stack en U8).

---

## 1. Contexto del assessment (Step 1 — analizado)

U7 **no despliega ningún workload propio**: es el pipeline `collect()` dentro del proceso del Core (hilo daemon de `MetricsServer` en :9108, ya creado por U2) y **un único manifiesto estático** (`ServiceMonitor`). Aquí se deciden: cómo se entrega/aplica el manifiesto, el efecto en resources del Pod (lecturas extra por scrape), el efecto en el PVC (cero escrituras nuevas), el **contrato de red Prometheus→:9108** (handoff de NetworkPolicy a U8, crítico si U8 aplica default-deny), los **parámetros de scrape** del endpoint y las **convociones de labels** del ServiceMonitor frente al kube-prometheus-stack de U8.

**Ya decidido (NO se pregunta)**:
- Puerto 9108 y `MetricsServer` de U2 intactos; Dockerfile/imagen sin cambios (NFR-U7-STACK-01; TS-U7).
- Namespace `sentinel`, Service `sentinel-core`, PVC y Secret heredados de U2 sin cambios (U7 solo lee SQLite, nunca escribe).
- Servicio de monitoreo: **kube-prometheus-stack con release name `monitoring`** — decisión de PRD SN-031 que se ejecuta en U8 (SN-031..035); U7 solo aporta el `ServiceMonitor` que ese stack va a descubrir.
- Sin broker/mensajería, sin colas asíncronas (patrón U1 #7; hook y scrape síncronos in-process).
- Logs a stdout JSON vía `foundation.logging` (eventos `metrics_error`/`metrics_hook_failed`); sin sistema de logs nuevo.
- Sin auth en :9108 — control por NetworkPolicy (NFR-U7-SEC-01; SN-038 en U8).
- Retención/series del stack, Alertmanager, reglas prometheustool y dashboards: **U8** (SN-031..035) — fuera del alcance de U7.
- `ci.yml` sin cambios; sin gitops propio en U7 (SN-043 es U9/PRD).

**Categorías evaluadas**:

| Categoría | Aplica a U7 | Tratamiento |
|---|---|---|
| Deployment Environment | Sí | Q1 (cómo se entrega/aplica el ServiceMonitor) |
| Compute Infrastructure | Sí | Q2 (resources del Pod ante el scrape periódico) |
| Storage Infrastructure | Sí | Q3 (PVC ante lecturas `COUNT`/`LIMIT` por scrape — sin escrituras nuevas) |
| Messaging Infrastructure | No | **Sin pregunta**: sin broker/colas — scrape pull síncrono en hilo existente + hook síncrono (decisión U1 #7) |
| Networking Infrastructure | Sí | Q4 (tráfico Prometheus → `:9108` y handoff de NetworkPolicy a U8) |
| Monitoring Infrastructure | Sí | Q5 (parámetros de scrape del ServiceMonitor: intervalo/timeout) |
| Shared Infrastructure | Sí | Q6 (convención de labels `release`/`app` del SM frente al selector del stack) |

---

## 2. Checklist del plan

- [x] Analizar Functional, NFR Requirements y NFR Design (Step 1)
- [x] Generar preguntas de infraestructura (Q1–Q6, todas las categorías evaluadas)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-24: "Acepto todo lo recomendado" ⇒ Q1–Q6 = A)
- [x] Analizar respuestas y resolver ambigüedades — interacciones revisadas (Q1×Q6 label `release: monitoring` = helm release de SN-031; Q4×NFR-U7-SEC-01 handoff NP; Q5×FD §3.4 endpoint mínimo; Q1×orden U8 stack→SM) ⇒ **sin FQ necesarias**
- [x] Generar `infrastructure-design/infrastructure-design.md`
- [x] Generar `infrastructure-design/deployment-architecture.md`
- [ ] Presentar mensaje de completitud y esperar aprobación (Step 7)
- [ ] Registrar aprobación y actualizar `aidlc-state.md` (Step 9)

---

## 3. Preguntas de infraestructura

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Entrega/aplicación del ServiceMonitor (Deployment Environment)

Contexto: U7 genera `deploy/monitoring/servicemonitor.yaml` como archivo nuevo; el stack kube-prometheus-stack se instala en **U8** con release `monitoring` (SN-031). El SM no puede funcionar antes de que exista el stack.

- **A (recomendado)**: **Manifest estático standalone aplicado con `kubectl apply -f deploy/monitoring/servicemonitor.yaml` documentado en el README** (posterior a la instalación del stack en U8) — cero dependencia de helm/chart en U7, el archivo es autocontenido y U8/GT puede invocarlo tal cual; mismo patrón que el resto de `deploy/` (handoff PRD §4, SN-031).
- **B**: Empaquetar el SM dentro del chart de Sentinel (U9) como plantilla Helm — mezcla responsabilidades (el SM pertenece al stack de monitoreo, no al chart de la app) y exige templating para un manifiesto de 30 líneas.
- **C**: GitOps (carpeta monitoriada por Argo/Flux) — requiere plataforma GitOps no decidida en el PRD (SN-043 es posterior); sobredimensiona para un manifiesto.

[Answer]: A (2026-11-24, "Acepto todo lo recomendado")
### Question 2 — Resources del Pod ante el scrape (Compute Infrastructure)

Contexto: el scrape ejecuta ~8 COUNTs sobre índices existentes + `LIMIT 500` de observaciones + heartbeats ligeros, cada ~30 s, en un hilo daemon ya existente (`ThreadingHTTPServer`); NFR-U7-PERF-01 fija `K=500` y prohíbe DDL; sin hilos nuevos ni `asyncio`.

- **A (recomendado)**: **Sin cambios a `resources.requests/limits`** del Core — el costo por scrape es despreciable frente a la ingesta que el Pod ya maneja (mismo razonamiento que U6 Q2); el sizing se valida en kind (U11).
- **B**: Subir preventivamente `requests/limits` por el exporter (headroom sin evidencia; contrario a «baseline de rendimiento sin gate» de NFR-Req).
- **C**: Other (describe después de `[Answer]:`)

[Answer]: A (2026-11-24, "Acepto todo lo recomendado")
### Question 3 — Efecto en el almacenamiento (Storage Infrastructure)

Contexto: U7 **solo lee** SQLite (`observations` con `idx_obs_source`, `events` con `idx_events_type`, `alerts`, `baselines`, `sensor_status`); no escribe filas nuevas, no crea tablas, no altera esquema (FD §2.6, NFR-Req sin DDL).

- **A (recomendado)**: **Sin cambios al PVC ni políticas de almacenamiento** — crecimiento cero atribuible a U7; la revisión de retención de `observations` (crecimiento del tráfico) queda como futuro documentado en `infrastructure-design.md` (mismo tratamiento que U2/U6).
- **B**: Ampliar el PVC preventivamente por la carga de lectura (no hay escritura nueva que justificarlo).
- **C**: Other (describe después de `[Answer]:`)

[Answer]: A (2026-11-24, "Acepto todo lo recomendado")
### Question 4 — Contrato de red Prometheus → :9108 (Networking Infrastructure)

Contexto: el scrape va desde el namespace `monitoring` (Prometheus del stack de U8) hacia `sentinel-core:9108` en el namespace `sentinel`. **SN-038 (U8) aplica NetworkPolicy default-deny** — sin una regla de ingress explícita para el puerto 9108, el scrape fallará y el target quedará `down`. NFR-U7-SEC-01 confirmó :9108 sin auth y dejó el control a esa policy.

- **A (recomendado)**: **Handoff documentado a U8**: el `infrastructure-design.md` de U7 fija el contrato (ingress a `sentinel-core:9108` desde pods con label del namespace `monitoring`) y U8 lo implementa junto con SN-038 (que también permite 8080 para health/ready) — separación limpia: U7 declara el requisito de red, U8 posee todas las NetworkPolicies.
- **B**: U7 publica ya un fragmento de NetworkPolicy en `deploy/monitoring/` — duplicaría la propiedad de U8 sobre las policies y podría chocar con el default-deny de SN-038 si se aplica en distinto orden.
- **C**: Sin nada — el tráfico funciona sin policy (incorrecto si U8 aplica default-deny: rompería el scrape en silencio).

[Answer]: A (2026-11-24, "Acepto todo lo recomendado")
### Question 5 — Parámetros de scrape del ServiceMonitor (Monitoring Infrastructure)

Contexto: el endpoint del SM solo fija `port: metrics` y `path: /metrics` (FD Q7); `interval` y `scrapeTimeout` pueden omitirse (hereda defaults del Prometheus del stack, que U8 puede sobreescribir en `values.yaml`) o fijarse en el manifiesto.

- **A (recomendado)**: **Omitir `interval`/`scrapeTimeout` en el SM** — el stack decide (default del Prometheus instalado) y U8 afina desde `deploy/monitoring/values.yaml` si hace falta; el manifiesto de U7 queda mínimo y sin acoplar a un número que U8 podría querer cambiar; coherente con «sin gate de latencia» (NFR-PERF-02 es informativo).
- **B**: Fijar `interval: 15s` en el SM (muestra más fina para `rate()` de contadores; acopla el manifiesto y U8 no puede cambiarlo sin tocar U7).
- **C**: Fijar `interval: 30s` en el SM (muestreo más barato; misma pérdida de flexibilidad).

[Answer]: A (2026-11-24, "Acepto todo lo recomendado")
### Question 6 — Convención de labels del ServiceMonitor (Shared Infrastructure)

Contexto: kube-prometheus-stack por defecto selecciona los ServiceMonitor cuyo label `release` coincide con el nombre del release de helm (`monitoring`, según SN-031). El SM de U7 debe «encajar» en ese selector compartido; el selector del Service apunta a `app.kubernetes.io/name: sentinel-core` (patrón de labels de U2).

- **A (recomendado)**: **Labels mínimos compatibles con los defaults del stack** — `metadata.labels.release: monitoring` + selector de Service por `app.kubernetes.io/name: sentinel-core`, sin namespaceSelector explícito (SM vive en `sentinel`, Prometheus del stack por defecto mira todos los namespaces salvo que se restrinja en values de U8) — cero configuración extra del stack; U8 conserva el poder de restringir desde `values.yaml`.
- **B**: Selector explícito personalizado (p. ej. `app.kubernetes.io/part-of: sentinel` en el SM + `serviceMonitorSelector` en values de U8) — acopla dos archivos en dos unidades distintas para un caso de uso único.
- **C**: Other (describe después de `[Answer]:`)

[Answer]: A (2026-11-24, "Acepto todo lo recomendado")
