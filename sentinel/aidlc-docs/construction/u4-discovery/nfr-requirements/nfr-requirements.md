# NFR Requirements — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 2: Generation)
**Fecha**: 2026-11-16
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U4 — `src/sentinel/discovery/`
**Decisiones (plan Q1–Q9)**: **A en todas** (2026-11-16).
**Entradas**: Functional Design de U4 (aprobado 2026-11-16T17:44:07Z), `requirements.md` §3/§4/§5, U1/U2/U3 `tech-stack-decisions.md`, `implementation-scope.md`.

---

## 1. Alcance

NFR **específicos de U4** (colector de descubrimiento: config de alcance, escaneo por fases con subprocess, ingesta al Core, CLI). Hereda sin cambio TS-01..11 de U1, TS-U2-01..10 de U2 y el stack global (Python 3.11, httpx, foundation).

**Fijados por requisito/aprobados (no se preguntaron)**: **NFR-TECH-03 (PBT designado a U4 para Nmap XML)**, NFR-SEC-02 (non-root), NFR-SEC-01 (SECURITY blocking), FR-DISC-01..06 (métodos, intervalo, modos de scope), NFR-PERF-01 (no vinculante), FD Q1–Q16+FQ1 (config env, fallback fixtures, whitelist, reconcile, exit codes, FQ1=C), `implementation-scope.md` (documented-only: ST-M1-03/04, ST-M2-05).

**Categorías**: Usability **no aplica** (U4 sin UI — única unidad con UI es U3).

---

## 2. Requisitos no funcionales de U4

### 2.1 Rendimiento y capacidad (Performance / Scalability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U4-PERF-01 | Baseline **informativo** de duración de ciclo con `FixtureScanner`: registra duración total y por fase (arp/icmp/tcp/nmap) en la suite **sin gate** en CI; la envolvente real (NFR-PERF-01: <60 s para /24) se valida en el lab durante Build & Test | Plan Q1=A, NFR-PERF-01 | test informativo que imprime tiempos (sin assert de duración) |
| NFR-U4-SCAL-01 | **Cap de 1000 targets por ciclo** (alineado a `MAX_BATCH_ITEMS` y al límite de `DiscoveryRequest`): la expansión de cidr se valida contra el cap y una config que lo supere ⇒ `ConfigError` fail-fast; con ≤1000 targets el lote (1 obs/host) **siempre cabe en un solo POST** | Plan Q2=A, FD §3.1/§3.5 | `test_config_validation.py -k target_cap`; test de expansión de /22 con cap |

### 2.2 Disponibilidad y fiabilidad (Availability / Reliability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U4-AVAIL-01 | **Degradación por capas, nunca ciclo a medias**: sin binario nmap ⇒ `FixtureScanner` + warning (el ciclo termina); fase sin `ping`/red ⇒ se omite con warning; Core caído ⇒ `with_retries` ×5 (backoff) ⇒ si se agota, ciclo `failed` con causa y **exit 1** (BR-U4-32) | FD §3.4/§3.6, D-U4-03/05, Plan Q9=A | `test_scanner -k fallback_fixtures`; `test_client -k retry_exhausted`; `test_cli -k exit_codes` |
| NFR-U4-AVAIL-02 | Worker **sin estado propio**: sin BD, sin caché entre ciclos; cada ciclo es independiente (reentrada); en `--loop`, SIGTERM se atiende **entre** ciclos (no a mitad de un lote en tránsito) | FD §1/§3.7, unit-of-work §U4 | revisión: cero imports de `sqlite3`/`core`; test de dos ciclos consecutivos independientes |
| NFR-U4-REL-01 | **Reparto proporcional del deadline**: arp 20% / icmp 30% / tcp 30% / nmap 20% de `timeout_seconds`; cada fase se corta en su cupo y el ciclo continúa — todas las fases corren siempre dentro del deadline (sin fase glotona) | Plan Q3=A, BR-U4-14 | `test_worker.py -k phase_budget` (fase lenta simulada ⇒ las demás aún corren) |

### 2.3 Seguridad (Security — extensión SECURITY blocking)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U4-SEC-01 | **Allowlist como control de seguridad**: validación de targets **siempre** en el worker (antes de cualquier paquete) y en la API cuando el proceso tiene config de scope (400 `scope_violation` pre-run); whitelist estricta de flags (`-O/-sU/-sS/-sC/--script/-A` rechazados) | FR-DISC-01/02, ST-M1-02, FD §3.2, BR-U4-06..11 | `test_scope_validation -k out_of_scope`; `test_config_validation -k forbidden_scan_methods` |
| NFR-U4-SEC-02 | **Subprocess endurecido**: `shell=False` con argv como lista (nunca string de shell), flags construidos programáticamente, PATH fijo de la imagen, fixtures con path canónico bajo `tests/fixtures/` (sin traversal), sin ejecución de NSE/scripts jamás | Plan Q4=A, NFR-SEC-01 | test: `build_nmap_argv` no contiene shell metacharacters; test de path de fixtures; revisión de `subprocess.run(..., shell=False)` |
| NFR-U4-SEC-03 | **Non-root sin capacidades**: sin scapy ni raw sockets; ARP vía tabla del sistema, ICMP vía `ping` — el worker corre con el usuario de la imagen **sin** `cap_net_raw` añadida (NFR-SEC-02) | Plan Q5=A, NFR-SEC-02, FD D-U4-05 | `grep -r scapy src/` vacío; Dockerfile `USER` no-root; sin `securityContext.capabilities` en manifiestos (U9) |
| NFR-U4-SEC-04 | **Secretos mínimos**: solo `SENTINEL_INGEST_TOKEN` (hereda U2, comparación constante); sin credenciales SNMP (documented-only); los logs del worker nunca incluyen el token ni `NMAP_ARGS` completos si contuvieran credenciales | IP2, ST-M1-04 documented-only, BR-12 U1 | test de log: token ausente en payload; revisión de `client.py` |

### 2.4 Mantenibilidad (Maintainability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U4-MNT-01 | Gate de cobertura **≥ 70% en `src/sentinel/discovery/`** en el job `test` (misma bar que `core/` TS-U2-10 y `gui/` U3) | Plan Q6=A | `coverage report --include='*/discovery/*' --fail-under=70` en CI |
| NFR-U4-MNT-02 | **Tests sin red real**: ningún test de U4 toca la LAN ni binarios de escaneo reales — `FixtureScanner` o subprocess mockeado (`nmap`, `ping`, `ip neigh`); validación de alcance pura; el sondeo real queda para el Build & Test en lab | Plan Q7=A | revisión de tests (sin `socket.connect` externo); suite verde en CI sin red |
| NFR-U4-MNT-03 | **PBT obligatorio del parser Nmap XML** (NFR-TECH-03 designado a U4): propiedades — (a) parsea hosts/puertos/estados/servicios de XML válido, (b) normalización idempotente de hallazgos, (c) XML malformado/truncado ⇒ error controlado (nunca excepción cruda), (d) el merge por host conserva el método preponderante | NFR-TECH-03, `requirements.md` §5, FD §3.4 | `pytest tests/property/test_nmap_xml.py` en job `test` |
| NFR-U4-MNT-04 | Logging hereda `foundation.logging` (`component=discovery.worker`, `event` canónico snake_case — D-U4-02); métricas: **solo** las familias del contrato U1 (con `cycles_total`/`cycles_failed_total` ya agregadas en FD Q8) — sin familias ni endpoints propios del worker (FQ1=C) | BR-12/20..22 U1, FD §3.6, FQ1=C | test de log JSON; `METRIC_FAMILIES` sin crecimientos no aprobados |
| NFR-U4-MNT-05 | `ruff check` + `ruff format --check` + `mypy` en verde sobre `discovery/` (hereda TS-04/05) | TS-04/05 | job `lint`/`typecheck` de CI |

### 2.5 Stack técnico (Tech Stack)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U4-TECH-01 | **Sin dependencias pip nuevas**: stdlib (`subprocess`, `socket`, `ipaddress`, `argparse`, `xml.etree`) + `httpx` + `foundation.*`; `hypothesis` solo en dev | Plan Q5=A, P6 | `requirements.txt` sin cambios de runtime en U4 |
| NFR-U4-TECH-02 | **nmap sin pin de versión**: cualquier distribución que soporte `-sT -sV --version-light -oX -`; paquete del distro en la imagen de lab (U9/Dockerfile); ausente ⇒ fallback fixtures (BR-U4-18) | Plan Q9=A, FR-DISC-02 | test de argv (flags presentes, sin versión); `docker build` verde con y sin nmap documentado |
| NFR-U4-TECH-03 | **Config estricta**: `extra="forbid"` (typo en `SENTINEL_DISCOVERY_*` ⇒ `ConfigError`), `interval_minutes ≥ 1`, `timeout_seconds ∈ [1, 3600]` (límite de U2), puertos 1..65535 sin duplicados, allowlist no vacía | Plan Q8=A, FD §3.1, BR-U4-01..05 | `test_config_validation.py -k strict_env / -k interval_min / -k ports` |
| NFR-U4-TECH-04 | **Reparto de deadline proporcional** (20/30/30/20) codificado como constante testeable; el deadline total sigue siendo `timeout_seconds` de la request/config | Plan Q3=A, NFR-U4-REL-01 | `test_worker.py -k phase_budget` |

### 2.6 Usability

**No aplica a U4** (sin UI; la única unidad con UI es U3 — NFR-TECH-04).

---

## 3. Trazabilidad con NFR globales

| NFR global | Contribución de U4 |
|---|---|
| NFR-PERF-01 (scan <60 s /24, not binding) | PERF-01: baseline informativo en CI + validación real en lab (Build & Test) |
| NFR-AVAIL-01 (sin HA) | AVAIL-01/02: degradación por capas, worker sin estado |
| NFR-SEC-01 (SECURITY blocking) | SEC-01/02/04 (allowlist, subprocess endurecido, secretos mínimos) |
| NFR-SEC-02 (non-root) | SEC-03 (sin scapy/raw sockets/caps) |
| NFR-OPS-01 (Helm values) | TECH-03 + FD §3.1: env `SENTINEL_DISCOVERY_*` listas para el mapeo de U9 |
| NFR-OPS-02 (pipeline CI) | MNT-01/02/05 + MNT-03 (PBT) dentro de lint/test heredado |
| NFR-TECH-02 (Python 3.11, scapy, nmap parser) | TECH-01 (stdlib para U4; scapy queda para U5 — Plan Q5=A); MNT-03 (parser propio) |
| NFR-TECH-03 (PBT: **Nmap XML**, flow, baseline) | **MNT-03: PBT de Nmap XML ejecutado aquí** (designado a U4) |

---

## 4. Criterios de aceptación del assessment

- [x] Las 9 preguntas del plan respondidas sin ambigüedad (todas A).
- [x] Categorías evaluadas con justificación de omisión (Usability no aplica; Availability parcial cerrada en FD).
- [x] Todo NFR tiene forma de verificación (ninguno "estándar/típico" sin medición).
- [x] Sin contradicción con `implementation-scope.md`, FD de U4 (Q1–Q16, FQ1=C, D-U4-01..08), NFR-TECH-03/SEC-02 ni TS heredados.
- [x] NFR-TECH-03 (Nmap XML) **atribuido y verificable en U4** (MNT-03).

---

## 5. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
