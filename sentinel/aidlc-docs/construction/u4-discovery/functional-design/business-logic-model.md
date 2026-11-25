# Business Logic Model — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-16
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U4 — `src/sentinel/discovery/` (config, scope C12, scanner, worker, cliente de ingesta, runner)
**Plan de preguntas**: `construction/plans/u4-discovery-functional-design-plan.md` (Q1–Q16 = A) + **FQ1 = C** (sin reporte de fallos standalone; ver D-U4-01)
**Entradas**: ST-M1-01..04, ST-M2-01..06, FR-DISC-01..06, NFR-TECH-03, `services.md` §2.1/§2.2/§4, `component-methods.md` §7/§8, contratos U1+U2 aprobados.

---

## 1. Propósito y frontera

U4 construye el **colector de descubrimiento**: configura el alcance autorizado (C12), sondea ARP/ICMP/TCP + Nmap ligero sobre la allowlist, normaliza los hallazgos y los envía por HTTP al Core; además aporta el `CycleRunner` real que U2 inyecta en `POST /api/v1/discovery`.

- **Hace**: loader de config `SENTINEL_DISCOVERY_*` (fail-fast), validación de alcance/puertos/métodos (worker y API), orquestación del ciclo con deadline, escaneo por fases con escáner intercambiable (nmap real / fixtures), fusión de hallazgos en `DiscoveryObservation`, ingesta por HTTP con reintento, manejo de fallos de ciclo (log + contadores en runs vía API), CLI `--once`/`--loop`.
- **No hace** (frontera): **nunca abre SQLite** ni importa `sentinel.core.*` (solo `foundation` + HTTP, `unit-of-work.md` §imports); no evalúa condiciones ni alertas; no escanea fuera de la allowlist; no ejecuta `-O/-sU/-sS/-sC/--script/-A` (FR-DISC-02); no reconcilia inventario (U2 `InventoryService`); no emite `PortServiceChanged` ni SNMP (documented-only); no define Helm values (U9 los mapeará a estas env).
- **Depende de**: U2 aprobado — `POST /api/v1/ingest` (Bearer token), `POST/GET /api/v1/discovery` + `DiscoveryTrigger` (protocolo `CycleRunner.run(hosts, timeout_seconds) -> hosts_seen`, timeout ⇒ `DiscoveryTimeoutError`, otro error ⇒ `failed`), handler 400 `scope_violation` (hoy sin trigger), `foundation.retry.with_retries`, `foundation.models.DiscoveryObservation`.

---

## 2. Componentes lógicos

| Componente | Módulo | Responsabilidad |
|---|---|---|
| `DiscoverySettings` (C12 cfg) | `discovery/config.py` | Loader propio de `SENTINEL_DISCOVERY_*` (patrón `foundation.config`): fail-fast `ConfigError`, defaults de lab (Q10=A), valida puertos y flags de escaneo al cargar |
| `ScopeValidator` (C12) | `discovery/scope.py` | `validate_scope(mode, hosts, cidrs)`, `validate_ports(ports)`, `validate_target(target)` → `ValidationResult` (`component-methods.md` §8) |
| Dominio puro | `discovery/domain.py` | `ScopeConfig`, `ScanTarget`, `HostFinding`, `CycleResult`, `CycleStatus` — sin I/O (Q11=A) |
| Escáner | `discovery/scanner.py` | Protocolo `Scanner`; `NmapScanner` (binario + `ip neigh` + `ping` + TCP connect stdlib), `FixtureScanner` (XML/ARP fixtures), `build_nmap_argv` + `validate_scan_options` (Q3=A, Q9=A) |
| Worker de ciclo | `discovery/worker.py` | Orquesta fases con deadline (arp→icmp→tcp→nmap), fusiona hallazgos, decide `reconcile` del lote, calcula `hosts_seen` |
| Cliente de ingesta | `discovery/client.py` | `POST /api/v1/ingest` con Bearer `SENTINEL_INGEST_TOKEN` + `with_retries` (Q5=A) |
| Runner (puente U2) | `discovery/runner.py` | `CycleRunnerImpl` que satisface el protocolo `CycleRunner`: levanta `ScopeError`/`DiscoveryTimeoutError`/errores ⇒ `DiscoveryTrigger` los mapea a `failed`/`timeout` |
| CLI | `discovery/__main__.py` | `python -m sentinel.discovery --once` \| `--loop --interval <min>` (Q4=A) |
| Contadores de ciclo | U2 (edición acotada) | `CycleCounter` en `core/metrics/collect.py`; `DiscoveryTrigger` incrementa al finalizar; familia nueva `sentinel_discovery_cycles_failed_total` (Q8=A) |

```mermaid
flowchart LR
  subgraph U4["U4 src/sentinel/discovery/ (nuevo)"]
    CFG[config.py DiscoverySettings] --> SCOPE[scope.py C12]
    SCOPE --> WK[worker.py ciclo]
    WK --> SC["scanner.py (Nmap o Fixture)"]
    WK --> DOM[domain.py Hallazgos]
    WK --> CLI[client.py ingesta HTTP]
    RUN[runner.py CycleRunnerImpl] --> WK
    MAIN[__main__.py --once|--loop] --> WK
  end
  APP["U2 create_app (lazy import)"] -. inyeccion .- RUN
  CLI -->|"POST /ingest (items + reconcile)"| API["U2 Core 8080"]
  TRG["U2 DiscoveryTrigger"] -->|"contador + log discovery_cycle_failed"| MET["metrics 9108"]
  APP --> TRG
```

---

## 3. Flujos

### 3.1 Arranque y configuración (fail-fast, Q2=A, Q10=A)

```text
load_discovery_settings(environ)  →  DiscoverySettings (frozen, extra=forbid)
  SENTINEL_DISCOVERY_SCOPE_MODE      default "explicit_hosts"   (cidr | explicit_hosts)
  SENTINEL_DISCOVERY_HOSTS           default ""  (lista explícita, comma-separated)
  SENTINEL_DISCOVERY_CIDRS           default ""  (rangos, comma-separated)
  SENTINEL_DISCOVERY_PORTS           default "22,80,443"
  SENTINEL_DISCOVERY_INTERVAL_MIN    default 15                 (solo --loop)
  SENTINEL_DISCOVERY_TIMEOUT_SECONDS default 30                 (solo --once / runner)
  SENTINEL_DISCOVERY_SCANNER         default "auto"             (auto | nmap | fixtures)
  SENTINEL_DISCOVERY_NMAP_ARGS       default ""                 (extra args, whitelist)
  validation: mode válido; allowlist no vacía según modo
              (explicit_hosts ⇒ HOSTS ≠ ∅ ; cidr ⇒ CIDRS ≠ ∅)
              puertos 1..65535; validate_scan_options(NMAP_ARGS)
  cualquier violación ⇒ ConfigError (fail-fast, nada se sondea)
```

- `SENTINEL_INGEST_TOKEN` (clave de U2) se **lee** en el cliente de ingesta para el Bearer; `CoreSettings` de U1 **no cambia** (sigue con exactamente 4 claves `SENTINEL_*`, BR-06 intacto) — Q2=A.
- El proceso Core (API) puede cargar el **mismo** loader para construir su validador de scope (§3.2): las env son idénticas en Deployment y CronJob porque U9 las derivará del mismo `values.yaml`.

### 3.2 Validación de alcance — C12 (Q1=A: worker **y** API)

```text
validate_target(t):
  mode=explicit_hosts → t ∈ HOSTS (match exacto, normalizado)
  mode=cidr            → IP(t) ∈ alguno de CIDRS
  fuera ⇒ ValidationResult(ok=False) / ScopeError("host fuera de alcance")

Ruta A — worker (siempre, defensa en profundidad):
  antes de la fase de sondeo, cada target pasa por validate_target
  ⇒ ScopeError + log event="scope_violation" + event="discovery_cycle_failed"
    (cause="scope_violation"); SIN enviar paquetes; exit 1 (standalone)
    o excepción ⇒ run failed (in-process, el runner la propaga)

Ruta B — API (solo si el proceso Core tiene config de scope):
  POST /api/v1/discovery → por cada host validate_target
  ⇒ ScopeError → 400 {"code":"scope_violation"} ANTES de crear el run
    (handler ya existe en U2; hoy nadie lo levanta — IP4 cerrada aquí)
  ⇒ sin config de scope en el proceso ⇒ la API omite esta validación
    (la garantía la da la Ruta A; evita romper arranque/tests de U2 — D-U4-04)
```

### 3.3 Ciclo de descubrimiento — fases con deadline (Q6=A, ST-M2-01/02)

```text
run_cycle(settings, scanner, ingest, timeout_seconds) -> CycleResult
  deadline = monotonic() + timeout_seconds
  targets  = resolve_targets(settings)            # IPs canónicas (hosts o expansión de cidrs)
  1. ARP   : scanner.arp_neighbors() (ip neigh / arp -a) filtrado por allowlist
             → HostFinding(ip, mac, method="arp")
  2. ICMP  : por target con deadline restante: ping -c 1 -W 1 (binario con caps; sin root)
             → respuesta ⇒ HostFinding(method="icmp")            (si falta `ping`: fase omitida + warning)
  3. TCP   : connect stdlib (timeout corto) a puertos allowlist por target vivo
             → puerto abierto ⇒ HostFinding(method="tcp", ports=[...])
  4. Nmap  : si el scanner lo soporta y hay targets vivos:
             argv = build_nmap_argv(...) → validate_scan_options(argv)
             → nmap -sT -sV --version-light -p <csv> -oX - <targets>
             → parse XML (PBT con hypothesis, NFR-TECH-03) → merge en hallazgos
  si monotonic() > deadline en cualquier fase → status="timeout", partial=True, cortar
  hosts_seen = nº de hallazgos fusionados con ≥1 indicio   (Q16=A)
  ingesta según §3.5 → CycleResult(status, hosts_seen, findings, error)
```

- **Fusión por host (1 `DiscoveryObservation` por host por ciclo)** — D-U4-07: método preponderante `nmap > tcp > icmp > arp`; puertos combinados (servicio/versión de nmap gana sobre el `state` del TCP connect); `hostname` solo si el escáner lo reporta (fixtures/XML), nunca reverse-DNS propio.
- `os_name` siempre `None` con `os_provenance="unknown"`: `-O` está prohibido (FR-DISC-02) — D-U4-06.
- El timeout de la ruta in-process lo define la request (`DiscoveryRequest.timeout_seconds`, default 30); el runner respeta su **propio** deadline e ingiere los parciales **antes** de lanzar `DiscoveryTimeoutError` (así `DiscoveryTrigger` marca `timeout` y el lote parcial ya está en el Core).

### 3.4 Escáner intercambiable (Q3=A, Q9=A)

| Escáner | Cuándo | Detalle |
|---|---|---|
| `NmapScanner` | `SCANNER=auto` con binario `nmap` disponible, o `SCANNER=nmap` | argv **construido programáticamente** (nunca string crudo del usuario): `["nmap","-sT","-sV","--version-light","-p",csv,"-oX","-", *targets]` + `NMAP_ARGS` solo si pasa la whitelist; ARP vía tabla del sistema; ICMP vía `ping`; TCP vía stdlib |
| `FixtureScanner` | `SCANNER=fixtures`, tests, o fallback de `auto` cuando falta el binario | Lee XML nmap + tabla ARP de fixtures; mismo pipeline aguas abajo |
| `auto` (default) | `shutil.which("nmap")` ⇒ NmapScanner; si no ⇒ FixtureScanner + `log warning event="scanner_fallback"` | nunca falla el ciclo por falta del binario — D-U4/§3.4 |

- `validate_scan_options(argv)` (whitelist): rechaza `-O`, `-sU`, `-sS`, `-sC`, `--script*`, `-A` y cualquier flag fuera de lista ⇒ `ConfigError` al cargar la config o `ValidationError` antes de ejecutar (ST-M1-02 AC2, ST-M2-02 AC2).

### 3.5 Ingesta del lote (Q5=A, Q7=A)

```text
al finalizar el ciclo:
  status=completed      → items = observaciones fusionadas; reconcile=true
  status=timeout|partial→ items = parciales acumulados;     reconcile=false
  status=failed         → SIN lote (nada que conservar / ScopeError / escáner caído)

POST /api/v1/ingest
  headers: Authorization: Bearer SENTINEL_INGEST_TOKEN
  body   : {"items": [DiscoveryObservation...], "reconcile": <bool>}   ← edición acotada de Batch (U1)
  retry  : with_retries(fn, attempts=5, base_delay=0.5, jitter, retry_on=(errores de red/5xx))
           backoff exponencial ± jitter (BR-23 U1)
  si se agotan los reintentos ⇒ IngestionError ⇒ status="failed" con causa   (D-U4-03)
```

- `reconcile=false` ⇒ U2 persiste observaciones y actualiza `last_seen` **sin** ejecutar `reconcile_missing` ⇒ un ciclo parcial/timeout jamás incrementa `miss_count` (cierra literal ST-M2-04 AC2 / BR-U2-15, hoy incumplible desde U4).
- `reconcile=true` (completed) ⇒ `InventoryService` emite `asset_first_seen` / `asset_missing` tal como aprobó U2 (frontera Q12=A: U4 no toca inventario).

### 3.6 Estados del ciclo y manejo de fallos (Q8=A, FQ1=C)

```mermaid
stateDiagram-v2
    [*] --> running
    running --> completed: sin exceder deadline + ingest reconcile=true OK
    running --> timeout: deadline excedido, parciales ingeridos reconcile=false
    running --> failed: scope_violation / error de escáner / ingest agotado
    completed --> [*]
    timeout --> [*]
    failed --> [*]
```

**Ruta in-process (POST /discovery, manual/GUI):**

```text
DiscoveryTrigger._execute (U2, edición acotada):
  al finalizar el run:
    CycleCounter.record(status)   → cycles_total (todo run) + failed_total (failed|timeout)
    failed|timeout ⇒ log info event="discovery_cycle_failed" run_id=… cause=…
  collect() expone ambas familias en /metrics (9108) — valores reales desde U4, U7 sigue el contrato
```

**Ruta standalone (`--once` / CronJob U9) — FQ1=C (decisión del usuario 2026-11-16):**

```text
al finalizar el ciclo:
  completed            → exit 0
  timeout | failed     → log local event="discovery_cycle_failed" + cause
                         (scope_violation | timeout | scanner_error | ingestion_error)
                         exit 1  (el Job aparece fallido en kubectl)
  SIN reporte HTTP al Core ⇒ failed_total solo cubre runs vía API   (D-U4-01)
```

- **Nunca `AssetMissing` por fallo**: failed ⇒ sin lote; partial/timeout ⇒ `reconcile=false` (§3.5) ⇒ cumple ST-M2-04 AC2 y ST-M2-06 AC1.

### 3.7 CLI y programación (Q4=A, FR-DISC-03)

| Modo | Uso | Detalle |
|---|---|---|
| `--once` | CronJob de U9, tests, demo manual | 1 ciclo con `SENTINEL_DISCOVERY_TIMEOUT_SECONDS`; exit 0/1 según §3.6 |
| `--loop [--interval N]` | demo sin chart (laptop) | duerme `INTERVAL_MIN` (default 15) entre ciclos; SIGTERM limpia entre ciclos |

- Ambos modos comparten `run_cycle` (mismo worker que el runner in-process — `component-methods.md` §7: "invoca el mismo módulo que usa el CronJob").

### 3.8 Composición del runner en la API (Q15=A)

```text
create_app(..., runner=None):
  if runner is None:
      try: from sentinel.discovery.runner import CycleRunnerImpl
           runner = CycleRunnerImpl()          # lazy, igual que el bloque try/except de gui
      except ImportError: runner = None        # ⇒ 503 runner unavailable (comportamiento U2 actual)
  app.state.discovery = DiscoveryTrigger(db, runner=runner)
```

- Dirección **core→discovery** aceptada como *composición de arranque* (el colector sigue sin importar `core`); GT-02 funciona con la imagen estándar; los tests inyectan `runner=` con escáner fixture.

---

## 4. Ediciones acotadas a unidades aprobadas

| Archivo | Edición | Por qué (pregunta) |
|---|---|---|
| `foundation/models.py` — `Batch` | `+ reconcile: bool = True` (retrocompatible) | Q7=A |
| `foundation/metrics_contract.py` — `METRIC_FAMILIES` | `+ "sentinel_discovery_cycles_failed_total"` | Q8=A |
| `core/ingestion/service.py` | `if has_discovery and batch.reconcile:` | Q7=A |
| `core/api/routes_discovery.py` | validación `ScopeError` pre-run + log `scope_violation` | Q1=A |
| `core/api/app.py` | scope_validator opcional + runner lazy + `CycleCounter` | Q1/Q8/Q15 |
| `core/discovery/trigger.py` | `CycleCounter` + log `discovery_cycle_failed` | Q8=A |
| `core/metrics/collect.py` | `CycleCounter` + samples de `cycles_total`/`cycles_failed_total` | Q8=A |

---

## 5. Decisiones y desviaciones

| ID | Decisión / desviación | Origen |
|---|---|---|
| D-U4-01 | **FQ1=C**: los fallos del ciclo standalone solo se loguean en el Job (`kubectl logs`); `sentinel_discovery_cycles_failed_total` y `cycles_total` cubren **únicamente** runs vía API. ST-M2-06 AC2 se verifica con un fallo vía API. Aceptado por el usuario ("lo importante es el reporte del tráfico de red") | FQ1=C, 2026-11-16 |
| D-U4-02 | Los logs de eventos usan los valores **canónicos snake_case** de `EventType` (`discovery_cycle_failed`, `asset_first_seen`); las AC en prosa citan nombres display (`DiscoveryCycleFailed`, `AssetFirstSeen`) — los tests GT afirman el canónico (consistente con U1/U2 aprobados) | U1 EventType, U2 evidencia |
| D-U4-03 | Reintentos de ingesta acotados por `with_retries` (attempts=5, BR-23 U1); si se agota ⇒ ciclo `failed`. `services.md` "hasta lograrlo" queda cubierto dentro del presupuesto de reintentos de U1 | Q5=A, foundation.retry |
| D-U4-04 | Validación de scope en la API es **condicional** (solo si el proceso Core tiene `SENTINEL_DISCOVERY_*`): evita 400 masivos en los tests existentes de U2 y permite arrancar el Core standalone; U9 inyecta las env en ambos workloads | Q1+Q2, compatibilidad U2 |
| D-U4-05 | ICMP echo vía binario `ping` (caps de red sin root); si falta el binario ⇒ fase omitida con warning (ARP/TCP siguen cubriendo el hallazgo) | FR-DISC-01 + non-root |
| D-U4-06 | `os_name=None` / `os_provenance="unknown"` en el MVP: `-O` prohibido ⇒ sin detección de SO por nmap | FR-DISC-02 |
| D-U4-07 | **1 observación fusionada por host por ciclo** (método preponderante `nmap>tcp>icmp>arp`), consistente con `tests/fixtures/observations.json` y con el dedup de U2 | Q11, fixtures U2 |
| D-U4-08 | **Documented-only sin código**: ST-M1-03 (`sensor_id` configurable ⇒ U9; default `sensor-0`), ST-M1-04 (SNMP), ST-M2-05 (`PortServiceChanged` ⇒ reconciliación futura de U2) | `unit-of-work.md` §U4, Q13/Q14 |

---

## 6. Cobertura de historias

| Historia | Estado en U4 | Nota |
|---|---|---|
| ST-M1-01 Helm-configurable scope/scheduling | implementada | loader `SENTINEL_DISCOVERY_*` + `--interval`; `helm template/lint` se verifica en U9 (Build & Test) |
| ST-M1-02 Validación de alcance | implementada | §3.2 (worker + API) + `validate_scan_options` |
| ST-M1-03 `sensor_id` reservado | documented-only | default `sensor-0` del modelo U1 (D-U4-08) |
| ST-M1-04 SNMP opcional | documented-only | extensión futura (D-U4-08) |
| ST-M2-01 Descubrimiento periódico | implementada | §3.3 + §3.7; Job de U9 en Build & Test |
| ST-M2-02 Sondeo ligero de servicios | implementada | §3.4 (`-sT -sV --version-light`, PBT XML) |
| ST-M2-03 `AssetFirstSeen` | implementada | frontera Q12=A: lo emite U2 ante el primer lote (test GT-02 end-to-end) |
| ST-M2-04 `AssetMissing` tras N ciclos | implementada | §3.5 `reconcile` + U2 (test GT-03, `-k partial_cycle`) |
| ST-M2-05 Cambio puerto/servicio | documented-only | D-U4-08 |
| ST-M2-06 Fallo de ciclo | implementada | §3.6 (log + métrica en API; log local en standalone — D-U4-01) |
