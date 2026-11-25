# Domain Entities — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-18
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/`
**Traza**: ST-M3-01..06 (documented-only), FR-TRAF-01..05, FR-ARP-01..04; plan Q1–Q13 = A; **U5 no escribe DB** — sus entidades son de dominio puro y se proyectan a los contratos de U1 (`TrafficObservation`, `ArpObservation`, `Batch`) y a los servicios de U2 (ingest, health, inventory).

---

## 1. Entidades de dominio (`traffic/`, sin I/O)

### 1.1 `TrafficSettings` (`traffic/config.py`)

Modelo Pydantic `frozen` con `extra="forbid"` (patrón `foundation.config`):

| Campo | Env | Default | Validación |
|---|---|---|---|
| `window_seconds` | `SENTINEL_TRAFFIC_WINDOW_SECONDS` | `5` | ∈ `{1,5,10,30,60}`; otro ⇒ `ConfigError` (BR-U5-02) |
| `interface` | `SENTINEL_TRAFFIC_INTERFACE` | `"eth0"` | no vacío, ≤ 255 |
| `sensor_id` | `SENTINEL_TRAFFIC_SENSOR_ID` | `"sensor-0"` | no vacío, ≤ 255 (D-U5-06) |
| `sim_seed` | `SENTINEL_TRAFFIC_SIM_SEED` | `42` | entero ≥ 0 |
| `sim_rate` | `SENTINEL_TRAFFIC_SIM_RATE` | `50.0` | float > 0 (paquetes/s) |
| `fallback` | `SENTINEL_TRAFFIC_FALLBACK` | `true` | `false` ⇒ `ConfigError` (D-U5-07) |

> `CoreSettings` (U1) no se modifica (BR-U5-04). `SENTINEL_API_BASE` (default `http://127.0.0.1:8080`) y `SENTINEL_INGEST_TOKEN` se leen en `client.py` sin redefinir (mismo patrón que U4).

### 1.2 `IpPacket` — evento crudo de la fuente (IPv4)

| Campo | Tipo | Notas |
|---|---|---|
| `observed_at` | `UTCDateTime` | timestamp del paquete (tz-aware UTC) |
| `interface` | `str` | interfaz configurada (`settings.interface`) |
| `protocol` | `Literal["tcp","udp","icmp","other"]` | derivado del campo IP `protocol` (BR-U5-18); **nunca `"arp"`** |
| `src_ip` / `dst_ip` | `IPv4Address` | sin MAC ni puerto (FR-TRAF-03) |
| `packet_length_bytes` | `int` (≥ 0) | `total_length` IPv4 (PRD §3.2) |

Invariantes (BR-U5-08/10): sin campos de payload/MAC/puerto (el modelo interno los rechaza con `extra="forbid"`); eventos IPv6 no se generan/aceptan en el MVP (D-U5-03).

### 1.3 `ArpPacket` — evento crudo de la fuente

| Campo | Tipo | Notas |
|---|---|---|
| `observed_at` | `UTCDateTime` | |
| `interface` | `str` | |
| `opcode` | `Literal[1,2]` | request / reply (FR-ARP-01) |
| `psrc` / `pdst` | `IPv4Address` | protocol addresses |
| `hwsrc` / `hwdst` | `MACAddress` (U1) | hardware addresses |

### 1.4 `PacketSource` (protocolo)

```python
class PacketSource(Protocol):
    def events(self) -> Iterator[IpPacket | ArpPacket]: ...
```

| Implementación | Estado | Detalle |
|---|---|---|
| `SimulatedSource` | implementado (MVP) | determinista con `sim_seed`/`sim_rate` (BR-U5-07); IP a `sim_rate` pps con protocolo ciclado; ARP 1 msg/s simulado alternando opcode |
| `FixtureSource` | implementado (tests) | replay de `tests/fixtures/traffic_*.json` (secuencias exactas: mapping-change, rate, minimal_fields) |
| `AfPacketSource` | **solo documentado** (§5) | scapy sobre AF_PACKET/TPACKET_V3 — sin código, sin dependencia (Q3=A) |

### 1.5 `WindowAccumulator` — estado interno por ventana (no persistido)

| Campo | Tipo | Notas |
|---|---|---|
| `window_start` / `window_end` | `UTCDateTime` | tumbling epoch-aligned (BR-U5-12) |
| `interface` | `str` | |
| `packets_by_protocol` | `dict[Protocol, int]` | conteo por protocolo |
| `bytes_by_protocol` | `dict[Protocol, int]` | Σ `packet_length_bytes` por protocolo |
| `pairs_by_protocol` | `dict[Protocol, dict[tuple[IPv4Address, IPv4Address], int]]` | pares → nº paquetes (para ordenar y acotar) |
| `arp_count` | `int` | nº de `ArpPacket` en la ventana (entrada a `arp_rate`) |

Se descarta al cerrar la ventana; nunca sale del proceso.

### 1.6 `arp_rate` — función pura (BR-U5-19)

```text
arp_rate(n: int, window_seconds: float) -> float   # n / window_seconds
# ST-M3-05 AC1: arp_rate(100, 10.0) == 10.0
```

---

## 2. Proyección a contratos de U1 (salida)

### 2.1 `TrafficObservation` — por (ventana × interfaz × protocolo) o ventana cero (BR-U5-13/14)

| Campo de U1 | Origen en U5 |
|---|---|
| `observed_at` | `window_end` (cierre de la ventana) |
| `sensor_id` | `settings.sensor_id` (default `sensor-0`) |
| `source` | fijo `"traffic"` |
| `window_start` / `window_end` | acumulador (BR-U5-12) |
| `interface` | `settings.interface` |
| `protocol` | grupo del acumulador; ventana vacía ⇒ `"other"` (D-U5-01) |
| `packet_length_bytes` | Σ bytes del grupo (0 en vacía) |
| `bytes_per_second` | Σ bytes / (window_end − window_start) (BR-U5-15) |
| `packets` | conteo del grupo (0 en vacía) |
| `flows` | total de pares distintos del grupo (0 en vacía) |
| `pairs` | hasta 100 pares, orden determinista (BR-U5-16); `[]` en vacía |
| `window_id` | `uuid5(sensor_id, window_start, interface, protocol)` (D-U5-02) |

Conversión en `aggregator.py` (`to_observations(accumulator)`); el dedup de U2 (UUIDv5 del contenido normalizado) hace idempotente un reenvío; `pairs=[]` ⇒ `_ip_of=None` ⇒ la ventana cero no se vincula a activos (D-U5-01).

### 2.2 `ArpObservation` — 1 por mensaje ARP (BR-U5-09)

| Campo de U1 | Origen en U5 |
|---|---|
| `observed_at` | timestamp del `ArpPacket` |
| `sensor_id` / `source` | `settings.sensor_id` / fijo `"arp"` |
| `interface` | `settings.interface` |
| `opcode` | `ArpPacket.opcode` (1\|2) |
| `psrc` / `pdst` | `ArpPacket.psrc` / `.pdst` |
| `hwsrc` / `hwdst` | `ArpPacket.hwsrc` / `.hwdst` |

Sin campo de tasa (D-U5-08): la tasa vive solo en el log vía `arp_rate`.

### 2.3 `Batch` — sin cambios (Q7=A)

| Campo | Envío desde U5 | Notas |
|---|---|---|
| `items` | `TrafficObservation…` + `ArpObservation…` (≤ 1000) | lote mixto por ventana |
| `reconcile` | **omitido** (default `True`) | inofensivo: sin `DiscoveryObservation` ⇒ U2 no reconcilia (BR-U5-26) |

U5 **no edita** `foundation/models.py` ni ningún archivo de U1/U2 (BLM §4).

---

## 3. Contratos de U2 consumidos (sin modificar)

| Contrato | Uso en U5 |
|---|---|
| `POST /api/v1/ingest` → 202 `IngestResult` | 1 POST por ventana cerrada (BR-U5-23); Bearer + reintentos (BR-U5-24/25) |
| `dedup_key` (UUIDv5 contenido normalizado) | idempotencia de reenvíos (BR-U5-27) |
| `HealthService.sensor_heartbeats` = `MAX(observed_at) GROUP BY sensor_id` | las observaciones del sensor **son** el heartbeat (BR-U5-28); GT-05 = detener loop |
| `InventoryService.observe(hwsrc…)` → evento `arp_mapping_changed` | tracking IP↔MAC **delegado** (BR-U5-20); U5 solo exporta |
| `create_if_missing=False` para no-discovery | ARP con IP desconocida no crea activo (BR-U5-21) |

---

## 4. Estructura del paquete (Q1=A)

```text
src/sentinel/traffic/
├── __init__.py
├── __main__.py       # CLI: --once | --loop (exit 0/1)
├── config.py         # TrafficSettings + load_traffic_settings (fail-fast)
├── source.py         # PacketSource, IpPacket, ArpPacket, SimulatedSource, FixtureSource
├── aggregator.py     # WindowAccumulator, cierre de ventana, to_observations, MAX_PAIRS_PER_OBSERVATION=100
├── arp.py            # to_arp_observations, arp_rate (función pura)
├── worker.py         # run_window: fuente → acumulador → cierre → log arp_rate → export (reloj inyectable)
└── client.py         # post_batch (Bearer + with_retries ×5) espejo de discovery/client.py
```

Tests (rutas reales, D-U5-04):

```text
tests/unit/traffic/
├── test_config.py            # loader, ventana ∈ {1,5,10,30,60}, fallback, defaults
├── test_source.py            # determinismo, fixture replay, ipv6_skipped, protocol_fallback
├── test_minimal_fields.py    # BR-U5-08 (minimal_fields, no_payload)
├── test_aggregation.py       # five_second_windows, epoch_aligned, empty_window, pairs_cap, window_id
├── test_arp.py               # request_and_reply
├── test_arp_rate.py          # ten_per_second
├── test_worker.py            # ciclo, retry_exhausted_drop, heartbeat, gt05, exit codes
├── test_client.py            # single_post_per_window, bearer, no_reconcile_field
└── test_cli.py               # exit_codes
tests/integration/
├── test_traffic_export.py    # --once contra Core real (testclient): ventana consultable (ST-M3-03)
└── test_arp_mapping_change.py  # 2 ingests MAC distinta ⇒ arp_mapping_changed + no_asset_created (ST-M3-04/06)
```

Imports: `sentinel.foundation.*` + httpx + stdlib — **nunca** `sentinel.core.*` ni `sqlite3` (BR-U5-32).

---

## 5. Extensión documentada (sin código en U5)

| Concepto | Diseño documentado | Historia / NFR |
|---|---|---|
| `AfPacketSource` (captura real) | scapy `AsyncSniffer`/`L2Socket` sobre `AF_PACKET` con `TPACKET_V3` en la interfaz mirror/SPAN; extrae los mismos campos mínimos que `IpPacket`/`ArpPacket` (FR-TRAF-03) y alimenta el mismo `PacketSource`; selección: `FALLBACK=false` ⇒ esta fuente (hoy ⇒ `ConfigError`, D-U5-07) | FR-TRAF-01, ST-M3-01, NFR-TECH-02 |
| Pod del sensor (FR-TRAF-02) | Deployment con `hostNetwork: true` y capabilities `CAP_NET_RAW`, `CAP_NET_ADMIN`; **OQ-01**: evaluar si `CAP_SYS_ADMIN` puede descartarse (se resuelve en NFR Design/Infra de U5); imagen Alpine non-root con excepción de capabilities (NFR-SEC-02) | FR-TRAF-02, OQ-01, NFR-SEC-02 |
| Diseño SPAN/mirror | puerto mirror de switch/bridge hacia la interfaz del sensor; segmento autorizado = mismo scope de U4; documentación en runbook de U11 | `unit-of-work.md` §U5, implementation-scope M3 |
| Helm values (U9) | `traffic.window` (validado por BR-U5-02 ⇒ `helm lint --set traffic.window=7s` falla), `traffic.interface`, `traffic.simRate`, `sensor.id` ⇒ `SENTINEL_TRAFFIC_*`; chart = Deployment `--loop` | NFR-OPS-01, ST-M3-02 AC2 |
| R-02 `ArpRateThresholdExceeded` | U7 expone `sentinel_arp_messages_total` (familia ya en U1); regla PromQL `rate(...[10s]) > umbral` en U8; el log `arp_rate` de U5 da la evidencia por ventana | FR-ARP-03, ST-M3-05, R-02 |
| R-03 `ArpMappingChanged` | evento ya lo emite U2 (BR-U5-20); la **regla/alerta** Prometheus es de U8 (documented-only) | FR-ARP-04, ST-M3-06, R-03 |
| IPv6 | extensión futura: ampliar `IpPacket`/agregación a IPv6 (D-U5-03) | PRD §3.2 (IPv4 hoy) |
