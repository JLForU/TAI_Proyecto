# Infrastructure Design — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 2: Generation)
**Fecha**: 2026-11-24
**Estado**: APPROVED (2026-11-24)
**Unidad**: U7 — `src/sentinel/core/metrics/` (librería en proceso dentro del Pod `sentinel-core`) + `deploy/monitoring/servicemonitor.yaml` (manifiesto estático)
**Decisiones (plan Q1–Q6)**: **A en todas** — SM standalone aplicado con `kubectl apply -f` documentado en README (tras el stack de U8); resources del Core **sin cambios**; PVC **sin cambios** (solo lecturas); **handoff de NetworkPolicy a U8** (contrato de ingress a :9108 — crítico ante default-deny SN-038); SM **sin** `interval`/`scrapeTimeout` (defaults del stack, U8 afina desde values); labels mínimos `release: monitoring` + selector `app.kubernetes.io/name: sentinel-core`.
**Entradas**: FD, NFR Requirements y NFR Design de U7 (aprobados 2026-11-24), infra heredada de U2 (ID-U2-01..09), TS-U7-01..12, `requirements.md` §4/§5, precedentes Infra U4/U5/U6, PRD SN-031..035/038.

---

## 1. Mapeo componente lógico → infraestructura real

| Componente lógico (NFR Design) | Infraestructura real | Notas |
|---|---|---|
| Pipeline `collect()` + `ObservationCounters` | **Dentro del proceso uvicorn del Pod `sentinel-core`** (mismo contenedor, mismo worker) | Contadores en memoria del proceso; gauges leen SQLite del mismo Pod (Q1 del FD) |
| `MetricsServer` hilo daemon (U2) | **:9108 en el Pod `sentinel-core`, expuesto por el Service `sentinel-core:9108`** (puerto ya definido en U2) | Sin puerto nuevo; el scrape es pull desde Prometheus |
| Contrato v2 `metrics_contract.py` | Sin infraestructura — módulo de código en la imagen existente | Catálogo cerrado 14 familias / 7 labels |
| SQL de gauges (`LIMIT 500`, COUNTs) | **SQLite en el PVC existente de U2** (`/data/sentinel.db`) — **solo lectura**, índices `idx_obs_source`/`idx_events_type` ya existentes | Sin DDL, sin escrituras nuevas por U7 (Q3=A) |
| `HealthService.sensor_heartbeats()` | Sin infraestructura — método en el mismo proceso | Ahorra queries por scrape en el hilo de :9108 |
| `deploy/monitoring/servicemonitor.yaml` | **Objeto `ServiceMonitor` en el namespace `sentinel`**, descubierto por el kube-prometheus-stack (release `monitoring`, namespace `monitoring`) instalado en **U8** | Manifest standalone (Q6=A: `release: monitoring`) |
| Scraping Prometheus → :9108 | **Tráfico cross-namespace `monitoring` → `sentinel`**; contrato de ingress declarado aquí, implementado como NetworkPolicy en **U8 (SN-038)** | Q4=A handoff; sin auth (NFR-U7-SEC-01) |
| Logs `metrics_error` / `metrics_hook_failed` | **stdout JSON del Pod `sentinel-core`** (`kubectl logs deploy/sentinel-core`) | Canal existente (foundation.logging) |
| Tests U7 (unit/integration/property/latencia) | **Se ejecutan en CI local/`docker sentinel:test`** — no consumen infraestructura de runtime | El test de latencia es informativo (sin gate) |
| Dockerfile / imagen | **Sin cambios** (misma imagen `sentinel:test`, non-root) | TS-U7; sin deps pip nuevas (Q1=A implícito) |
| Objeto K8s nuevo | **Ninguno nuevo por U7** — Deployment/Service/PVC/Secret heredados de U2; el ServiceMonitor vive en `deploy/`, no en el chart | Q1=A; patrón ID-U5-10 (spec ahora, chart/ops en su unidad) |

**No aplican a U7** (con justificación):
- **Messaging**: sin broker/colas — scrape pull síncrono en hilo existente + hook síncrono (decisión de diseño #7 de U1).
- **Storage nuevo / migración**: U7 no escribe en la BD; crecimiento de `observations` es responsabilidad de la ingesta (U2/U5) y su retención queda como futuro (§5).
- **ConfigMap / Secret nuevos**: U7 no tiene configuración runtime — `K=500` y catálogos son constantes de código (NFR-Req); sin env `SENTINEL_METRICS_*`.
- **Load balancing / API gateway**: :9108 es un endpoint pull interno, sin ingress público (U8 controla por NetworkPolicy, no por Gateway).
- **`shared-infrastructure.md`**: U7 no introduce infraestructura compartida multi-unidad nueva (el ServiceMonitor apunta a infra ya existente; la compartida del stack la instala U8).

---

## 2. Decisiones y justificación

| # | Decisión | Por qué |
|---|---|---|
| ID-U7-01 | **Sin workload propio**: el exporter corre en el hilo daemon de `MetricsServer` dentro del Pod `sentinel-core`; sin entrypoint, command ni contenedor nuevos | El endpoint `/metrics` ya existe desde U2 con `collect_fn` inyectable (FD §3.3); un Pod separado exigiría duplicar acceso a SQLite y al estado de contadores en memoria (rompería los contadores de proceso) |
| ID-U7-02 | Dockerfile **sin cambios** en Code Gen U7 | TS-U7: sin deps pip nuevas; stdlib `http.server` + código en el paquete ya instalado (Q1=A implícito) |
| ID-U7-03 | Resources del Core **sin cambios** (los fijó U2: requests 100m/128Mi → limits 500m/512Mi) | Un scrape cada ~30 s ejecuta ~8 COUNTs indexados + `LIMIT 500` + heartbeats ligeros — despreciable frente a la ingesta; NFR-PERF-02 es solo informativo; sizing se valida en kind (U11) (Q2=A) |
| ID-U7-04 | PVC **sin cambios**; U7 es **solo lectura** sobre SQLite; retención de `observations` documentada como **futuro** (§5) | FD §2.6 sin DDL; `COUNT`/`SELECT … LIMIT` no crecen el archivo de forma atribuible a U7; WAL ya soporta el reader concurrente del hilo de métricas (Q3=A) |
| ID-U7-05 | Health `live`/`ready` de U2 **sin cambios**: un 500 del scrape no afecta los probes (viven en :8080) | NFR-U7-AVAIL-01: el fallo de scrape se comunica por la propia señal de Prometheus (target `down`) + log; meter el exporter en `ready` provocaría reinicios en bucle sin resolver la causa (Q4=NFR-Req) |
| ID-U7-06 | **ServiceMonitor standalone** en `deploy/monitoring/servicemonitor.yaml`, aplicado con **`kubectl apply -f` documentado en el README** — después de instalar el stack de U8 (SN-031) | Manifiesto autocontenido de ~30 líneas; sin templating ni acople al chart de Sentinel; U8/GT puede invocarlo tal cual; patrón `deploy/` del PRD (Q1=A) |
| ID-U7-07 | **Handoff de NetworkPolicy a U8**: este documento fija el contrato de ingress (pods del namespace `monitoring` → `sentinel-core:9108`); SN-038 lo implementa junto con la política default-deny | Si U8 aplica default-deny sin esta regla, el scrape queda `down` en silencio; U8 es dueña única de todas las NetworkPolicies (evita solaparse con SN-038/036/037) (Q4=A) |
| ID-U7-08 | SM **sin `interval` ni `scrapeTimeout`** — hereda los defaults del Prometheus del stack; U8 afina desde `deploy/monitoring/values.yaml` si hace falta | El manifiesto no se acopla a un número que otra unidad pueda querer cambiar; coherente con «baseline de rendimiento sin gate» (Q5=A) |
| ID-U7-09 | Labels del SM: `metadata.labels.release: monitoring` + selector de Service `app.kubernetes.io/name: sentinel-core`; sin `namespaceSelector` explícito | `release: monitoring` coincide con el nombre del release de helm de SN-031 ⇒ encaja en el `serviceMonitorSelector` por defecto del stack con **cero configuración extra**; U8 puede restringir namespaces desde values (Q6=A) |
| ID-U7-10 | **Cero objetos K8s nuevos por U7** (ni Deployment, ni Service, ni Secret, ni ConfigMap, ni SM dentro del chart) | FD §4: los únicos artefactos de U7 son código + 1 manifiesto en `deploy/`; namespace/SA/Secret heredados de U2 |
| ID-U7-11 | Observabilidad del exporter: **solo logs stdout** (`metrics_error`, `metrics_hook_failed`) + la métrica de estado que Prometheus derive (target `up`) | Sin sistema de logs nuevo; sin self-instrumentación de errores (NFR-Req Q7=A / patrón P9) |
| ID-U7-12 | **Sin env/config runtime nueva** (`SENTINEL_METRICS_*` no existe) — `LATEST_OBS_LIMIT=500`, HELP y catálogos son constantes de código | La única «config» es el contrato, que debe coincidir entre tests y runtime sin posibilidad de drift por env; handoff de config a U9: **ninguno** (Q3=NFR-Req sin DDL, FD Q10=A) |

---

## 3. Especificación de manifiestos

### 3.1 `deploy/monitoring/servicemonitor.yaml` — ServiceMonitor (archivo nuevo de U7, Q6=A)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: sentinel-core
  namespace: sentinel
  labels:
    release: monitoring          # coincide con el helm release de SN-031 (U8)
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: sentinel-core   # label del Service de U2
  endpoints:
    - port: metrics              # nombre del puerto en el Service de U2
      path: /metrics             # sin interval/scrapeTimeout (Q5=A: defaults del stack)
```

### 3.2 Service `sentinel-core` — sin cambios (entrada de U2, verificable por U7)

```yaml
ports:
  - name: http-api       # 8080
  - name: metrics        # 9108  ← endpoint que scrapa el ServiceMonitor
```

### 3.3 Deployment `sentinel-core` — sin cambios por U7

```yaml
# command/args, image, resources, probes, securityContext, env: SIN CAMBIOS (ID-U7-01/02/03/05/12)
# U7 no añade env; el collect_fn se compone en create_app (código, no manifiesto)
```

### 3.4 NetworkPolicy (especificación → implementación en U8, handoff ID-U7-07)

```yaml
# namespace: sentinel — A IMPLEMENTAR POR SN-038 (U8), contrato fijado aquí:
# ingress hacia pods label app.kubernetes.io/name=sentinel-core:
#   - puerto TCP 9108 desde pods del namespace monitoring (Prometheus)
#   - puerto TCP 8080 desde donde health/ready lo requiera (decisión de U8)
# El default-deny de SN-038 NO debe dejar sin regla al 9108 (si no, target down).
```

---

## 4. Handoffs por unidad

| Unidad | Qué recibe de U7 |
|---|---|
| **U8** (Observability & alerting / SN-031..035, 038) | Instalar kube-prometheus-stack (release `monitoring`, ns `monitoring`) → aplicar `deploy/monitoring/servicemonitor.yaml` → crear NetworkPolicy con el contrato §3.4 → `values.yaml` (interval/retención si se desea), PrometheusRules y dashboards |
| **U9** (K8s/Helm) | **Ninguna env nueva**; el chart ya expone Service 9108; el SM **no** se embebe en el chart (ID-U7-06/10) |
| **U11** (Docs & GT) | Sección README «Metrics & monitoring» (NFR-MNT-03) con `kubectl apply -f deploy/monitoring/servicemonitor.yaml` y verificación de scrape en kind |
| **U10** (Security) | Revisar que :9108 sigue sin auth y que la NetworkPolicy de U8 cumple NFR-U7-SEC-01/02 |

---

## 5. Futuros documentados (no en MVP)

1. **Retención de `observations`** — el crecimiento lo dicta la ingesta (U5), no U7; cuando toque, decidir retención global (afecta también el `LIMIT 500` como techo barato, no como límite duro).
2. **Ajuste de `interval`/`scrapeTimeout`** — desde `values.yaml` de U8 si la cadencia default no sirve (el SM de U7 queda sin fijarlos, Q5=A).
3. **Auth o mTLS en :9108** — si algún día el cluster comparte red no confiable; hoy lo resuelve NetworkPolicy (NFR-U7-SEC-01).
4. **`serviceMonitorNamespaceSelector` restrictivo** — si el cluster crece y el stack debe mirar solo `sentinel` (hoy el default mira todos, Q6=A).
