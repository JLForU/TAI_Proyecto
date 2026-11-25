# NFR Design Patterns — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — NFR Design (Parte 2: Generation)
**Fecha**: 2026-11-16
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U4 — `src/sentinel/discovery/`
**Decisiones (plan Q1–Q8)**: **A en todas** — loop continúa tras fallo por ciclo (sin circuit breaker); concurrencia CronJob↔manual aceptada con dedup de U2; `ThreadPoolExecutor` acotado 32 hilos por fase; timeouts de sonda fijos (`ping -W 1`, connect 1 s); datos de red validados por el contrato Pydantic U1 + logs JSON (sin sanitización extra); inyección por constructor con defaults reales; `CycleCounter` inyectado como `ApiRequestCounter`; gate de cobertura como step de CI separado.
**Entradas**: `nfr-requirements/*` (NFR-U4-*, TS-U4-01..12), Functional Design de U4 (BR-U4-01..36, D-U4-01..08), `foundation` (retry, logging, models, metrics_contract), U2 (`core/discovery/trigger.py`, `core/metrics/collect.py`).

---

## 1. Patrones de Resilience

### P1 — Fallos por ciclo en el `--loop` (→ NFR-U4-AVAIL-01/02, Q1=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Un ciclo fallido se registra (`event=discovery_cycle_failed` + causa: `scope_violation\|timeout\|scanner_error\|ingestion_error`) y el worker **duerme hasta el siguiente intervalo** para correr el siguiente ciclo; los fallos son **por ciclo**, sin estado acumulado entre ciclos, **sin circuit breaker** ni contador de fallos consecutivos |
| `--once` | Un solo ciclo ⇒ exit 1 ante `failed`/`timeout` (BR-U4-32) — la gestión de reintentos la tiene K8s (CronJob/Job backoff de U9) |
| No hace | Sin persistencia de estado (worker sin BD, AVAIL-02); sin degradación de intervalo (backoff entre ciclos) ni alertas propias (FQ1=C) |
| Verificación | Test de loop con runner que falla 2 veces: ambos ciclos se intentan, el worker sigue vivo entre ellos, sin efectos acumulados; `test_cli -k exit_codes` |

### P2 — Concurrencia aceptada: CronJob `--once` ↔ trigger manual (→ Q2=A, lock de U2)

| Elemento | Diseño |
|---|---|
| Mecanismo | El lock único de U2 (409) protege **solo** los runs API dentro del proceso Core; el CronJob de U9 corre `--once` como proceso aparte — **dos escaneos simultáneos son aceptables en lab**: cada ciclo es independiente y el **dedup UUIDv5 de U2** absorbe las observaciones duplicadas (mismo contenido ⇒ mismo `dedup_key` ⇒ `deduplicated`) |
| Límite documentado | Sin lock cross-proceso en el MVP (requeriría almacenamiento compartido — frontera "sin DB" del worker); se registra como limitación conocida para threat model/operaciones de U10/U11 |
| No hace | Sin fichero de lock, sin consulta best-effort a `GET /discovery` (sin atomicidad ⇒ falsa seguridad), sin serialización entre workloads |
| Verificación | Test de dos `run_cycle` concurrentes con `FixtureScanner` ⇒ ambos completan, el segundo POST deduplica (`deduplicated ≥ 1`); nota de limitación en el summary |

### P3 — Degradación por capas (heredada de NFR-U4-AVAIL-01, sin pregunta)

| Elemento | Diseño |
|---|---|
| Mecanismo | (a) sin binario nmap ⇒ `FixtureScanner` + `event=scanner_fallback` (warning); (b) sin `ping`/fase no viable ⇒ fase omitida con warning, el ciclo continúa; (c) Core caído ⇒ `with_retries` ×5 (backoff 0.5·2ⁿ ≤30 s ± jitter) ⇒ si se agota, `IngestionError` ⇒ ciclo `failed` (D-U4-03) |
| Orden | El fallo **nunca** deja el ciclo "a medias": o termina (`completed`/`timeout` con lote) o falla explícito (`failed` sin lote) |
| Verificación | `test_scanner -k fallback_fixtures`; `test_client -k retry_exhausted`; test de fase sin `ping` mockeado ⇒ warning + ciclo completo |

---

## 2. Patrones de Performance

### P4 — Fases con presupuesto + paralelismo acotado (→ NFR-U4-REL-01/TECH-04, Q3=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Reparto fijo del deadline: **arp 20% / icmp 30% / tcp 30% / nmap 20%** de `timeout_seconds` (constantes testeables); dentro de las fases **ICMP y TCP** usan un `ThreadPoolExecutor(max_workers=32)` (shutdown ordenado, sin hilos huérfanos) para cubrir hasta 1000 targets dentro del cupo; ARP y nmap son **una sola llamada** por fase |
| Determinismo | Los resultados de las sondas paralelas se **normalizan al fusionar** (orden por IP canónico antes de construir `CycleResult`) ⇒ mismo escenario ⇒ mismo lote byte a byte (dedup estable) |
| No hace | Sin async/event loop (stdlib sync basta); sin límite dinámico de hilos por load; sin pre-scan de hosts vivos |
| Verificación | `test_worker -k phase_budget` (fase lenta simulada ⇒ las demás aún corren); test de determinismo: mismo fixture ⇒ lotes idénticos; revisión de `max_workers=32` |

### P5 — Timeouts de sonda fijos (→ Q4=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Constantes de módulo: `PING_TIMEOUT_S = 1.0` (`ping -c 1 -W 1`), `CONNECT_TIMEOUT_S = 1.0` (`socket.create_connection`), tabla ARP instantánea (`ip neigh` es lectura local) — dentro de los cupos de fase (P4) |
| Por qué fijos | Sin claves nuevas en el loader estricto (TECH-03); valores testeables y documentados; configurables solo si el lab lo pide (futuro U9) |
| No hace | Sin env `SENTINEL_DISCOVERY_*_TIMEOUT`; sin timeout por host adaptativo |
| Verificación | Test unitario de constantes + test con sonda lenta mockeada que no supera su cupo |

---

## 3. Patrones de Security

### P6 — Confianza cero en datos de red (→ NFR-U4-SEC-04/SEC-01, Q5=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Todo hallazgo cruza la frontera de contrato: `HostFinding` → **`DiscoveryObservation` (Pydantic U1)** antes del POST — longitudes ≤255, IP/MAC canónicos, puertos 1..65535, `method` en el `Literal`; los logs son **JSON estructurado** (`foundation.logging`) con campos separados ⇒ el contenido de red (hostname, service, version) nunca se interpreta como formato de log (sin log injection) |
| No hace | Sin sanitización extra de control chars (los datos son legítimos y ya validados); sin escaping agresivo de no alfanuméricos (rompería servicios reales como `Apache httpd 2.4`) |
| Verificación | Test: hallazgo con `hostname` hostil (`\n`, `<script>`, 300 chars) ⇒ `ValidationError`/recorte del modelo U1, jamás llega al POST; test de log: payload JSON con `event` canónico y sin campos arbitrarios |

### P7 — Subprocess endurecido (heredado de NFR-U4-SEC-02, sin pregunta)

| Elemento | Diseño |
|---|---|
| Mecanismo | `subprocess.run([argv...], shell=False)` con lista construida por `build_nmap_argv` + `validate_scan_options` (whitelist previa); PATH fijo de la imagen; fixtures bajo `tests/fixtures/` con resolución canónica (sin traversal); sin NSE/scripts jamás |
| Verificación | `test_nmap_args -k no_aggressive_flags`; test de metacaracteres en argv; revisión `grep shell=True src/` vacío |

### P8 — Allowlist como control perimetral (heredado de NFR-U4-SEC-01, sin pregunta)

| Elemento | Diseño |
|---|---|
| Mecanismo | Doble validación (worker siempre + API condicional, FD §3.2); fuera de alcance ⇒ sin paquetes + `scope_violation`; ports/métodos acotados por config |
| Verificación | `test_scope_validation -k out_of_scope / -k api_pre_run_400` |

---

## 4. Patrones de Maintainability

### P9 — Seams de inyección por constructor (→ NFR-U4-MNT-02, Q6=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `run_cycle(settings, scanner, ingest_client, timeout_seconds)` y `CycleRunnerImpl(scanner=..., ingest_client=..., settings=...)` con **defaults reales** en producción (`NmapScanner`/`auto`, `IngestClient` httpx, `load_discovery_settings()`); los tests construyen: `FixtureScanner` + `httpx.Client(transport=MockTransport)` + `DiscoverySettings` de test |
| Por qué | Cero monkeypatch de módulos (tests estables ante refactor), mismo espíritu que `runner`/`http_client`/`api_base` de `create_app` en U2/U3 |
| No hace | Sin contenedor DI/registry (peso innecesario); sin variables globales de módulo para escáner/cliente |
| Verificación | Test de ciclo completo con los 3 seams inyectados sin tocar red ni binarios; revisión de firmas con defaults |

### P10 — `CycleCounter` por inyección (→ FD Q8, Q7=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `create_app` instancia `CycleCounter` (en `core/metrics/collect.py`, espejo de `ApiRequestCounter`) y lo pasa a `DiscoveryTrigger(..., counter=...)` y a `collect(..., cycles=...)`; `DiscoveryTrigger._execute` incrementa `cycles_total` (todo run) y `cycles_failed_total` (`failed`/`timeout`) junto al log `discovery_cycle_failed` |
| No hace | Sin estado global de módulo (aislamiento entre tests); sin persistencia del contador (en proceso, como los demás — U7 lo proyecta) |
| Verificación | Test de trigger con counter inyectado: 1 completed + 1 failed ⇒ `(total=2, failed=1)`; `collect()` muestra ambas familias; `test_discovery_failure -k metrics_increment` |

### P11 — Gate de cobertura como step separado (→ NFR-U4-MNT-01, Q8=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Job `test` de `ci.yml`: paso propio `Discovery coverage gate` ⇒ `coverage report --include='*/discovery/*' --fail-under=70` sobre el **mismo** `.coverage` (espejo exacto del gate `gui/`; ~0 s, sin re-ejecutar tests) |
| No hace | Sin segunda invocación de pytest; sin gate unificado que oculta el paquete culpable |
| Verificación | El step está presente en `ci.yml`; en local el mismo comando pasa con `discovery/` ≥70 |

### P12 — PBT del parser Nmap XML (heredada de NFR-U4-MNT-03, sin pregunta)

| Elemento | Diseño |
|---|---|
| Mecanismo | `tests/property/test_nmap_xml.py` con `hypothesis`: (a) XML válido ⇒ hosts/puertos/estados/servicios correctos, (b) normalización idempotente, (c) XML malformado/truncado ⇒ error controlado (`ScannerError`, nunca crudo), (d) merge por host conserva método preponderante `nmap>tcp>icmp>arp` |
| Verificación | `pytest tests/property/test_nmap_xml.py` en job `test` (junto a los PBT de U1/U2) |

---

## 5. Patrón de Scalability (cerrado — sin pregunta)

### P13 — Cap de 1000 targets con lote único (→ NFR-U4-SCAL-01, heredado)

| Elemento | Diseño |
|---|---|
| Mecanismo | `resolve_targets` valida la expansión de cidr/lista contra **1000** (alineado a `MAX_BATCH_ITEMS` y `DiscoveryRequest`); exceso en config ⇒ `ConfigError`; 1 obs/host ⇒ **un solo POST** por ciclo siempre |
| Crecimiento | Entorno >1000 hosts o multi-subnet se revisa en **U11** (misma bar que NFR-U2-SCAL-01/U3): partir lotes o multi-worker — sin cambio de diseño hoy |
| Verificación | `test_config_validation -k target_cap`; test de expansión de /22 con cap |

---

## 6. Trazabilidad de patrones → NFR

| NFR (U4) | Patrón |
|---|---|
| NFR-U4-PERF-01 | P4 (presupuesto+paralelismo; baseline informativo en tests de code-gen) |
| NFR-U4-SCAL-01 | P13 |
| NFR-U4-AVAIL-01/02 | P1, P3 |
| NFR-U4-REL-01 | P4 |
| NFR-U4-SEC-01 | P8 |
| NFR-U4-SEC-02 | P7 |
| NFR-U4-SEC-03 | heredado (sin scapy/caps — TS-U4-01; sin pregunta) |
| NFR-U4-SEC-04 | P6 |
| NFR-U4-MNT-01 | P11 |
| NFR-U4-MNT-02 | P9 |
| NFR-U4-MNT-03 | P12 |
| NFR-U4-MNT-04 | P10 + logs canónicos (FD D-U4-02) |
| NFR-U4-TECH-01..04 | P4 (TECH-04), P5 (TECH-03), config estricta heredada (FD §3.1) |
