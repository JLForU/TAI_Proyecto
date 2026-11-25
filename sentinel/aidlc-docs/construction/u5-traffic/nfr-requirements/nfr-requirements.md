# NFR Requirements — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — NFR Requirements (Part 2: Generation)
**Fecha**: 2026-11-18
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/`
**Decisiones (plan Q1–Q9)**: **A en todas** (2026-11-18).
**Entradas**: Functional Design de U5 (aprobado 2026-11-18T16:53:34Z), `requirements.md` §3/§4/§5, U1–U4 `tech-stack-decisions.md`, `implementation-scope.md`.

---

## 1. Alcance

NFR **específicos de U5** (colector de sensor: fuente abstracta/simulada, agregación de ventanas, ARP, export al Core, CLI). Hereda sin cambio TS-01..11 de U1, TS-U2-01..11 de U2, TS-U3 de U3, TS-U4-01..12 de U4 y el stack global (Python 3.11, httpx, foundation).

**Fijados por requisito/aprobados (no se preguntaron)**: NFR-AVAIL-01 (single sensor, gap aceptado en FD D-U5-05), NFR-SEC-02 (non-root; caps del sensor ⇒ diseño documentado + U9), NFR-SEC-01 (SECURITY blocking), NFR-PERF-02 (no vinculante), FD Q1–Q13 (sin scapy, config estricta, retries ×5, heartbeat sin endpoint, reloj inyectable), `implementation-scope.md` (ST-M3-01..06 documented-only).

**Categorías**: Usability **no aplica** (U5 sin UI — única unidad con UI es U3).

---

## 2. Requisitos no funcionales de U5

### 2.1 Rendimiento y capacidad (Performance / Scalability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U5-PERF-01 | Baseline **informativo** de throughput con `SimulatedSource` a tasa alta: registra flows/s y duración del pipeline (fuente → agregación → proyección) en la suite **sin gate** en CI; la envolvente real (NFR-PERF-02: ≥10k flows/s en 2 cores) se valida en el lab durante Build & Test | Plan Q1=A, NFR-PERF-02 | test informativo que imprime throughput (sin assert de duración) |
| NFR-U5-SCAL-01 | **Chunking del export**: los items de una ventana se parten en POSTs secuenciales de ≤1000 (`MAX_BATCH_ITEMS`); un lote nunca supera el límite (ráfaga ARP no produce 422); si un chunk falla tras reintentos se descartan solo los chunks no entregados de esa ventana | Plan Q2=A, FD §3.5, BR-U5-23 | `test_client.py -k chunked_export` (ventana con 2500 ARP ⇒ 3 POSTs ≤1000) |

### 2.2 Disponibilidad y fiabilidad (Availability / Reliability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U5-AVAIL-01 | **Loop que nunca muere por la fuente**: fallo de `PacketSource` a mitad de ventana ⇒ `log event="sensor_source_error"` + causa, descarte del acumulador parcial, el loop continúa con la siguiente ventana (heartbeat sigue vivo); `--once` ⇒ exit 1 | Plan Q3=A, NFR-AVAIL-01, GT-05 | `test_worker.py -k source_error_continues` (fuente que lanza ⇒ siguiente ventana se emite) |
| NFR-U5-AVAIL-02 | **Degradación por capas sin estado**: Core caído ⇒ `with_retries` ×5 (backoff) ⇒ ventana/chunk descartado con `sensor_export_failed` (D-U5-05); worker sin BD ni caché entre ventanas; SIGTERM en `--loop` se atiende **entre** ventanas | FD §3.5/§3.6, D-U5-05, BR-U5-25 | `test_worker.py -k retry_exhausted_drop` + revisión (cero imports `sqlite3`/`core`) |
| NFR-U5-REL-01 | **Reloj UTC inyectable**: ventanas alineadas con pared UTC vía protocolo de reloj (tests con reloj falso, **sin `sleep`**); `monotonic` solo para el backoff de reintentos — alineación estable con Core/Prometheus | Plan Q9=A, FD BR-U5-12 | `test_worker.py -k injectable_clock` (reloj falso avanza 25 s ⇒ 5 ventanas) |

### 2.3 Seguridad (Security — extensión SECURITY blocking)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U5-SEC-01 | **Sin privilegios en el MVP**: el paquete no usa sockets crudos, capabilities ni `hostNetwork` (solo simulador/fixtures); imagen **non-root** (NFR-SEC-02); el diseño AF_PACKET con `securityContext` (`CAP_NET_RAW/NET_ADMIN`, evaluación OQ-01 de `CAP_SYS_ADMIN`) queda documentado para U9 | Plan Q4=A, FD §5, FR-TRAF-02 | `grep -r scapy src/` vacío; Dockerfile `USER` no-root; sin `capabilities` en manifiestos de U5 (no existen hasta U9) |
| NFR-U5-SEC-02 | **Config estricta**: claves `SENTINEL_TRAFFIC_*` desconocidas ⇒ `ConfigError` (typo no pasa silencioso); `window ∈ {1,5,10,30,60}`, `sim_rate > 0`, `interface`/`sensor_id` no vacíos, `fallback=false` ⇒ `ConfigError` | Plan Q5=A, FD BR-U5-01/02/05 | `test_config.py -k strict_env / -k window_values / -k fallback_false_rejected` |
| NFR-U5-SEC-03 | **Sin payload y secretos mínimos**: contratos U1 `extra="forbid"` (imposible transportar payload/MAC/puerto de tráfico IP); solo secreto = `SENTINEL_INGEST_TOKEN` (hereda comparación constante de U2); los logs del sensor **nunca** incluyen el token | FR-TRAF-03, IP2, FD BR-U5-08 | `test_minimal_fields.py -k no_payload`; test de log: token ausente |

### 2.4 Mantenibilidad (Maintainability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U5-MNT-01 | Gate de cobertura **≥ 70% en `src/sentinel/traffic/`** en el job `test` (misma bar que `core/` TS-U2-10, `gui/` U3, `discovery/` TS-U4-08) | Plan Q6=A | `coverage report --include='*/traffic/*' --fail-under=70` en CI |
| NFR-U5-MNT-02 | **Tests sin red real ni sockets crudos**: todo con `SimulatedSource`/`FixtureSource` + `TestClient`; sin `socket` crudo, sin `scapy`, sin binarios de red; la captura real queda documentada | Plan Q7=A, FD BR-U5-32/33 | revisión de tests (sin apertura de sockets); suite verde en CI sin red |
| NFR-U5-MNT-03 | **PBT de agregación de ventanas** (adicional a los tres designados en NFR-TECH-03): (a) las ventanas particionan la línea temporal sin solapes ni huecos, (b) Σ `packet_length_bytes` de los grupos == Σ bytes de los eventos de la ventana, (c) mismo `(seed, rate)` ⇒ mismas observaciones | Plan Q8=A, `hypothesis` dev | `pytest tests/property/test_window_aggregation.py` en job `test` |
| NFR-U5-MNT-04 | Logging hereda `foundation.logging` (`component=traffic.*`, `event` canónico snake_case: `arp_rate`, `sensor_export_failed`, `sensor_source_error`); métricas: **sin familias ni endpoints propios** — el sensor no expone `/metrics` (unit-of-work §U5) | BR-12/20..22 U1, FD §1 | test de log JSON; sin servidor de métricas en `traffic/` |
| NFR-U5-MNT-05 | `ruff check` + `ruff format --check` + `mypy` en verde sobre `traffic/` (hereda TS-04/05) | TS-04/05 | job `lint`/`typecheck` de CI |

### 2.5 Stack técnico (Tech Stack)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U5-TECH-01 | **Sin dependencias pip nuevas**: stdlib (`argparse`, `datetime`, `uuid`, `math`) + `httpx` + `foundation.*`; `hypothesis` solo en dev; **sin `scapy`** (captura real documentada, D-U5-07) | FD Q3=A, Plan Q4/Q7=A | `requirements.txt` sin cambios de runtime en U5 |
| NFR-U5-TECH-02 | **Config estricta y determinista**: `TrafficSettings` (`frozen`, `extra="forbid"`), defaults de lab (seed 42, rate 50, window 5, interface eth0, sensor-0) | FD §3.1, Plan Q5=A | `test_config.py -k defaults / -k strict_env` |
| NFR-U5-TECH-03 | **Determinismo del simulador**: misma terna `(sim_seed, sim_rate, fixtures)` ⇒ misma secuencia de eventos y mismas observaciones (GT-04/GT-05 reproducibles sin red) | FD BR-U5-07, Plan Q1/Q7 | `test_source.py -k deterministic_seed` + PBT (MNT-03 c) |
| NFR-U5-TECH-04 | **CLI stdlib `argparse`**: `--once` (tests/CI) y `--loop` (demo/U9), exit 0/1; mismo worker (reloj y fuente inyectables) | FD BR-U5-29/30, patrón U4 | `test_cli.py -k exit_codes` |

### 2.6 Usability

**No aplica a U5** (sin UI; la única unidad con UI es U3 — NFR-TECH-04).

---

## 3. Trazabilidad con NFR globales

| NFR global | Contribución de U5 |
|---|---|
| NFR-PERF-02 (sensor ≥10k flows/s, not binding) | PERF-01: baseline informativo en CI + validación real en lab (Build & Test) |
| NFR-AVAIL-01 (single sensor, sin HA) | AVAIL-01/02: loop anti-frágil, degradación por capas, sin estado |
| NFR-SEC-01 (SECURITY blocking) | SEC-01/02/03 (sin privilegios MVP, config estricta, sin payload/token en logs) |
| NFR-SEC-02 (non-root, "except sensor capabilities") | SEC-01: non-root en MVP; capabilities documentadas para U9 (OQ-01 en NFR Design/Infra) |
| NFR-OPS-01 (Helm values) | TECH-02 + FD §5: env `SENTINEL_TRAFFIC_*` listas para el mapeo de U9 |
| NFR-OPS-02 (pipeline CI) | MNT-01/02/03/05 dentro de lint/test heredado |
| NFR-TECH-02 (Python 3.11, scapy, nmap parser) | TECH-01: scapy queda **documentado** para U5 (sin dep, FD Q3=A) |
| NFR-TECH-03 (PBT: Nmap XML, flow, baseline) | MNT-03: PBT **adicional** de agregación (no designado; refuerzo) — los designados ya están en U2/U4; baseline en U6 |

---

## 4. Criterios de aceptación del assessment

- [x] Las 9 preguntas del plan respondidas sin ambigüedad (todas A).
- [x] Categorías evaluadas con justificación de omisión (Usability no aplica; Availability parcial cerrada en FD).
- [x] Todo NFR tiene forma de verificación (ninguno "estándar/típico" sin medición).
- [x] Sin contradicción con `implementation-scope.md`, FD de U5 (Q1–Q13, D-U5-01..09), NFR-TECH-03/SEC-02 ni TS heredados.

---

## 5. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
