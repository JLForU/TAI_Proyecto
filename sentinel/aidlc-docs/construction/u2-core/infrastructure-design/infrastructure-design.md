# Infrastructure Design — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 2: Generation)
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U2 — `src/sentinel/core/` (Runtime: Deployment/Service/PVC/Secret del Core)
**Decisiones (plan Q1–Q8)**: **A en todas** — dev local con uvicorn+SQLite temporal; resources 100m/128Mi→500m/512Mi; PVC 2 Gi RWO Retain; Service único con 2 puertos; ServiceMonitor; liveness TCP/readiness `/health`/startupProbe; token vía `.env` local + Secret en K8s; namespace `sentinel`.
**Entradas**: FD y NFR Design de U2 (aprobados), `requirements.md` §4, nota de despliegue del usuario.

---

## 1. Mapeo componente lógico → infraestructura real

| Componente lógico (NFR Design) | Infraestructura real | Notas |
|---|---|---|
| App factory + lifespan (`core/api/app.py`) | Proceso **uvicorn** dentro del Pod `sentinel-core` (1 worker, Q3 NFR) | Dev local: mismo proceso fuera de contenedor (Q1=A) |
| `Database` + repos (`core/db/*`) | Archivo SQLite en **PVC** montado en `/data` (`SENTINEL_DB_PATH=/data/sentinel.db`) | WAL + integrity_check (P1) + write-lock (P3) |
| Routers `/api/v1/*` (8080) | **Service** `sentinel-core` puerto `http-api` (8080, ClusterIP) | Exposición externa solo `kubectl port-forward` (SEC-01) |
| Metrics adapter (9108) | Mismo Service, puerto `http-metrics` (9108) + **ServiceMonitor** | Familias del contrato U1; scrape por kube-prometheus-stack |
| `require_ingest_token` / `CoreSettings` | **Secret** `sentinel-core` → `env: SENTINEL_INGEST_TOKEN`; resto de claves en `env` del Deployment | Dev: `.env` gitignored (Q7=A); Secret creado por U9 |
| Evidencia JSONL (`core/evidence.py`) | stdout del Pod → logging de K8s (docker/kind) | Sin sidecar ni archivo (FD Q6=A) |
| Discovery trigger + `CycleRunner` | **En el mismo Pod** (runner inyectado por U4 como módulo del Core) | Lock de proceso = efímero con el Pod (P2 recupera stale runs) |
| Probes | `livenessProbe` TCP 8080 · `readinessProbe` HTTP `/api/v1/health` · `startupProbe` TCP 8080 | Q6=A |
| Resources | `requests 100m/128Mi` · `limits 500m/512Mi` | Q2=A, ajustables en values (U9) |

**No aplican a U2** (con justificación): Messaging (sin broker, HTTP síncrono); Shared Infrastructure multi-tenant (namespace único `sentinel`, Q8=A → sin `shared-infrastructure.md`); registro de imágenes (build local + `kind load`, U1 Q2=A).

---

## 2. Decisiones y justificación

| # | Decisión | Por qué |
|---|---|---|
| ID-U2-01 | Dev/test local con `uvicorn` + SQLite temporal; contenedor solo en Build & Test y demo kind | Ciclo rápido de Code Generation (Q1=A); misma imagen para todo |
| ID-U2-02 | Resources del Pod 100m/128Mi → 500m/512Mi | Envelope de lab (PERF-01); techo contra runaway en kind (Q2=A) |
| ID-U2-03 | PVC **2 Gi** RWO, storageClass default de kind, `Retain` | DB <1 GB con margen; sin dependencia de clases externas (Q3=A) |
| ID-U2-04 | Service único `sentinel-core` con dos puertos | Menos objetos, un punto de scrape (Q4=A); el ServiceMonitor referencia `http-metrics` |
| ID-U2-05 | **ServiceMonitor** (CRD de kube-prometheus-stack ya presente) | Integrado con el stack del proyecto (Q5=A) |
| ID-U2-06 | liveness TCP · readiness `/health` (DB) · startupProbe TCP | Un fallo de DB **no** reinicia el Pod (readiness separado); DDL del arranque tolerado (Q6=A) |
| ID-U2-07 | Token: `.env` local gitignored + Secret K8s → env | SEC-03 sin secretos en repo; tests 401/403 locales posibles (Q7=A) |
| ID-U2-08 | Namespace `sentinel` single-tenant; default-deny/SA = U10 | Aislamiento fino donde aporta (Q8=A, OQ-04 en U9/U10) |
| ID-U2-09 | Manifestos = **especificación** aquí; YAML reales los genera U9 en el chart (OQ-03) | Separación: U2 decide valores, U9 los materializa |

---

## 3. Especificación de manifiestos (entradas para U9)

### 3.1 Deployment `sentinel-core`

```yaml
spec:
  replicas: 1                 # single-writer (REL-01); sin HPA en MVP
  template:
    spec:
      securityContext: { runAsNonRoot: true, runAsUser: 10001 }   # hereda U1
      containers:
        - name: core
          image: sentinel:test                # kind load (U1)
          ports:
            - { name: http-api, containerPort: 8080 }
            - { name: http-metrics, containerPort: 9108 }
          env:
            - { name: SENTINEL_DB_PATH, value: /data/sentinel.db }
            - { name: SENTINEL_INGEST_TOKEN, valueFrom: { secretKeyRef: { name: sentinel-core, key: ingest-token } } }
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits:   { cpu: 500m, memory: 512Mi }
          startupProbe:   { tcpSocket: { port: http-api },   failureThreshold: 30, periodSeconds: 2 }
          livenessProbe:  { tcpSocket: { port: http-api },   periodSeconds: 10 }
          readinessProbe: { httpGet: { path: /api/v1/health, port: http-api }, periodSeconds: 5 }
          volumeMounts: [{ name: data, mountPath: /data }]
      volumes: [{ name: data, persistentVolumeClaim: { claimName: sentinel-core } }]
```

### 3.2 Service `sentinel-core`

```yaml
spec:
  type: ClusterIP
  ports:
    - { name: http-api, port: 8080, targetPort: http-api }
    - { name: http-metrics, port: 9108, targetPort: http-metrics }
```

### 3.3 PVC `sentinel-core`

```yaml
spec:
  accessModes: [ReadWriteOnce]
  resources: { requests: { storage: 2Gi } }
  # storageClass: default de kind; persistentVolumeReclaimPolicy: Retain (a nivel PV)
```

### 3.4 ServiceMonitor `sentinel-core`

```yaml
spec:
  selector:
    matchLabels: { app.kubernetes.io/name: sentinel-core }
  endpoints:
    - { port: http-metrics, interval: 15s }
```

### 3.5 Secret `sentinel-core`

```yaml
stringData: { ingest-token: "<generado por U9 desde values; nunca en git>" }
```

---

## 4. Entradas para `values.yaml` de U9 (cierra OQ-03 parcial)

| Clave propuesta | Default | Origen |
|---|---|---|
| `core.image` | `sentinel:test` | ID-U2-01 |
| `core.resources.requests/limits` | 100m/128Mi · 500m/512Mi | Q2=A |
| `persistence.size` | `2Gi` | Q3=A |
| `persistence.accessMode` | `ReadWriteOnce` | Q3=A |
| `persistence.mountPath` | `/data` | FD (DB_PATH) |
| `core.ingestToken` | (requerido, desde `--set`/secret externo) | SEC-03; vacío ⇒ proceso 403 en ingest |
| `metrics.serviceMonitor.enabled` | `true` | Q5=A |
| `metrics.port` | `9108` | FR-CORE-02 |

---

## 5. Recursos consumidos por U2

| Recurso | Propiedad | Coste/mantenimiento |
|---|---|---|
| Pod `sentinel-core` (1 réplica) | kind local (máquina del usuario) | Se arranca/para con la cluster |
| PVC 2 Gi | kind default provisioner (hostPath subyacente) | Retain: conserva la DB al borrar el Pod |
| Service + ServiceMonitor | cluster / kube-prometheus-stack | Ninguno propio |
| Secret de token | creado por U9 | Rotación manual (post-MVP) |

---

## 6. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
