# Infrastructure Design — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 2: Generation)
**Fecha**: 2026-11-19
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/` (Runtime: worker en proceso propio — Deployment `--loop` en U9 o `--once` local)
**Decisiones (plan Q1–Q7)**: **A en todas** — Deployment `replicas: 1` con `--loop`; Dockerfile **sin cambios**; resources = Core (validar pico SIM_RATE en U11); **OQ-01 resuelta: `CAP_SYS_ADMIN` descartado** (captura futura documentada con `NET_RAW`+`NET_ADMIN`); requisito de egress documentado para U9/U10 + salvedad `hostNetwork` vs NetworkPolicy; observabilidad solo logs stdout + heartbeat por observaciones (sin puerto/probe); config solo env desde values.yaml (sin ConfigMap).
**Entradas**: FD, NFR Requirements y NFR Design de U5 (aprobados), infra de U2 (ID-U2-01..09), infra de U4 (ID-U4-01..10), TS-U5-01..13, `requirements.md` §4 y OQ-01.

---

## 1. Mapeo componente lógico → infraestructura real

| Componente lógico (NFR Design) | Infraestructura real | Notas |
|---|---|---|
| `__main__.py` CLI (`--once`/`--loop`) | **Proceso del contenedor sensor** (misma imagen `sentinel:test`, distinto command/args) | Deployment de U9 ejecuta `--loop`; `--once` = tests/CI/demo sin chart (Q1=A, TECH-04) |
| `TrafficSettings` + loader env | **env `SENTINEL_TRAFFIC_*`** inyectadas por U9 desde `values.yaml` (Q7=A) | Sin ConfigMap; fail-fast (`ConfigError`) si valor inválido |
| Fuente (`SimulatedSource`/`FixtureSource`) | **Dentro del proceso del sensor** — sin dependencias de infra (MVP) | Sin scapy, sin sockets crudos, sin capabilities (SEC-01); `AfPacketSource` futuro = mismo proceso con `hostNetwork`+caps (§3.3) |
| `aggregator.py`/`arp.py` (ventanas, guard monótono) | **Hilos dentro del proceso sensor** (pipeline síncrono de un hilo, P4) | Sin sidecar, sin cola, sin servicio intermedio |
| `client.py` (ingest HTTP) | Egress **sensor → `sentinel-core:8080`** (Service heredado de U2) con Bearer del Secret | Requisito de egress en NetworkPolicy (ID-U5-04) |
| Ciclo de ventana → observaciones | `POST /api/v1/ingest` → SQLite del Core (PVC de U2) | Heartbeat `sensor-0` y `arp_mapping_changed` se derivan aquí (U2) |
| Logs (`arp_rate`, `sensor_export_failed`, `window_clock_regression`) | **stdout JSON** del sensor (`kubectl logs` del Pod) | Sin métrica propia (MNT-04, Q6=A) |
| Probes/ServiceMonitor/PVC/Service | **Idénticos a U2 para el Core**; el sensor **no añade** ninguno | Sin puerto, probe ni Service propio (ID-U5-06) |
| Dockerfile | **Sin cambios** (entrypoint `python -m sentinel.traffic` ya documentado, BR-26 U1) | scapy llegará —si se decide— con captura real futura (Q2=A) |

**No aplican a U5** (con justificación): Storage (sensor stateless, NFR-AVAIL-01 — sin PVC/caché; ventana descartable D-U5-05); Messaging (HTTP síncrono con retry ×5, sin broker — decisión #7 de U1); ConfigMap (config por env, Q7=A); Ingress/NodePort/LB (lab vía port-forward, hereda U2); ServiceMonitor propio (sin endpoint de métricas, MNT-04); `shared-infrastructure.md` (sin infra compartida multi-unidad nueva).

---

## 2. Decisiones y justificación

| # | Decisión | Por qué |
|---|---|---|
| ID-U5-01 | Workload = **Deployment `replicas: 1` con `--loop`** (U9): `restartPolicy: Always`, `python -m sentinel.traffic --loop` | Observación continua (heartbeat por ventanas, demo GT-05); FD §5 ya fija el patrón; single-sensor MVP (NFR-AVAIL-01) — un DaemonSet duplicaría observaciones/`sensor_id`; CronJob `--once` viviría <1 s por tick y rompería el heartbeat continuo (Q1=A) |
| ID-U5-02 | Dockerfile **sin cambios** en Code Gen U5 | TS-U5/Tech-stack §3: entrypoint ya documentado; imagen non-root existente; sin scapy ni deps pip nuevas (TECH-01, BR-U5-33) — pre-instalar scapy añadiría peso/superficie sin consumidor (Q2=A) |
| ID-U5-03 | Resources del sensor = **los del Core** (requests 100m/128Mi → limits 500m/512Mi) | Hot path ligero (dicts O(1), P5) y POSTs locales; pico con SIM_RATE alto (GT-04) a validar en U11 y subir solo si hace falta (Q3=A) |
| ID-U5-04 | **Requisito de egress documentado aquí**, implementado en U9/U10: DNS + `sentinel-core:8080` **+ salvedad `hostNetwork`**: cuando el sensor pase a `hostNetwork` (captura real), NetworkPolicy deja de ser el mecanismo de contención confiable según el CNI ⇒ acotar por bridge/CNI de laboratorio (`DECISIONES_PENDIENTES.md` §1) | El default-deny de U10 mataría el export en silencio; el sensor no escanea la LAN (eso es U4) — solo necesita el Core; documentar la salvedad evita afirmar un control que el CNI pueda no aplicar (Q5=A) |
| ID-U5-05 | **OQ-01 resuelta: `CAP_SYS_ADMIN` se descarta** del diseño documentado de captura; el Pod futuro queda con `hostNetwork: true` + `CAP_NET_RAW` + `CAP_NET_ADMIN` (solo si modo promiscuo) | `AF_PACKET` exige `CAP_NET_RAW`; promiscuo exige `CAP_NET_ADMIN`; `TPACKET_V3` no exige `CAP_SYS_ADMIN` — mantenerlo sería superficie de privilegio injustificada frente a SEC-01 (Q4=A); registro en `requirements.md` OQ-01 |
| ID-U5-06 | Sensor **sin Service, puerto, probe, ServiceMonitor ni PVC**; namespace `sentinel` y ServiceAccount heredados de U2 | El sensor solo hace egress; nada que health-checkear desde un Service (como U4 ID-U4-08); vitalidad vía heartbeat de observaciones + logs (Q6=A) |
| ID-U5-07 | Observabilidad = **solo logs JSON a stdout** + vitalidad por observaciones exitosas (heartbeat `sensor-0`) y `kubectl get pods` | MNT-04 prohíbe `/metrics` propio (los indicadores los publica U7 con familias de U1); ante crash el Deployment reinicia (exit ≠ 0) (Q6=A) |
| ID-U5-08 | Config **solo por env** (`values.yaml` → `SENTINEL_TRAFFIC_*` en el sensor; token desde el Secret heredado) | El loader estricto lee env (TS-U5-05); ConfigMap añadiría una pieza sin consumidor; U2/U4 no usan ConfigMap (Q7=A) |
| ID-U5-09 | Imagen **única compartida** Core+worker (`sentinel:test`): mismo artefacto, distinto command | Una imagen versionada con todo el código; el sensor no necesita capas distintas (Q2=A implícito) |
| ID-U5-10 | **Cero objetos K8s nuevos por U5**; el chart lo construye U9 | FD §4 = ninguna edición de U5 a U1/U2; manifiestos = especificación aquí, YAML en el chart de U9 (patrón ID-U2-09) |

---

## 3. Especificación de manifiestos (entradas para U9)

### 3.1 Deployment `sentinel-traffic` (nuevo en U9 — Q1=A)

```yaml
spec:
  replicas: 1                 # single-sensor MVP (NFR-AVAIL-01); sin HPA
  template:
    spec:
      securityContext: { runAsNonRoot: true, runAsUser: 10001 }   # hereda U1; sin capabilities (SEC-01)
      containers:
        - name: traffic
          image: sentinel:test                # kind load (U1)
          command: ["python", "-m", "sentinel.traffic"]
          args: ["--loop"]
          env:
            - { name: SENTINEL_TRAFFIC_WINDOW_SECONDS, value: "5" }
            - { name: SENTINEL_TRAFFIC_INTERFACE, value: "eth0" }
            - { name: SENTINEL_TRAFFIC_SIM_SEED, value: "42" }
            - { name: SENTINEL_TRAFFIC_SIM_RATE, value: "50" }
            - { name: SENTINEL_TRAFFIC_SENSOR_ID, value: "sensor-0" }
            - { name: SENTINEL_TRAFFIC_FALLBACK, value: "false" }
            - { name: SENTINEL_API_BASE, value: "http://sentinel-core:8080" }
            - { name: SENTINEL_INGEST_TOKEN, valueFrom: { secretKeyRef: { name: sentinel-core, key: ingest-token } } }
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits:   { cpu: 500m, memory: 512Mi }
          # sin ports, sin probes (ID-U5-06/07)
      # sin volumes (stateless)
```

> Nota: las `env` de `values.yaml` llegan como **literales** traducidos por U9 (no un ConfigMap — Q7=A); el snippet de arriba muestra el valor default de referencia.

### 3.2 Manifiestos de U2 — sin cambios de objeto

Deployment `sentinel-core`, Service, PVC, Secret, ServiceMonitor **idénticos**; U5 no añade env al Core (las observaciones de tráfico se procesan con los contratos ya existentes de `/api/v1/ingest`).

### 3.3 Diseño documentado del sensor con captura real (sin código en U5 — OQ-01 resuelta)

```yaml
spec:
  template:
    spec:
      hostNetwork: true        # solo cuando exista AfPacketSource (fuera del MVP)
      containers:
        - name: traffic
          securityContext:
            runAsNonRoot: true
            capabilities:
              drop: ["ALL"]
              add: ["CAP_NET_RAW", "CAP_NET_ADMIN"]   # NET_ADMIN solo si modo promiscuo
              # CAP_SYS_ADMIN: DESCARTADO (OQ-01, Q4=A)
```

- Con `hostNetwork: true`, la NetworkPolicy del sensor **puede no aplicar** según el CNI (ID-U5-04) — acotar el alcance por bridge/CNI (`DECISIONES_PENDIENTES.md` §1).
- Este bloque es **especificación para U9/U10**; no se despliega hasta que la captura real exista.

---

## 4. Entradas para `values.yaml` de U9

| Clave propuesta (U9) | env del sensor | Default (FD §3.1) | Restricción |
|---|---|---|---|
| `traffic.window` | `SENTINEL_TRAFFIC_WINDOW_SECONDS` | `5` | ∈ {1,5,10,30,60} — validador detrás de `helm lint --set traffic.window=7s` (BR-U5-02) |
| `traffic.interface` | `SENTINEL_TRAFFIC_INTERFACE` | `eth0` | no vacía, ≤255 |
| `traffic.simRate` | `SENTINEL_TRAFFIC_SIM_RATE` | `50` | > 0 |
| `traffic.simSeed` | `SENTINEL_TRAFFIC_SIM_SEED` | `42` | entero ≥ 0 |
| `sensor.id` | `SENTINEL_TRAFFIC_SENSOR_ID` | `sensor-0` | no vacío |
| `traffic.fallback` | `SENTINEL_TRAFFIC_FALLBACK` | `true` | `false` ⇒ `ConfigError` (D-U5-07) |
| `ingest.token` (Secret heredado) | `SENTINEL_INGEST_TOKEN` | — | Bearer del `POST /ingest` |
| `core.apiBase` (o default interno) | `SENTINEL_API_BASE` | `http://sentinel-core:8080` | BR-U5-24 |

Además U9/U10: crear el Deployment §3.1, la NetworkPolicy de egress del sensor (ID-U5-04: DNS + `sentinel-core:8080`) y — cuando haya captura real — el bloque §3.3.

---

## 5. Recursos consumidos por U5

| Recurso | Propiedad | Coste/mantenimiento |
|---|---|---|
| Objeto K8s nuevo | **1 Deployment** (creado en U9) | Pod permanente de lab (1 réplica) |
| CPU/RAM sensor | Propia del Pod (100m/128Mi→500m/512Mi) | Pico con SIM_RATE alto a validar en U11 |
| Tamaño de imagen | **Cero** (sin cambios de Dockerfile, Q2=A) | Nada que añadir al build |
| Disco | **Cero** (sin PVC nuevo, stateless) | Nada que purgar |
| Red | Egress: DNS + 8080 (1+ POSTs por ventana) | Sin puertos nuevos; sin tráfico a la LAN |
| Estado en Core | Cero objetos nuevos; observaciones vía `/ingest` ya existente | Cero cambios hasta U9 |

---

## 6. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
