# Business Logic Model — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-18
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/` (config, fuente de paquetes, agregación de ventanas, ARP, export, CLI)
**Plan de preguntas**: `construction/plans/u5-traffic-functional-design-plan.md` (Q1–Q13 = A, sin FQ)
**Entradas**: ST-M3-01..06 (todas documented-only), FR-TRAF-01..05, FR-ARP-01..04, NFR-AVAIL-01, NFR-SEC-02, NFR-TECH-02, `services.md` §2.1/§4/health, `component-methods.md` §11/§36, `components.md` (C10), `implementation-scope.md` (M3), `demo-plan.md` (GT-04/GT-05), contratos U1+U2 aprobados.

---

## 1. Propósito y frontera

U5 construye el **colector de tráfico/ARP**: lee eventos de una fuente de paquetes abstracta (simulada en el MVP; real documentada), los agrega en ventanas tumbling, calcula la tasa de mensajes ARP, parsea ARP request/reply y envía los agregados por HTTP al Core; sus observaciones con `sensor_id` son el **heartbeat de disponibilidad** que U6/U8 consumen.

- **Hace**: loader `SENTINEL_TRAFFIC_*` (fail-fast), fuente abstracta `PacketSource` + `SimulatedSource` determinista (fixtures/generador), agregación por ventanas (1/5/10/30/60 s), parseo ARP (opcode 1/2), tasa ARP por ventana (función pura + log), cliente de export con reintento, CLI `--once`/`--loop`.
- **No hace** (frontera): **nunca abre SQLite** ni importa `sentinel.core.*` (solo `foundation` + HTTP); no evalúa umbrales ni alertas; no expone `/metrics` propio; no persiste eventos ni inventario (U2 ya detecta `ARP_MAPPING_CHANGED`); no almacena payload/MAC/puerto de tráfico IP (FR-TRAF-03); no modifica paquetes; no define Helm values (U9 los mapeará); **sin código de captura real** (AF_PACKET documentado, Q3=A).
- **Depende de**: U1 aprobado (`TrafficObservation`, `ArpObservation`, `Batch`, `with_retries`, `ConfigError`), U2 aprobado (`POST /api/v1/ingest` Bearer + dedup UUIDv5, `HealthService.sensor_heartbeats`, `InventoryService.observe` → `arp_mapping_changed`).
- **Alcance construido**: fuente abstracta + fallback simulado/fixtures (GT-04/GT-05); historias ST-M3-01..06 **documented-only** — el simulador/fixtures es código de soporte de la unidad (`unit-of-work.md` §U5).

---

## 2. Componentes lógicos

| Componente | Módulo | Responsabilidad |
|---|---|---|
| `TrafficSettings` | `traffic/config.py` | Loader propio de `SENTINEL_TRAFFIC_*` (patrón `foundation.config`): fail-fast `ConfigError`, ventana ∈ {1,5,10,30,60} (Q2=A) |
| Fuente abstracta | `traffic/source.py` | Protocolo `PacketSource` → eventos tipados `IpPacket \| ArpPacket`; `SimulatedSource` (seed + rate + fixtures, Q3/Q13=A); `FixtureSource` replay de JSON versionado |
| Agregador | `traffic/aggregator.py` | Ventanas tumbling epoch-aligned; acumuladores por (ventana × interfaz × protocolo); proyección a `TrafficObservation` (Q4/Q5=A) |
| Dominio ARP | `traffic/arp.py` | Parseo de eventos ARP → `ArpObservation`; `arp_rate(count, window_seconds)` función pura (Q10=A); **sin estado de mapping** (delegado a U2, Q11=A) |
| Worker | `traffic/worker.py` | Ciclo: source → ventana → cierre → log `arp_rate` → export; reintentos y descarte de ventana (Q9=A); reloj inyectable (tests sin sleep) |
| Cliente de export | `traffic/client.py` | `POST /api/v1/ingest` espejo de U4 (Bearer `SENTINEL_INGEST_TOKEN`, `with_retries` ×5, base `SENTINEL_API_BASE`) (Q7/Q8=A) |
| CLI | `traffic/__main__.py` | `python -m sentinel.traffic --once` \| `--loop` (Q12=A) |
| Captura real | **sin código** | `AfPacketSource` (scapy/AF_PACKET) solo documentado en §5 (Q3=A) |

```mermaid
flowchart LR
  subgraph U5["U5 src/sentinel/traffic/ (nuevo)"]
    CFG[config.py TrafficSettings] --> WK[worker.py ciclo ventana]
    SRC["source.py PacketSource<br/>(Simulated / Fixture)"] --> WK
    WK --> AGG[aggregator.py ventanas]
    WK --> ARP[arp.py parseo + arp_rate]
    AGG --> CLI[client.py POST /ingest]
    ARP --> CLI
    MAIN[__main__.py --once|--loop] --> WK
  end
  CLI -->|"Batch mixto (traffic+arp), Bearer"| API["U2 Core 8080 /api/v1/ingest"]
  API -. sensor_heartbeats MAX observed_at .- HS["U2 HealthService"]
  API -. observe hwsrc changed .- INV["U2 InventoryService → arp_mapping_changed"]
  WK -. log event=arp_rate .- LOG["kubectl logs (sensor)"]
```

---

## 3. Flujos

### 3.1 Arranque y configuración (fail-fast, Q2=A)

```text
load_traffic_settings(environ)  →  TrafficSettings (frozen, extra=forbid)
  SENTINEL_TRAFFIC_WINDOW_SECONDS  default 5      ∈ {1,5,10,30,60}  else ConfigError
  SENTINEL_TRAFFIC_INTERFACE       default "eth0" (no vacío)
  SENTINEL_TRAFFIC_SENSOR_ID       default "sensor-0"
  SENTINEL_TRAFFIC_SIM_SEED        default 42     (entero ≥ 0)
  SENTINEL_TRAFFIC_SIM_RATE        default 50.0   (paquetes/s, > 0)
  SENTINEL_TRAFFIC_FALLBACK        default "true" (false ⇒ ConfigError:
                                       captura real documentada, no implementada)
  SENTINEL_API_BASE                default "http://127.0.0.1:8080"  (clave U2/U4)
  SENTINEL_INGEST_TOKEN            (clave U2, leída sin redefinir)
  cualquier violación ⇒ ConfigError (fail-fast; nada se captura)
```

- `CoreSettings` de U1 **no cambia** (sigue con exactamente 4 claves `SENTINEL_*`, BR-06 intacto) — análogo a BR-U4-04.
- La ventana inválida se rechaza **en el loader** (ST-M3-02 AC2; el `helm lint --set traffic.window=7s` se verifica en U9/Build & Test con este mismo validador detrás del value).

### 3.2 Fuente de paquetes abstracta (Q3=A, Q13=A)

```text
PacketSource (protocolo)
  events() -> Iterator[IpPacket | ArpPacket]

IpPacket  : observed_at, interface, protocol(tcp|udp|icmp|other),
            src_ip, dst_ip, packet_length_bytes     (IPv4, sin MAC/puerto/payload)
ArpPacket : observed_at, interface, opcode(1|2), psrc, pdst, hwsrc, hwdst

SimulatedSource (implementado — única fuente en el MVP)
  · determinista: misma (SIM_SEED, SIM_RATE, fixtures) ⇒ misma secuencia de eventos
  · IP: a SIM_RATE paquetes/s; protocolo cicla tcp→udp→icmp→other (trasiego fijo del seed);
    pares src/dst de tablas fijas; length en rango determinista
  · ARP: 1 mensaje por segundo simulado, alterna opcode 1/2, IPs/MACs de tabla fija
  · GT-04 = subir SIM_RATE vía env (trafico alto reproducible)
  · replay: FixtureSource lee tests/fixtures/traffic_*.json (secuencias exactas
    para mapping-change, rate, minimal_fields)

AfPacketSource — SOLO DOCUMENTADO (§5; sin código, sin scapy en requirements)
```

- **Solo IPv4 en MVP** (PRD §3.2 `total_length`); IPv6 queda documentado como extensión (D-U5-03).
- FR-TRAF-03: del paquete IP solo se extraen `observed_at, protocol, src_ip, dst_ip, packet_length_bytes, interface, sensor_id` — MAC/puerto/payload **no se extraen**; los contratos U1 son `extra="forbid"` ⇒ imposible transportar payload.

### 3.3 Ventanas de agregación (Q4=A, Q5=A)

```text
al arrancar (o al despertar de --loop):
  W      = settings.window_seconds
  ahora  = reloj()
  window_start = floor(ahora / W) * W          # tumbling alineada al reloj
  window_end   = window_start + W
  acumular eventos de la fuente hasta window_end (reloj inyectable en tests)
  al cerrar la ventana:
    si hay ≥1 paquete en la interfaz:
      por cada protocolo con ≥1 paquete (tcp|udp|icmp|other):
        TrafficObservation{window_start, window_end, interface, protocol,
          packet_length_bytes = Σ length,
          bytes_per_second    = Σ length / (window_end − window_start),
          packets             = nº paquetes,
          flows               = nº pares src-dst distintos (total),
          pairs               = hasta 100 pares (orden: packets desc, src asc, dst asc),
          window_id           = uuid5(sensor_id|window_start|interface|protocol),
          sensor_id, observed_at = window_end}
    si la ventana NO tiene paquetes en la interfaz:
      1 sola TrafficObservation cero con protocol="other",
      packets=0, bytes_per_second=0.0, pairs=[]   ← heartbeat (D-U5-01)
  siempre: log event="arp_rate" interface=… arp_messages_per_second=arp_rate(n, W)
  exportar §3.5; repetir
```

- **Toda ventana se emite** (con o sin paquetes): las observaciones **son el heartbeat** (Q4/Q6=A) — red idle ≠ sensor caído; **GT-05 = detener el loop**.
- La observación cero lleva `pairs=[]` ⇒ `_ip_of` ⇒ `asset_id=None` en U2 ⇒ **no vincula a activos** ⇒ BR-U3-07 ("activos sin tráfico ⇒ sin datos", cero inventado) **queda intacto** (D-U5-01).
- `bytes_per_second` sobre la duración efectiva (`window_end − window_start` = W) — ST-M3-02 AC1: 25 s @ 5 s ⇒ 5 ventanas.
- Agrupación por (ventana × interfaz × protocolo): el modelo U1 tiene `protocol` singular (D-U5-02).

### 3.4 ARP: parseo, tasa y tracking delegado (Q10=A, Q11=A)

```text
por cada ArpPacket de la ventana:
  ArpObservation{observed_at, sensor_id, source="arp", interface,
                 opcode ∈ {1,2}, psrc, pdst, hwsrc, hwdst}   ← U1, sin cambios

al cierre de la ventana:
  n = nº ArpObservation de la ventana en la interfaz
  rate = arp_rate(n, W) = n / W            # función pura, testeable
  log info event="arp_rate" interface=… window_start=… arp_messages_per_second=rate
  # ST-M3-05 AC1: n=100, W=10 ⇒ 10.0

tracking IP↔MAC: DELEGADO a U2 (ya generado)
  el sensor NO mantiene mapa local; exporta ArpObservation crudas
  U2 InventoryService.observe(hwsrc) detecta mac_changed ⇒ evento arp_mapping_changed
  (ST-M3-04/06 se verifica con integration test de ingest con MAC cambiado)
  R-02 (documented-only, U8): U7 expondrá sentinel_arp_messages_total
  ⇒ PromQL rate() sobre la familia ya definida en U1 (sin cambio de modelos)
```

### 3.5 Export al Core (Q7=A, Q8=A, Q9=A)

```text
al cerrar cada ventana:
  items = [TrafficObservation…] + [ArpObservation…] de esa ventana   # lote mixto
  POST /api/v1/ingest                     ← endpoint existente de U2 (sin editar U2)
    headers: Authorization: Bearer SENTINEL_INGEST_TOKEN
    body   : {"items": [...]}             # reconcile omitido (default; no hay discovery)
    retry  : with_retries(attempts=5, base_delay=0.5, jitter)   # mismo patrón U4
  si OK (2xx)     → ventana entregada (dedup de U2 hace idempotente un reenvío)
  si se agotan    → log event="sensor_export_failed" window_start=…
                    + DESCARTAR la ventana (sin buffer local; hueco aceptado
                    por NFR-AVAIL-01, D-U5-05) y continuar con la siguiente
                    (--once ⇒ exit 1)
```

- **Sin endpoint de latido propio** (Q6=A): `HealthService` ya deriva `sensor_heartbeats = MAX(observed_at) GROUP BY sensor_id`; el sensor solo debe seguir emitiendo observaciones con `sensor_id`.
- `Batch.reconcile` no se envía: los lotes de sensor no contienen `DiscoveryObservation` ⇒ `has_discovery=False` ⇒ U2 nunca ejecuta `reconcile_missing` (frontera U2 intacta).
- Idempotencia (ST-M3-03 AC2): reenvío del mismo lote ⇒ `dedup_key` UUIDv5 del contenido normalizado ⇒ `deduplicated` en U2, sin filas nuevas.

### 3.6 CLI, GT-04 y GT-05 (Q12=A, Q13=A)

| Modo | Uso | Detalle |
|---|---|---|
| `--once` | tests/CI, verificación manual | 1 ventana completa (reloj inyectable ⇒ sin sleep en tests) → export → exit `0` (OK) / `1` (config inválida o export agotado) |
| `--loop` | demo sin chart, Deployment de U9 | duerme hasta el borde de ventana; cierra → export → repite; SIGTERM limpia entre ventanas y sale `0` |

- **GT-04 (tráfico alto)**: `SENTINEL_TRAFFIC_SIM_RATE` alto ⇒ ventanas con `bytes_per_second` alto persistidas en U2 ⇒ U6/U7/U8 evalúan R-01 (fuera de U5).
- **GT-05 (sensor caído)**: detener el loop (o no iniciarlo) ⇒ sin observaciones nuevas ⇒ heartbeat cae ⇒ U8 alerta R-04 (fuera de U5).
- Ambos modos comparten `run_window` (mismo worker); el generador es determinista (`SIM_SEED`) ⇒ escenarios reproducibles sin red real.

---

## 4. Ediciones acotadas a unidades aprobadas

| Archivo | Edición | Por qué |
|---|---|---|
| *(ninguno)* | **U5 no edita U1 ni U2**: contratos, endpoint, dedup, heartbeats e inventario ya soportan traffic/arp (Q7/Q10/Q11=A) | Frontera limpia — a diferencia de U4, no se requieren ediciones acotadas |

---

## 5. Decisiones y desviaciones

| ID | Decisión / desviación | Origen |
|---|---|---|
| D-U5-01 | **Ventana vacía ⇒ 1 observación cero `protocol="other"` con `pairs=[]`**: mantiene el heartbeat (Q4=A) sin vincular a activos (`_ip_of` ⇒ None ⇒ `asset_id=NULL`) ⇒ BR-U3-07 y "no se inventan ceros" por activo quedan intactos; la observación cero es factual (0 paquetos reales en la ventana) | Q4=A + BR-U3-07, services.md §4 |
| D-U5-02 | `window_id` = `uuid5(sensor_id, window_start, interface, protocol)` **determinista**: trazabilidad estable en logs/reintentos; la idempotencia la garantiza el dedup de U2 por contenido | Q5=A |
| D-U5-03 | **IPv4 only** en el MVP (PRD §3.2 `total_length`); IPv6 documentado como extensión futura | FR-TRAF-03, PRD §3.2 |
| D-U5-04 | Rutas de verificación de ST-M3-01..06 (historias **documented-only**, sus AC citan paths que no existen) se re-mapean a `tests/unit/traffic/*` + `tests/integration/*`; el AC `POST /ingest/traffic` queda documentado (se usa `/ingest` real) | Q7=A, story-map M3 documented-only |
| D-U5-05 | Descarte de ventana tras reintentos agotados (sin buffer local) — mismo precedente que D-U4-03; services.md "hasta lograrlo" queda cubierto dentro del presupuesto ×5 de `foundation.retry` | Q9=A, NFR-AVAIL-01 |
| D-U5-06 | `SENTINEL_TRAFFIC_SENSOR_ID` como env propia del sensor (default `sensor-0`); U9 mapeará `sensor.id` ⇒ env. Discovery sigue sin env (D-U4-08) — coherencia por valor, no por mecanismo | Q2=A |
| D-U5-07 | `FALLBACK=false` ⇒ `ConfigError` al arranque: la captura real está documentada, no implementada (Q3=A) — no existe fuente real que seleccionar | Q3=A, implementation-scope |
| D-U5-08 | Tasa ARP **solo como función pura + log** en U5; sin campo de tasa ni modelo nuevo (sin edición U1). R-02 consumirá `sentinel_arp_messages_total` (U7) vía PromQL `rate()` | Q10=A |
| D-U5-09 | Tracking IP↔MAC **delegado en U2** (`InventoryService` ya emite `arp_mapping_changed`); U5 no duplica estado local pese a la redacción de `unit-of-work.md` ("tracking IP↔MAC") — la responsabilidad se cumple alimentando el contrato | Q11=A, U2 service.py |

---

## 6. Cobertura de historias

| Historia | Estado en U5 | Nota |
|---|---|---|
| ST-M3-01 Captura mínima en SPAN | documented-only | soporte: `SimulatedSource` + test `minimal_fields` (D-U5-04); captura real §5 |
| ST-M3-02 Ventanas configurables | documented-only | soporte: loader valida ventana + `test_aggregation -k five_second_windows`; `helm lint` en U9 |
| ST-M3-03 Export a Core | documented-only | soporte: `test_client` + integration export vía `/ingest` (D-U5-04) |
| ST-M3-04 ARP + tracking IP-MAC | documented-only | soporte: `test_arp -k request_and_reply` + integration `test_arp_mapping_change` (evento en U2) |
| ST-M3-05 Tasa ARP | documented-only | soporte: `test_arp_rate -k ten_per_second`; métrica R-02 ⇒ U7/U8 |
| ST-M3-06 Alerta `ArpMappingChanged` | documented-only | evento ya en U2; alerta R-03 ⇒ U8 (story-map) |
