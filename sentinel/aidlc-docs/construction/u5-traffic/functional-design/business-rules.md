# Business Rules & Validation — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-18
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/`
**Traza**: ST-M3-01..06 (documented-only), FR-TRAF-01..05, FR-ARP-01..04, NFR-AVAIL-01, NFR-SEC-02; plan Q1–Q13 = A; `services.md` §2.1/§4, `component-methods.md` §11/§36.

---

## 1. Configuración y arranque (fail-fast)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U5-01 | Loader propio `load_traffic_settings` desde `SENTINEL_TRAFFIC_*` (patrón `foundation.config`); config inválida ⇒ `ConfigError` al arranque — nada se captura con config inválida | Q2=A, BR-07 U1 | `pytest tests/unit/traffic/test_config.py -k invalid_config` |
| BR-U5-02 | `WINDOW_SECONDS` ∈ `{1,5,10,30,60}` (default 5); cualquier otro valor (p. ej. 7) ⇒ `ConfigError` — el validador detrás de `helm lint --set traffic.window=7s` (U9) | FR-TRAF-04, ST-M3-02 AC2 | `test_config.py -k window_values` + `-k window_seven_rejected` |
| BR-U5-03 | Defaults de laboratorio: `INTERFACE=eth0`, `SENSOR_ID=sensor-0`, `SIM_SEED=42`, `SIM_RATE=50.0`, `FALLBACK=true` | Q2/Q13=A | `test_config.py -k defaults` |
| BR-U5-04 | `CoreSettings` de U1 **no cambia** (exactamente 4 claves `SENTINEL_*`); `SENTINEL_API_BASE`/`SENTINEL_INGEST_TOKEN` se leen sin redefinir | Q2=A, BR-06 U1 | revisión de código + `tests/unit/foundation/test_config.py` (sin regresión) |
| BR-U5-05 | `FALLBACK=false` ⇒ `ConfigError` al arranque (la captura real AF_PACKET está documentada, no implementada) | Q3=A, D-U5-07 | `test_config.py -k fallback_false_rejected` |

## 2. Fuente de paquetes y campos extraídos (FR-TRAF-03, FR-ARP-01)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U5-06 | Fuente intercambiable vía protocolo `PacketSource` (`events() → Iterator[IpPacket\|ArpPacket]`); el MVP solo implementa `SimulatedSource`/`FixtureSource` | Q3=A, component-methods §11 | `test_source.py -k protocol_fallback` |
| BR-U5-07 | **Determinismo**: misma terna `(SIM_SEED, SIM_RATE, fixtures)` ⇒ misma secuencia de eventos (reproducible sin red) | Q13=A | `test_source.py -k deterministic_seed` (dos instancias ⇒ misma secuencia) |
| BR-U5-08 | Del paquete IP solo se extraen `observed_at, protocol, src_ip, dst_ip, packet_length_bytes, interface, sensor_id`; **sin payload, MAC ni puerto** (contratos U1 `extra="forbid"`) | FR-TRAF-03, ST-M3-01 AC1/AC2 | `test_minimal_fields.py -k minimal_fields` (conjunto de campos exacto) + `-k no_payload` (construir con campo extra ⇒ `ValidationError`) |
| BR-U5-09 | Del ARP solo se extraen `observed_at, opcode(1\|2), psrc, pdst, hwsrc, hwdst, interface, sensor_id` (request **y** reply) | FR-ARP-01, ST-M3-04 AC1 | `tests/unit/traffic/test_arp.py -k request_and_reply` |
| BR-U5-10 | **IPv4 only** en MVP: eventos IPv6 se descartan de la agregación (documentado como extensión) | D-U5-03, PRD §3.2 | `test_source.py -k ipv6_skipped` |
| BR-U5-11 | El sensor no importa `scapy` ni `nmap`; `requirements.txt` sin dependencias de captura real | Q3=A, NFR-TECH-02 parcial | revisión de imports + `requirements.txt` |

## 3. Agregación de ventanas (FR-TRAF-04, ST-M3-02)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U5-12 | Ventanas **tumbling alineadas al reloj**: `window_start = floor(now/W)*W`, `window_end = window_start + W`; emisión **al cierre** | Q4=A | `test_aggregation.py -k epoch_aligned` |
| BR-U5-13 | **Toda ventana se emite**: sin paquetes ⇒ 1 `TrafficObservation` cero (`protocol="other"`, `packets=0`, `bytes_per_second=0.0`, `pairs=[]`) — es el heartbeat (red idle ≠ sensor caído) | Q4/Q6=A, D-U5-01 | `test_aggregation.py -k empty_window_emitted` |
| BR-U5-14 | Con tráfico: **1 `TrafficObservation` por (ventana × interfaz × protocolo con ≥1 paquete)** ∈ {tcp,udp,icmp,other}; ARP nunca entra a traffic (va en `ArpObservation`) | Q5=A, FR-TRAF-03 | `test_aggregation.py -k one_obs_per_protocol` |
| BR-U5-15 | `bytes_per_second = packet_length_bytes / (window_end − window_start)` (duración efectiva = W); 25 s @ 5 s ⇒ 5 ventanas | ST-M3-02 AC1 | `test_aggregation.py -k five_second_windows` |
| BR-U5-16 | `flows` = nº total de pares src-dst distintos; `pairs` = muestra **acotada a 100** (`MAX_PAIRS_PER_OBSERVATION`), orden determinista (packets desc, src asc, dst asc) | Q5=A, `MAX_BATCH_ITEMS` U1 | `test_aggregation.py -k pairs_cap` (`len(pairs) ≤ 100`, `flows ≥ len(pairs)`) |
| BR-U5-17 | `window_id = uuid5(sensor_id, window_start, interface, protocol)` **estable** (mismo contenido ⇒ mismo id en reintentos) | Q5=A, D-U5-02 | `test_aggregation.py -k window_id_stable` |
| BR-U5-18 | Protocolo desde IP: `6→tcp`, `17→udp`, `1→icmp`, otro→`other` (mapeo fijo, sin inspección de puertos) | FR-TRAF-03 | `test_aggregation.py -k protocol_mapping` |

## 4. ARP: tasa y tracking delegado (FR-ARP-02/03/04)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U5-19 | `arp_rate(n, W) = n / W` es **función pura** sin I/O; al cierre de cada ventana se registra `log event="arp_rate" interface=… window_start=… arp_messages_per_second=…` | ST-M3-05 AC1, Q10=A | `test_arp_rate.py -k ten_per_second` (n=100, W=10 ⇒ 10.0) + `-k log_field` |
| BR-U5-20 | U5 **no mantiene estado IP↔MAC** ni emite eventos de mapping: exporta `ArpObservation` crudas; la detección la hace `InventoryService` de U2 (evento `arp_mapping_changed` al cambiar `hwsrc`) | FR-ARP-02/04, Q11=A, D-U5-09 | `tests/integration/test_arp_mapping_change.py -k event` (2 ingests con MAC distinta ⇒ fila en `events`) |
| BR-U5-21 | ARP con IP aún desconocida **no crea activo** (`create_if_missing=False` para no-discovery en U2) — el sensor no fuerza inventario | frontera U2, unit-of-work §U5 | `test_arp_mapping_change.py -k no_asset_created` |
| BR-U5-22 | Sin campo de tasa en contratos U1 y sin edición de modelos: R-02 se construirá sobre `sentinel_arp_messages_total` (U7, familia ya en U1) + PromQL `rate()` | Q10=A, D-U5-08 | revisión: no existen cambios en `foundation/models.py` |

## 5. Export e idempotencia (FR-TRAF-05, ST-M3-03, services.md §2.1)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U5-23 | **1 `POST /api/v1/ingest` por ventana cerrada** con lote mixto (`TrafficObservation` + `ArpObservation`); endpoint genérico de U2 — **sin editar U2** ni crear `/ingest/traffic` | Q7=A, D-U5-04 | `test_client.py -k single_post_per_window` |
| BR-U5-24 | Bearer `SENTINEL_INGEST_TOKEN`; base `SENTINEL_API_BASE` (default loopback, U9 la inyecta) — mismo contrato que U4 | Q8=A, services.md §2.1 | `test_client.py -k bearer_header` |
| BR-U5-25 | Reintentos `with_retries(attempts=5, base_delay=0.5, jitter)`; agotados ⇒ `log event="sensor_export_failed"` + **descartar ventana** y continuar (`--once` ⇒ exit 1); sin buffer local | Q9=A, D-U5-05, NFR-AVAIL-01 | `test_worker.py -k retry_exhausted_drop` + `-k continue_next_window` |
| BR-U5-26 | El lote **no envía `reconcile`** (default): sin `DiscoveryObservation` ⇒ U2 no ejecuta `reconcile_missing` — los lotes del sensor jamás incrementan `miss_count` | frontera U2, BR-U2-15 | `test_client.py -k no_reconcile_field` (body sin la clave) |
| BR-U5-27 | Reenvío idempotente: mismo lote ⇒ `dedup_key` UUIDv5 de U2 ⇒ `deduplicated`, sin filas nuevas (ST-M3-03 AC2) | ST-M3-03 AC2 | `tests/integration/test_ingest_idempotency.py` (existente, reutilizado con items traffic/arp) |
| BR-U5-28 | **Sin endpoint de latido propio**: el heartbeat es `MAX(observed_at) GROUP BY sensor_id` en `HealthService` de U2; el sensor solo sigue emitiendo | Q6=A, GT-05 | `test_worker.py -k observations_are_heartbeat` (ventanas emitidas ⇒ `sensor_heartbeats` avanza) |

## 6. CLI y determinismo de la demo (ST-M3-02/GT-04/GT-05)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U5-29 | `--once`: 1 ventana → export → exit `0` (OK) / `1` (config inválida o export agotado); `--loop`: duerme hasta el borde de ventana, SIGTERM limpia entre ventanas ⇒ exit `0` | Q12=A, patrón U4 | `tests/unit/traffic/test_cli.py -k exit_codes` |
| BR-U5-30 | Ambos modos comparten `run_window` (mismo worker; reloj y fuente inyectables ⇒ tests sin `sleep`) | Q12=A, component-methods §11 | `test_worker.py -k injectable_clock` |
| BR-U5-31 | **GT-04** = `SIM_RATE` alto (env) ⇒ ventanas con `bytes_per_second` alto; **GT-05** = detener el loop ⇒ sin observaciones nuevas ⇒ heartbeat cae; ambos sin red real ni improvisación de datos | demo-plan.md, Q13=A | `test_source.py -k high_rate_windows` + `test_worker.py -k gt05_stops_heartbeat` |

## 7. Frontera y documented-only

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U5-32 | Frontera: `sentinel.traffic` solo importa `sentinel.foundation` + httpx + stdlib; **nunca** `sentinel.core.*` ni `sqlite3` | unit-of-work §imports | test de arquitectura (imports) |
| BR-U5-33 | **Sin código de captura real**: no existe `AfPacketSource`/scapy en `src/` ni en `requirements.txt`; el diseño AF_PACKET/TPACKET_V3 + SPAN/mirror + capabilities (FR-TRAF-02, OQ-01) queda documentado en `domain-entities.md` §5 | Q3=A, implementation-scope | revisión de alcance (grep `scapy` en `src/` ⇒ 0) |
| BR-U5-34 | **Sin Helm values en U5**: `traffic.window/interface/sensor.id` los mapea U9; el validador que rechaza ventana inválida vive en el loader (BR-U5-02) | Q2=A, NFR-OPS-01 | revisión de alcance (sin `deploy/` en U5) |
| BR-U5-35 | ST-M3-01..06 quedan **documented-only** con soporte de la unidad (simulador/fixtures/tests); las rutas de verificación de sus AC se re-mapean a `tests/unit/traffic/*` y `tests/integration/*` (D-U5-04) | story-map M3 | tabla de cobertura en BLM §6 |
| BR-U5-36 | `sensor_id` = settings del sensor (default `sensor-0`); toda observación lo porta — foundation solo expone el campo crudo (BR-16 U1) | Q2=A, D-U5-06 | `test_config.py -k sensor_id_default` + `test_worker.py -k sensor_id_on_obs` |
