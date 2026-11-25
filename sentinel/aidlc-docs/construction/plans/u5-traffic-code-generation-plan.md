# Code Generation Plan — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — Code Generation (Part 1: Planning)
**Fecha**: 2026-11-19
**Estado**: COMPLETED — aprobado 2026-11-19T03:10:00Z; los 25 steps ejecutados y en verde (Step 24)
**Workspace root**: `/home/jhoseph/Documents/TAI/TAI_Proyecto/sentinel` (de `aidlc-state.md`)
**Patrón**: Greenfield multi-unit (monolith) → `src/{unit-name}/` = **`src/sentinel/traffic/`**, tests = **`tests/unit/traffic/`** + **`tests/integration/`** + **`tests/property/`**
**Este plan es la única fuente de verdad de Code Generation para U5.**

---

## 1. Contexto de la unidad

- **Historias**: ST-M3-01..06 (**todas `documented-only`** en el story map — 0 implemented / 6 documented-only; el **simulador/fixtures es código de soporte de la unidad** según `unit-of-work.md` §U5 e `implementation-scope.md` §3).
  - ST-M3-01 Minimal traffic metadata capture on SPAN · ST-M3-02 Configurable aggregation windows · ST-M3-03 Export aggregated flows to Core · ST-M3-04 ARP observation and IP-MAC tracking · ST-M3-05 ARP rate per interface · ST-M3-06 ARP mapping changed alert.
  - **D-U5-04**: las rutas de verificación de los AC (que citan paths inexistentes) se re-mapean a `tests/unit/traffic/*` + `tests/integration/*`; el AC `POST /ingest/traffic` queda documentado (se usa el `/ingest` real).
- **Diseño aprobado**: FD (flujos §3.1–3.6, BR-U5-01..36, D-U5-01..09, §4 ediciones = **ninguna**), NFR Requirements (NFR-U5-*, TS-U5-01..13), NFR Design (P1–P13, 9 componentes lógicos), Infrastructure Design (ID-U5-01..10: Deployment `--loop` spec, Dockerfile sin cambios, OQ-01 resuelta, gate CI separado).
- **Dependencias**: **U1** (`foundation.*`: `TrafficObservation`/`ArpObservation`/`FlowPair`/`Batch`/`Protocol`/`UTCDateTime`/`ConfigError`/`with_retries`/`get_logger`/`MAX_BATCH_ITEMS`) y **U2** (`POST /api/v1/ingest` con `Batch` discriminator `source`, dedup UUIDv5, `HealthService.sensor_heartbeats`, `InventoryService.observe` → `arp_mapping_changed`, `create_if_missing=False` para no-discovery) **satisfechas — cero ediciones a U1/U2** (FD §4). **U9** (Deployment/values/NetworkPolicy) llega después — este plan solo deja el worker y el handoff documentado.
- **Interfaces/contratos**: CLI `python -m sentinel.traffic --once|--loop`; env `SENTINEL_TRAFFIC_{WINDOW_SECONDS,INTERFACE,SENSOR_ID,SIM_SEED,SIM_RATE,FALLBACK}` + `SENTINEL_API_BASE` (default `http://127.0.0.1:8080`) + `SENTINEL_INGEST_TOKEN`; `POST /api/v1/ingest` con `{"items":[...]}` (sin `reconcile`) + Bearer; protocolo `PacketSource.events() → Iterator[IpPacket|ArpPacket]`.
- **Límites**: `sentinel.traffic` **nunca** importa `sentinel.core.*` ni `sqlite3` (BR-U5-32); sin scapy/`AfPacketSource` (BR-U5-33); sin `/metrics` propio (MNT-04); sin Helm values ni objetos K8s (ID-U5-10); sin ediciones de Dockerfile (ID-U5-02); tracking IP↔MAC **delegado en U2** (D-U5-09); tasa ARP solo función pura + log (D-U5-08).
- **Toolchain**: hereda U1..U4 (ruff E,F,W,I,N,UP,B,SIM, mypy, pytest+cov, `TestClient`, `httpx.MockTransport`, `foundation.testing`, hypothesis); **cero deps nuevas** (TECH-01); gates: total `--cov=sentinel ≥70` **+** `coverage report --include='*/traffic/*' --fail-under=70` (P11/Q7=A).

---

## 2. Pasos de generación (numerados, checkbox)

- [x] **Step 1 — Project structure setup**
  Crear `src/sentinel/traffic/__init__.py`, `config.py`, `source.py`, `aggregator.py`, `arp.py`, `worker.py`, `client.py`, `__main__.py`; `tests/unit/traffic/__init__.py` + `tests/unit/traffic/fixtures/` (JSON de eventos de ejemplo); `tests/integration/test_traffic_export.py`, `tests/integration/test_arp_mapping_change.py` (placeholders), `tests/property/test_window_aggregation.py` (placeholder).

- [x] **Step 2 — Config estricta (BR-U5-01..05/36, TS-U5-05, D-U5-06/07)**
  Crear `src/sentinel/traffic/config.py`: `TrafficSettings` (Pydantic `frozen`, `extra="forbid"`) con defaults del FD §1.1 (`WINDOW_SECONDS=5`, `INTERFACE=eth0`, `SENSOR_ID=sensor-0`, `SIM_SEED=42`, `SIM_RATE=50.0`, `FALLBACK=true`); `load_traffic_settings(env)` ⇒ fail-fast `ConfigError` (ventana ∈ {1,5,10,30,60} — `window_seven_rejected`, `SIM_RATE > 0`, `SIM_SEED ≥ 0`, `INTERFACE`/`SENSOR_ID` no vacíos ≤255, `FALLBACK=false` ⇒ `ConfigError`); `CoreSettings` de U1 intacto (BR-U5-04).

- [x] **Step 3 — Unit tests: config (MNT-02)**
  `tests/unit/traffic/test_config.py`: `-k defaults`, `-k invalid_config`, `-k strict_env` (clave `SENTINEL_TRAFFIC_*` desconocida ⇒ error), `-k window_values`, `-k window_seven_rejected`, `-k fallback_false_rejected`, `-k sensor_id_default`, `-k sim_rate_positive`.

- [x] **Step 4 — Fuente abstracta y eventos ligeros (BR-U5-06..11, P5, TECH-03)**
  Crear `src/sentinel/traffic/source.py`: protocolo `PacketSource` (`events() → Iterator[IpPacket | ArpPacket]`); `IpPacket`/`ArpPacket` como `@dataclass(slotted=True)` internos (**sin validación Pydantic por evento**, P5) con los campos mínimos de BR-U5-08/09 (`IpPacket`: `observed_at`, `interface`, `protocol ∈ {tcp,udp,icmp,other}`, `src_ip`, `dst_ip`, `packet_length_bytes`; `ArpPacket`: `observed_at`, `opcode ∈ {1,2}`, `psrc`, `pdst`, `hwsrc`, `hwdst`, `interface`); `SimulatedSource(seed, rate, interface, sensor_id)` determinista (misma terna ⇒ misma secuencia, BR-U5-07; mapeo de protocolo 6→tcp/17→udp/1→icmp/otro→other, BR-U5-18; IPv6 descartado, BR-U5-10); `FixtureSource(path)` (replay JSON); ambos envían `sensor_id` en la proyección.

- [x] **Step 5 — Unit tests: source (MNT-02, GT-04)**
  `tests/unit/traffic/test_source.py`: `-k deterministic_seed` (dos instancias misma secuencia), `-k protocol_fallback`, `-k ipv6_skipped`, `-k high_rate_windows` (SIM_RATE alto ⇒ más eventos por ventana, soporte GT-04), `-k fixture_replay`.

- [x] **Step 6 — Agregador de ventanas (BR-U5-12..18, P2, D-U5-01/02)**
  Crear `src/sentinel/traffic/aggregator.py`: `MAX_PAIRS_PER_OBSERVATION = 100`; `WindowAccumulator` (dicts O(1): `packets_by_protocol`, `bytes_by_protocol`, `pairs_by_protocol`); cierre epoch-aligned `window_start = floor(now/W)*W` (BR-U5-12); **guard monótono** `last_emitted_window_start` — `window_start ≤ último emitido` ⇒ descarte + `log warning event="window_clock_regression"` (P2); **toda ventana se emite**: vacío ⇒ 1 `TrafficObservation` cero `protocol="other"` `pairs=[]` (BR-U5-13/D-U5-01); 1 obs por (ventana × interfaz × protocolo con ≥1 paquete) (BR-U5-14); `bytes_per_second = bytes / W` (BR-U5-15); `flows` = pares distintos, `pairs` acotado a 100 con orden determinista (packets desc, src asc, dst asc) (BR-U5-16); `window_id = uuid5(sensor_id, window_start, interface, protocol)` (BR-U5-17/D-U5-02); proyección **una vez por ventana** a `TrafficObservation` Pydantic U1 (P5/P6).

- [x] **Step 7 — Unit tests: aggregation (MNT-02)**
  `tests/unit/traffic/test_aggregation.py`: `-k epoch_aligned`, `-k empty_window_emitted`, `-k one_obs_per_protocol`, `-k five_second_windows` (25 s @ 5 s ⇒ 5 ventanas), `-k pairs_cap` (`len(pairs) ≤ 100`, `flows ≥ len(pairs)`), `-k window_id_stable`, `-k protocol_mapping`, `-k clock_regression` (reloj retrocede ⇒ sin re-emisión + warning).

- [x] **Step 8 — Dominio ARP (BR-U5-09/19/22, D-U5-08)**
  Crear `src/sentinel/traffic/arp.py`: `to_arp_observations(packets, …) → list[ArpObservation]` (frontera U1: opcode 1|2, IPs/MAC canónicos, sin campo de tasa); `arp_rate(n, W) -> float` **función pura** `n / W` (sin I/O) para el log `arp_rate` (BR-U5-19); sin modelo nuevo ni edición U1 (BR-U5-22).

- [x] **Step 9 — Unit tests: arp + arp_rate (MNT-02)**
  `tests/unit/traffic/test_arp.py`: `-k request_and_reply` (opcode 1 y 2 ⇒ `ArpObservation` válida). `tests/unit/traffic/test_arp_rate.py`: `-k ten_per_second` (n=100, W=10 ⇒ 10.0), `-k log_field` (cierre de ventana ⇒ log `event=arp_rate` con `arp_messages_per_second`).

- [x] **Step 10 — Unit tests: minimal fields / no payload (BR-U5-08, ST-M3-01)**
  `tests/unit/traffic/test_minimal_fields.py`: `-k minimal_fields` (conjunto exacto de campos IP: `observed_at, protocol, src_ip, dst_ip, packet_length_bytes, interface, sensor_id`); `-k no_payload` (construir observación con campo extra ⇒ `ValidationError` — contratos `extra="forbid"`).

- [x] **Step 11 — Cliente de export (BR-U5-23..26, P13, TS-U5-06)**
  Crear `src/sentinel/traffic/client.py`: espejo de `discovery/client.py` — `IngestClient(base_url=None, token=None, transport=None)` (base `SENTINEL_API_BASE` default loopback, token `SENTINEL_INGEST_TOKEN`); `post_batch(items)`: Bearer, **1 POST por ventana** con lote mixto `TrafficObservation`+`ArpObservation` (BR-U5-23), **chunking ≤ `MAX_BATCH_ITEMS` (1000)** por POST secuencial (P13), `with_retries(attempts=5, base_delay=0.5, jitter)` (BR-U5-25); body **sin clave `reconcile`** (BR-U5-26); sin `reconcile` ⇒ U2 no ejecuta `reconcile_missing`.

- [x] **Step 12 — Unit tests: client (MNT-02)**
  `tests/unit/traffic/test_client.py` (`MockTransport`): `-k single_post_per_window` (1 ventana ≤1000 ⇒ 1 POST), `-k chunked_export` (2500 ARP ⇒ 3 POSTs), `-k bearer_header`, `-k no_reconcile_field` (body sin la clave), retry ×5 en 500, 4xx sin retry.

- [x] **Step 13 — Worker de ventana (BR-U5-25/28/30, P1/P2/P3/P4, AVAIL-01/02, D-U5-05)**
  Crear `src/sentinel/traffic/worker.py`: `run_window(settings, source, client, clock, …)` **síncrono de un hilo** (P4): `clock.now()` → guard monótono → iterar `source.events()` → acumular → al borde proyectar (aggregator + arp) → `log event=arp_rate` → `client.post_batch(items)` chunked → siguiente borde; **fallo por ventana sin estado acumulado** (P1): export agotado ⇒ `log event=sensor_export_failed` + descartar ventana + continuar (`--once` ⇒ exit 1); fuente falla ⇒ `log event=sensor_source_error` + descartar + continuar (P3/AVAIL-01); SIGTERM se atiende **entre** ventanas (AVAIL-02); observaciones emitidas con `settings.sensor_id` (BR-U5-36) ⇒ heartbeat `sensor_heartbeats` avanza (BR-U5-28); seams por constructor con defaults reales (P9/Q6=A).

- [x] **Step 14 — Unit tests: worker (MNT-02, GT-05)**
  `tests/unit/traffic/test_worker.py`: `-k ciclo` (ventana completa con `FixtureSource`+`MockTransport`+`FakeClock`, sin red/sleep), `-k retry_exhausted_drop`, `-k continue_next_window` (2 ventanas fallidas ⇒ tercera emite, worker vivo), `-k source_error_continues`, `-k clock_regression`, `-k observations_are_heartbeat`, `-k injectable_clock`, `-k sensor_id_on_obs`, `-k gt05_stops_heartbeat` (sin emisiones ⇒ heartbeat no avanza).

- [x] **Step 15 — CLI (TS-U5-08, BR-U5-29, TECH-04)**
  Crear `src/sentinel/traffic/__main__.py`: `argparse` `--once` | `--loop`; `ConfigError` ⇒ log + exit 1; `--once` ⇒ 1 ventana, export OK ⇒ exit 0 / fallo ⇒ exit 1; `--loop` duerme hasta el borde (reloj inyectable en tests), SIGTERM limpia entre ventanas ⇒ exit 0; logs `component=traffic.*` snake_case (`arp_rate`, `sensor_export_failed`, `sensor_source_error`, `window_clock_regression`); **sin servidor de métricas** (MNT-04).

- [x] **Step 16 — Unit tests: CLI (MNT-02)**
  `tests/unit/traffic/test_cli.py`: `-k exit_codes` (`--once` OK ⇒ 0; export fallido ⇒ 1; config inválida ⇒ 1), `--loop` ≥2 ventanas con reloj falso sin `sleep`.

- [x] **Step 17 — Test de arquitectura: frontera de imports (BR-U5-32/33)**
  `tests/unit/traffic/test_boundaries.py`: `sentinel.traffic` solo importa `sentinel.foundation` + httpx + stdlib (ast/inspection de los módulos del paquete — `assert "sentinel.core" not in imports`, `assert "sqlite3" not in imports`); `grep scapy src/` ⇒ 0 (BR-U5-33) verificado como aserción de revisión en el summary.

- [x] **Step 18 — Integration: export de tráfico (ST-M3-03, BR-U5-23/27)**
  `tests/integration/test_traffic_export.py`: `--once` (o `run_window`) contra la app real de U2 (`TestClient`, `CoreSettings` temporal): ventana emitida ⇒ 2xx ⇒ consultable (observación `source=traffic` en DB); reenvío del mismo lote ⇒ `deduplicated` sin filas nuevas (idempotencia ST-M3-03 AC2).

- [x] **Step 19 — Integration: ARP mapping change (BR-U5-20/21, ST-M3-04/06, D-U5-09)**
  `tests/integration/test_arp_mapping_change.py`: 2 ingests de `ArpObservation` con distinto `hwsrc` para la misma IP ⇒ evento `arp_mapping_changed` en `events` (`-k event`); IP aún sin activo ⇒ **no** crea asset (`-k no_asset_created`, `create_if_missing=False`); sin atribución de ataque en el contenido del evento.

- [x] **Step 20 — Integration: idempotencia reutilizada con items traffic/arp (BR-U5-27)**
  Extender `tests/integration/test_ingest_idempotency.py` (existente): añadir caso con lote mixto `traffic`+`arp` ⇒ mismo `dedup_key` ⇒ `deduplicated`, sin filas nuevas (ST-M3-03 AC2).

- [x] **Step 21 — PBT: agregación de ventanas (P12, MNT-03)**
  `tests/property/test_window_aggregation.py` (hypothesis): (a) las ventanas particionan la línea temporal sin solapes ni huecos, (b) Σ `packet_length_bytes` de los grupos == Σ bytes de los eventos de la ventana, (c) mismo `(seed, rate)` ⇒ mismas observaciones (determinismo).

- [x] **Step 22 — CI: gate de cobertura de traffic (P11/Q7=A, TS-U5-09)**
  Editar `.github/workflows/ci.yml` (workspace root): paso nuevo tras el gate de discovery: `- name: Traffic coverage gate (P11)` → `coverage report --include='*/traffic/*' --fail-under=70`; mantener gate total, GUI y discovery.

- [x] **Step 23 — README + docs de la unidad**
  Añadir sección **Traffic Sensor** en `README.md`: run local (`python -m sentinel.traffic --once|--loop`), tabla de env `SENTINEL_TRAFFIC_*` con defaults, nota de fuente simulada/fixtures (captura real documentada, OQ-01 resuelta sin `CAP_SYS_ADMIN`), handoff Deployment/NetworkPolicy/values a U9 (ID-U5-01/04/05), ST-M3-01..06 documented-only (D-U5-04).

- [x] **Step 24 — Validación local**
  Ejecutar: `ruff check .` · `ruff format --check .` · `mypy src/sentinel` · `pytest tests/unit tests/property tests/integration -q --cov=sentinel --cov-fail-under=70` + `coverage report --include='*/traffic/*' --fail-under=70` — todo en verde.

- [x] **Step 25 — Resumen de generación**
  Crear `aidlc-docs/construction/u5-traffic/code/code-generation-summary.md`: archivos creados (sin ediciones U1/U2/Dockerfile), verificación de frontera (imports, scapy=0), desviaciones D-\*, cobertura total y de `traffic/`, historias ST-M3-01..06 con estado documented-only + soporte generado, estado del repo (sin `.git`).

---

## 3. Historias y trazabilidad

| Historia | Steps | Verificación principal | Estado |
|---|---|---|---|
| ST-M3-01 Minimal traffic metadata capture (documented-only) | 4, 10, 17 | `test_minimal_fields` (campos exactos + `no_payload`); frontera sin scapy; captura real documentada en FD §5 | [x] |
| ST-M3-02 Configurable aggregation windows (documented-only) | 2, 6, 7 | loader `window_values`/`window_seven_rejected` + `five_second_windows`; `helm lint` ⇒ U9/Build & Test | [x] |
| ST-M3-03 Export aggregated flows to Core (documented-only) | 11, 12, 18, 20 | 1 POST/ventana + integration export consultable + idempotencia `deduplicated` | [x] |
| ST-M3-04 ARP observation and IP-MAC tracking (documented-only) | 8, 9, 19 | `request_and_reply` + integration `arp_mapping_changed` + `no_asset_created` (tracking en U2) | [x] |
| ST-M3-05 ARP rate per interface (documented-only) | 8, 9 | `ten_per_second` + `log_field`; R-02 = U8 documented-only | [x] |
| ST-M3-06 ARP mapping changed alert (documented-only) | 19 | integration `-k event`; alerta R-03 = U8 documented-only (sin "spoofing") | [x] |

*Estado `[x]` = código de soporte + tests generados y en verde en la validación local (Step 24). Las historias permanecen `documented-only` en el story map (captura real AF_PACKET no demostrada — implementation-scope §3); los AC se verifican con fuente simulada/fixtures (D-U5-04).*

---

## 4. Fuera de alcance de este plan

- `AfPacketSource`/scapy/AF_PACKET, SPAN/mirror, `hostNetwork`+capabilities (documentados en FD §5 e infra §3.3; OQ-01 ya resuelta).
- Deployment, NetworkPolicy, `values.yaml` de `traffic.*`/`sensor.id` (U9/U10 — handoff en `deployment-architecture.md` §5).
- R-02 `ArpRateThresholdExceeded` y R-03 alert (U8, documented-only); familias `/metrics` (U7); baseline (U6).
- Ediciones a U1/U2/Dockerfile (**cero** — FD §4, ID-U5-02).
- Build & Test: `helm template`, demo en kind con GT-04/GT-05, gate total de imagen (al final de la cadena).

---

## 5. Approval Gate

Para iniciar Part 2: Generation, responde **`Aprobado`** (o pide cambios) — la aprobación cubre el plan completo y la secuencia de los 25 steps.
