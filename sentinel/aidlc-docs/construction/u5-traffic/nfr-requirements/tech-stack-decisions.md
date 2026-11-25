# Tech Stack Decisions — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — NFR Requirements
**Fecha**: 2026-11-18
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/`
**Nota**: decisiones de la **unidad**; hereda TS-01..11 de U1, TS-U2-01..11 de U2, TS-U3 de U3, TS-U4-01..12 de U4 y el stack global de `requirements.md` §4. Plan NFR Q1–Q9 = A.

---

## 1. Tabla de decisiones

| # | Decisión | Elegida | Alternativas descartadas | Justificación | Origen |
|---|---|---|---|---|---|
| TS-U5-01 | Fuente de paquetes | **Protocolo `PacketSource` + `SimulatedSource` determinista** (seed + rate) + `FixtureSource` (JSON versionado) | scapy `AsyncSniffer` ya en MVP (dep + caps, rompe non-root y CI); solo fixtures estáticos (sin GT-04 paramétrico); captura real implementada (FD Q3=A la documenta) | FD Q3/Q13=A; NFR-SEC-01 sin privilegios; GT-04/GT-05 reproducibles | FD §3.2, Plan Q4/Q7 |
| TS-U5-02 | Captura real AF_PACKET | **Solo documentada** en FD/domain-entities §5 (diseño scapy sobre AF_PACKET/TPACKET_V3 + SPAN/mirror + capabilities); sin código ni dep | scapy en `requirements.txt` (dep pesada sin uso en CI/demo); TPACKET_V3 crudo con ctypes (complejidad sin ejecución real) | implementation-scope M3; FD D-U5-07 (`fallback=false` ⇒ ConfigError) | FD Q3=A, Plan Q4=A |
| TS-U5-03 | Agregación de ventanas | **Tumbling epoch-aligned UTC** (stdlib `datetime`), acumulador en memoria por ventana, proyección a `TrafficObservation` | sliding windows (complejidad sin requisito); ventanas monotonic (se desfasa del Core/Prometheus); stateful store entre ventanas (sin estado = frontera) | FD BR-U5-12..18, Plan Q9=A | FD §3.3, Plan Q9=A |
| TS-U5-04 | Reloj | **Protocolo de reloj inyectable** (pared UTC en prod, reloj falso en tests); `monotonic` solo para backoff de reintentos | `datetime.now` directo (tests con `sleep` o monkeypatch frágil); monotonic para ventanas (D-U5: imposible alinear timestamps externos) | NFR-U5-REL-01, tests sin sleep | Plan Q9=A |
| TS-U5-05 | Config de unidad | **`TrafficSettings`** (Pydantic `frozen`, `extra="forbid"`) + loader propio `SENTINEL_TRAFFIC_*`, fail-fast | claves en `CoreSettings` (rompe BR-06 U1); YAML montado (U9 llega como env); CLI-only (sin env para Deployment) | FD Q2=A, patrón `foundation.config`, Plan Q5=A | FD §3.1 |
| TS-U5-06 | Cliente de export | **`httpx` + `foundation.retry.with_retries` (attempts=5, backoff ± jitter)** espejo de `discovery/client.py`, Bearer `SENTINEL_INGEST_TOKEN`, **chunking ≤1000** por ventana | importar `discovery.client` (acoplamiento entre unidades); retry infinito (D-U5-05); `requests` (no está en deps); sin retry (services.md §3 lo exige) | FD Q8/Q9=A, Plan Q2=A, TS-U2-09 | FD §3.5, Plan Q2=A |
| TS-U5-07 | Endpoint de ingesta | **`POST /api/v1/ingest` genérico de U2** (Batch con discriminador `source`); sin editar U2 | alias `/ingest/traffic` (edición acotada innecesaria; la historia es documented-only); endpoint dedicado nuevo (duplica contrato) | FD Q7=A, D-U5-04 | FD §3.5 |
| TS-U5-08 | CLI | **stdlib `argparse`**: `--once` (tests/CI) y `--loop` (demo, Deployment U9); mismo `run_window` | librerías `schedule`/`croniter` (dep innecesaria; el Deployment/K8s es el orquestador); solo `--once` (sin demo continua) | FD Q12=A, Dockerfile U1 ya documenta `python -m sentinel.traffic` | FD §3.6 |
| TS-U5-09 | Gate de cobertura | **≥ 70% en `src/sentinel/traffic/`** (`--include='*/traffic/*' --fail-under=70`) | solo el global 70% (diluye el gate); ≥90% (bar inconsistente con TS-06/TS-U2-10/TS-U3/TS-U4-08) | Mismo bar que las unidades anteriores | Plan Q6=A |
| TS-U5-10 | Estrategia de tests | **`SimulatedSource`/`FixtureSource` + reloj falso + `TestClient`**; cero red real, cero sockets crudos, cero scapy | loopback real para el POST (depende de red); red LAN/SPAN (no portable a CI); mocks de time con `sleep` (lento/frágil) | Plan Q7/Q9=A; AC de U5 son `pytest` + logs | NFR-U5-MNT-02 |
| TS-U5-11 | PBT | **Adicional: agregación de ventanas** en `tests/property/test_window_aggregation.py` (partición, conservación de bytes, determinismo) — `hypothesis` dev ya presente | sin PBT (la lógica central de U5 se beneficia; NFR-TECH-03 no lo designa pero tampoco lo prohíbe); PBT de config (validación determinista con casos) | Plan Q8=A, NFR-U5-MNT-03 | Plan Q8=A |
| TS-U5-12 | Logging y métricas | **`foundation.logging`** (`component=traffic.*`, eventos canónicos `arp_rate`/`sensor_export_failed`/`sensor_source_error`); **sin `/metrics` propio ni familias nuevas** | servidor de métricas en el sensor (unit-of-work §U5 lo prohíbe; dos fuentes rompen U7); familias nuevas en U1 (innecesarias: R-02 usará `sentinel_arp_messages_total`) | FD §1/§3.4, unit-of-work §U5, D-U5-08 | FD BR-U5-19/28, Plan Q1 |
| TS-U5-13 | Manejo de ráfaga ARP | **Chunking ≤1000 por ventana** (POSTs secuenciales) | cap con descarte (pierde datos en ráfaga); un solo POST (riesgo 422 en U2) | Plan Q2=A, `MAX_BATCH_ITEMS` U1 | Plan Q2=A |

---

## 2. Dependencias que U5 añade

**Pip: NINGUNA** (runtime y dev). U5 usa stdlib + `httpx` (heredado) + `hypothesis` (dev, ya presente desde U1) + toolchain heredada.

| Paquete | Uso en U5 | Tipo |
|---|---|---|
| *(ninguno nuevo)* | — | — |

> `scapy` (NFR-TECH-02) queda **documentado** para la captura real futura, sin instalarse (TS-U5-02); `nmap` es de U4.

---

## 3. Impacto en artefactos heredados

| Artefacto | Cambio requerido por U5 |
|---|---|
| `requirements.txt` | **sin cambios** (cero deps nuevas) |
| `Dockerfile` (U1) | **sin cambios**: entrypoint `python -m sentinel.traffic` ya documentado (BR-26 U1); imagen non-root existente |
| `.github/workflows/ci.yml` | job `test`: añadir gate `coverage report --include='*/traffic/*' --fail-under=70` (junto a `gui/` y `discovery/`) |
| `src/sentinel/foundation/*` y `core/*` | **sin ediciones**: FD U5 §4 = ninguna (contratos y endpoint ya soportan traffic/arp) |
| `pyproject.toml` | sin cambios (ruff/mypy/pytest ya cubren `src/`) |
| `deploy/helm/` (U9) | sin cambios aquí: U9 mapeará `values.yaml` → `SENTINEL_TRAFFIC_*` (NFR-OPS-01), definirá el Deployment `--loop` con `hostNetwork`/capabilities (FR-TRAF-02, OQ-01) |

---

## 4. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
