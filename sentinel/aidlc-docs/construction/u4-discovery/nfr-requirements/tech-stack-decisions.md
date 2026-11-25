# Tech Stack Decisions — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — NFR Requirements
**Fecha**: 2026-11-16
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U4 — `src/sentinel/discovery/`
**Nota**: decisiones de la **unidad**; hereda TS-01..11 de U1, TS-U2-01..10 de U2, TS-U3-01..11 de U3 y el stack global de `requirements.md` §4. Plan NFR Q1–Q9 = A.

---

## 1. Tabla de decisiones

| # | Decisión | Elegida | Alternativas descartadas | Justificación | Origen |
|---|---|---|---|---|---|
| TS-U4-01 | Sondas ARP/ICMP/TCP | **stdlib**: tabla del sistema (`ip neigh`/`arp -a`), binario `ping`, `socket.connect` — subprocess sin shell | scapy (dep pesada + exige `cap_net_raw`, rompe non-root); nmap para todo (no distingue fases ni aporta MAC sin -sn/ARP) | NFR-SEC-02 non-root sin caps; FD D-U4-05; cero deps nuevas | Plan Q5=A |
| TS-U4-02 | Detección de servicios | **nmap** `-sT -sV --version-light -oX -` (paquete del distro, **sin pin de versión**) | scapy/enum propio (menos preciso); NSE/`-A` (prohibidos por FR-DISC-02); pin ≥7.90 (restringe imágenes sin beneficio) | FR-DISC-02; fallback fixtures si falta (BR-U4-18) | Plan Q9=A, FD §3.4 |
| TS-U4-03 | Parser XML de nmap | **stdlib `xml.etree.ElementTree`** con manejo de error controlado + **PBT `hypothesis`** (dev) | lxml/defusedxml (dep extra; ElementTree basta con parser propio y validación); regex sobre XML (frágil) | NFR-TECH-03 designado a U4; P6 sin deps | NFR-TECH-03, NFR-U4-MNT-03 |
| TS-U4-04 | Config de unidad | **`DiscoverySettings`** (Pydantic `frozen`, `extra="forbid"`) + loader propio `SENTINEL_DISCOVERY_*`, fail-fast | claves en `CoreSettings` (rompe BR-06: exactamente 4 claves); archivo YAML (U9 llega como env); CLI-only (sin env para el CronJob) | FD Q2=A, Plan Q8=A, patrón `foundation.config` | FD §3.1 |
| TS-U4-05 | Cliente de ingesta | **`httpx`** + `foundation.retry.with_retries` (attempts=5, backoff exponencial ± jitter) con Bearer `SENTINEL_INGEST_TOKEN` | retry infinito (D-U4-03: presupuesto de U1 BR-23); `requests` (no está en deps); sin retry (services.md §3 lo exige) | services.md §3, TS-U2-09, FD §3.5 | Plan Q5=A (FD) |
| TS-U4-06 | Programación periódica | **CLI stdlib `argparse`**: `--once` (CronJob U9, tests) y `--loop --interval` (demo sin chart) | hilo dentro del Core (rompe frontera "colectores solo foundation"); librerías `schedule`/`croniter` (dep innecesaria; el CronJob de K8s es el scheduler real) | FR-DISC-03, FD Q4=A, Dockerfile ya documenta `python -m sentinel.discovery` | FD §3.7 |
| TS-U4-07 | Puente runner ↔ API | **`CycleRunnerImpl`** en `discovery/runner.py`, inyectado en `create_app` por **import perezoso** (bloque try/except, igual que `gui`) | entrypoint nuevo con CMD distinto (GT-02 dejaría de funcionar en la imagen estándar); worker dentro de `core/` (rompe la frontera de imports) | FD Q15=A, GT-02, unit-of-work §imports | FD §3.8 |
| TS-U4-08 | Gate de cobertura | **≥ 70% en `src/sentinel/discovery/`** (`--include='*/discovery/*' --fail-under=70`) | solo el global 70% (diluye el gate); ≥90% (bar inconsistente con TS-06/TS-U2-10/TS-U3-08) | Mismo bar que las unidades anteriores | Plan Q6=A |
| TS-U4-09 | Estrategia de tests | **FixtureScanner + mocks de subprocess + TestClient**; cero red real; fixtures XML/ARP deterministas | loopback real en CI (depende de red/binarios); red LAN (no portable a runners) | Plan Q7=A; los AC de U4 son `pytest` + `grep` de logs | NFR-U4-MNT-02 |
| TS-U4-10 | PBT | **Obligatorio: parser Nmap XML** en `tests/property/` (4 propiedades, MNT-03) | sin PBT (NFR-TECH-03 designa Nmap XML a esta unidad); PBT de scope/config (innecesario: validación determinista con casos) | NFR-TECH-03 (`requirements.md` §5) | NFR-U4-MNT-03 |
| TS-U4-11 | Logging y métricas | **`foundation.logging`** (`component=discovery.worker`, eventos canónicos snake_case) + contadores `cycles_total`/`cycles_failed_total` en el Core (FQ1=C: sin reporte standalone) | métricas propias del worker en otro puerto (FQ1=C descarta; dos fuentes rompen U7); familias nuevas fuera del contrato U1 | FD §3.6, FQ1=C, D-U4-01/02, BR-20..22 U1 | Plan (FD) Q8+A |
| TS-U4-12 | Aislamiento de subprocess | **`shell=False` + argv lista + PATH fijo de la imagen** + whitelist de flags previa | nsjail/bubblewrap (complejidad/dep para lab); `shell=True` con string (inyección) | Plan Q4=A, NFR-SEC-01 | NFR-U4-SEC-02 |

---

## 2. Dependencias que U4 añade

**Pip: NINGUNA** (runtime y dev). U4 usa stdlib + `httpx` (heredado) + `hypothesis` (dev, ya presente desde U1) + toolchain heredada.

**Binarios de sistema (runtime, opcionales según entorno)**:

| Binario | Uso | Si falta |
|---|---|---|
| `nmap` | Detección de servicios (FR-DISC-02) | `FixtureScanner` + warning (BR-U4-18) — el ciclo no falla |
| `ping` (busybox/iputils) | Fase ICMP echo | fase ICMP omitida con warning (ARP/TCP siguen) |
| `ip`/`arp` (busybox/iproute2) | Tabla de vecinos ARP | fase ARP vacía con warning |

---

## 3. Impacto en artefactos heredados

| Artefacto | Cambio requerido por U4 |
|---|---|
| `requirements.txt` | **sin cambios** (cero deps nuevas) |
| `Dockerfile` (U1) | **+ `nmap`** en `apk add` (escaneo real en la demo; opcional por fallback — decisión de Code Generation); busybox ya aporta `ping`/`ip` |
| `.github/workflows/ci.yml` | job `test`: añadir gate `coverage report --include='*/discovery/*' --fail-under=70` (junto al gate `gui/`) |
| `src/sentinel/core/*` y `foundation/*` | ediciones acotadas ya aprobadas en FD §4 (`Batch.reconcile`, `METRIC_FAMILIES`, scope en ruta discovery, `CycleCounter`, runner lazy) |
| `pyproject.toml` | sin cambios (ruff/mypy/pytest ya cubren `src/`) |
| `deploy/helm/` (U9) | sin cambios aquí: U9 mapeará `values.yaml` → `SENTINEL_DISCOVERY_*` (NFR-OPS-01) y definirá el CronJob `--once` |

---

## 4. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
