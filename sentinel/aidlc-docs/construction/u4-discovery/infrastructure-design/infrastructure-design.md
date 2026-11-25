# Infrastructure Design — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 2: Generation)
**Fecha**: 2026-11-16
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U4 — `src/sentinel/discovery/` (Runtime: worker en proceso propio — CronJob en U9 o `--loop` local)
**Decisiones (plan Q1–Q7)**: **A en todas** — Dockerfile +nmap en Code Gen U4; CronJob `--once` (*/15, Forbid, deadline 600 s, backoffLimit 3, Never); resources = Core (validar pico nmap en U11); non-root sin caps (ICMP degradable); requisito de egress documentado para U9/U10; observabilidad solo logs stdout + heartbeat por observaciones; config solo env desde values.yaml (sin ConfigMap).
**Entradas**: FD, NFR Requirements y NFR Design de U4 (aprobados), infra de U2 (ID-U2-01..09), TS-U4-01..12, `requirements.md` §4.

---

## 1. Mapeo componente lógico → infraestructura real

| Componente lógico (NFR Design) | Infraestructura real | Notas |
|---|---|---|
| `__main__.py` CLI (`--once`/`--loop`) | **Proceso del contenedor worker** (misma imagen `sentinel:test`, distinto command/args) | CronJob de U9 ejecuta `--once`; `--loop` = demo local sin chart (Q2=A) |
| `DiscoverySettings` + loader env | **env `SENTINEL_DISCOVERY_*`** inyectadas por U9 desde `values.yaml` (Q7=A) | Sin ConfigMap; fail-fast si falta la allowlist |
| `ScopeValidator` (C12) + worker scope | Mismo set de env en el worker **y en el Core** (D-U4-04: U9 inyecta en ambos workloads para la validación 400 pre-run) | Coherencia worker↔API por construcción |
| `scanner.py` (`NmapScanner`/`FixtureScanner`) | Binario **`nmap` en la imagen** (`apk add --no-cache nmap`, Q1=A); `ping`/`ip` los aporta busybox | Sin nmap ⇒ fallback fixtures (D-U4-05); scanner `auto` resuelve |
| Probe pool + worker `run_cycle` | **Hilos dentro del proceso worker** (ThreadPoolExecutor ≤32, P4) | Sin sidecar, sin cola, sin servicio intermedio |
| `client.py` (ingest HTTP) | Egress **worker → `sentinel-core:8080`** (Service heredado de U2) con Bearer del Secret | Requisito de egress en NetworkPolicy (ID-U4-05) |
| `runner.py` `CycleRunnerImpl` | **Composición de arranque del Core** (import perezoso en `create_app`) — vive en el Pod de U2 | Solo para triggers manuales `POST /discovery`; el CronJob NO pasa por él |
| Ciclo exitoso → observaciones | `POST /ingest` → SQLite del Core (PVC de U2) | Heartbeat `sensor-0` + `last_seen` se actualizan aquí (Q6=A) |
| Log `discovery_cycle_failed` + exit 1 | **stdout JSON** del worker (`kubectl logs` del Job) | Sin métrica ni canal nuevo (FQ1=C, Q6=A) |
| Ediciones acotadas de U2 (Batch.reconcile, METRIC_FAMILIES, routes/app/trigger/collect) | Despliegues **en el Pod `sentinel-core` existente** (mismo Deployment) | Cero objetos K8s nuevos por U4 |
| ServiceMonitor, probes, PVC, Service, puerto | **Idénticos a U2** (ID-U2-02..05) | Worker sin Service ni puerto propio (ID-U4-08) |

**No aplican a U4** (con justificación): Storage (worker stateless, AVAIL-02 — sin PVC/caché); Messaging (HTTP síncrono con retry, sin broker — decisión #7 de U1); ConfigMap (config por env, Q7=A); Ingress/NodePort/LB (lab vía port-forward, hereda U2); ServiceMonitor propio (sin endpoint de métricas, FQ1=C); `shared-infrastructure.md` (sin infra compartida multi-unidad nueva).

---

## 2. Decisiones y justificación

| # | Decisión | Por qué |
|---|---|---|
| ID-U4-01 | Ampliar el Dockerfile en **Code Gen U4**: `apk add --no-cache nmap` (imagen única, sin multi-stage) | TS-U4-02/Tech-stack §3; Build & Test de U4 necesita escaneo real; multi-stage copia binarios con dependencias frágiles; postergar a U9 deja los tests con fixtures (Q1=A) |
| ID-U4-02 | Workload = **CronJob `--once`** (U9): `schedule: "*/15 * * * *"`, `concurrencyPolicy: Forbid`, `activeDeadlineSeconds: 600`, `backoffLimit: 3`, `restartPolicy: Never`; `--loop` solo demo local | FR-DISC-03 + stories "CronJob/Job"; `Forbid` evita solapes; deadline > timeout máximo (3600 s sería excesivo — 600 cubre el ciclo de lab con margen; subir si U11 lo pide); deployment con loop contradice las stories (Q2=A) |
| ID-U4-03 | Resources del worker = **los del Core** (requests 100m/128Mi → limits 500m/512Mi) | Ciclo breve acotado por deadline de fases; cap 1000 targets; pico de nmap a validar en U11 y subir solo si hace falta (Q3=A) |
| ID-U4-04 | SecurityContext **non-root, sin capabilities** | NFR-U4-SEC-03; si el kernel no permite ICMP a non-root, la fase ICMP se omite con warning (D-U4-05) y ARP/TCP/nmap cubren el descubrimiento; la excepción "sensor capabilities" de SEC-02 queda sin usar en lab (Q4=A) |
| ID-U4-05 | **Requisito de egress documentado aquí**, implementado en U9/U10: DNS + `sentinel-core:8080` + rangos de `scope.*` (allowlist de `values.yaml`) | El default-deny de U10 mataría el escaneo en silencio; la política se deriva de la misma allowlist que el worker (coherencia); sin política el worker queda con egress abierto (Q5=A) |
| ID-U4-06 | Observabilidad = **solo logs JSON a stdout** + vitalidad por observaciones exitosas (heartbeat `sensor-0`) y `kubectl get cronjob/jobs` | FQ1=C rechaza canal/métrica de fallos; consistente con ST-M2-06 (fallo no parece "red sin activos" — se ve en logs del Job); reintroducir heartbeat en fallo violaría FQ1=C (Q6=A) |
| ID-U4-07 | Config **solo por env** (`values.yaml` → `SENTINEL_DISCOVERY_*` en el CronJob y en el Core; token desde el Secret heredado) | El loader estricto lee env (TS-U4-04); ConfigMap añadiría una pieza sin consumidor; U2 no usa ConfigMap (Q7=A) |
| ID-U4-08 | Worker **sin Service, puerto, probe, ServiceMonitor ni PVC**; namespace `sentinel` y ServiceAccount heredados de U2 | El worker solo hace egress; exponerlo no aporta; nada que health-checkear desde el Service (Q6=A + evaluación de categorías) |
| ID-U4-09 | Imagen **única compartida** Core+worker (`sentinel:test`): mismo artefacto, distinto command | Una imagen versionada con todo el código; el worker no necesita capas distintas (Q1=A implícito) |
| ID-U4-10 | Ediciones acotadas de U2 (FD §4) se despliegan **en el Deployment existente** de U2 — cero objetos K8s nuevos por U4 | La API (scope 400, reconcile, counters) corre en el Core; el chart no cambia hasta U9 |

---

## 3. Especificación de cambios (único artefacto construido en U4)

### 3.1 Dockerfile (edición acotada heredada de U1 — Q1=A)

```dockerfile
# … bloques existentes de U1/U2 intactos …
RUN apk add --no-cache nmap
# … COPY de src/ …
```

- `ping` e `ip` (para `ip neigh`) ya los aporta busybox en Alpine — sin paquetes extra.
- Si la capa se omite, `SENTINEL_DISCOVERY_SCANNER=auto` cae a fixtures y los tests siguen verdes (D-U4-05) — la demo real sí exige la capa.
- Sin cambios de stage, usuario ni entrypoint de U1.

### 3.2 Manifiestos K8s — CronJob nuevo en U9 (especificación recibida aquí)

| Campo | Valor (Q2=A) | Nota |
|---|---|---|
| `kind` / `schedule` | `CronJob` / `*/15 * * * *` | Alineado al default `INTERVAL_MIN=15` |
| `concurrencyPolicy` | `Forbid` | Evita ciclos superpuestos (sin dedup cross-proceso) |
| `activeDeadlineSeconds` | `600` | > timeout de ciclo de lab (30 s default); si U11 sube `TIMEOUT_SECONDS`, subir en paralelo |
| `backoffLimit` / `restartPolicy` | `3` / `Never` | Fallo ⇒ log + exit 1, reintento del Job (P1) |
| `command` / `args` | `python -m sentinel.discovery` / `["--once"]` | TS-U4-06 |
| `resources` | `100m/128Mi` → `500m/512Mi` | ID-U4-03 |
| `securityContext` | `runAsNonRoot: true`, sin `capabilities` | ID-U4-04 |
| Deployment/Service/PVC/Secret/ServiceMonitor de U2 | **Idénticos** | + env `SENTINEL_DISCOVERY_*` añadidas al Core (D-U4-04) |

### 3.3 Manifiestos de U2 — sin cambios de objeto

Deployment `sentinel-core`, Service, PVC, Secret, ServiceMonitor **idénticos**; solo se **añaden env** (`SENTINEL_DISCOVERY_*`) al contenedor Core cuando U9 lo monte (D-U4-04).

---

## 4. Entradas para `values.yaml` de U9

| Clave propuesta (U9) | env del worker (y del Core) | Default (FD §3.1) | Restricción |
|---|---|---|---|
| `discovery.scope.mode` | `SENTINEL_DISCOVERY_SCOPE_MODE` | `explicit_hosts` | `cidr \| explicit_hosts` |
| `discovery.scope.hosts` | `SENTINEL_DISCOVERY_HOSTS` | `""` | **no vacía** (fail-fast BR-U4-02) |
| `discovery.scope.cidrs` | `SENTINEL_DISCOVERY_CIDRS` | `""` | requerida si modo `cidr` |
| `discovery.scope.ports` | `SENTINEL_DISCOVERY_PORTS` | `22,80,443` | 1..65535 sin duplicados |
| `discovery.intervalMinutes` | `SENTINEL_DISCOVERY_INTERVAL_MIN` | `15` | ≥ 1 (solo `--loop`) |
| `discovery.timeoutSeconds` | `SENTINEL_DISCOVERY_TIMEOUT_SECONDS` | `30` | 1..3600 |
| `discovery.scanner` | `SENTINEL_DISCOVERY_SCANNER` | `auto` | `auto \| nmap \| fixtures` |
| `discovery.nmapArgs` | `SENTINEL_DISCOVERY_NMAP_ARGS` | `""` | whitelist (BR-U4-10/11) |
| `ingest.token` (Secret heredado) | `SENTINEL_INGEST_TOKEN` | — | Bearer del `POST /ingest` |
| `discovery.schedule` (U9) | — (campo CronJob) | `*/15 * * * *` | schedule del CronJob (ID-U4-02) |

Además U9/U10: crear el CronJob (§3.2) y la NetworkPolicy de egress del worker (ID-U4-05: DNS + `sentinel-core:8080` + CIDRs de `discovery.scope.*`).

---

## 5. Recursos consumidos por U4

| Recurso | Propiedad | Coste/mantenimiento |
|---|---|---|
| Objeto K8s nuevo | **1 CronJob** (creado en U9) | Un pod de lab cada 15 min, efímero |
| CPU/RAM worker | Propia del Job (100m/128Mi→500m/512Mi) | Pico de nmap a validar en U11 |
| Tamaño de imagen | +`nmap` (~tens de MB en la cap apk) | Build local algo más lento |
| Disco | **Cero** (sin PVC nuevo, worker stateless) | Nada que purgar |
| Red | Egress: DNS + 8080 + LAN (allowlist) | 1 POST por ciclo al Core; sin puertos nuevos |
| Estado en Core | Ediciones acotadas U2 (FD §4) en el Deployment existente | Cero objetos nuevos hasta U9 |

---

## 6. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
