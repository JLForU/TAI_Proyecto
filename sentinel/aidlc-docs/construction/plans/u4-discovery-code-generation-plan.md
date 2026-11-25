# Code Generation Plan — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — Code Generation (Part 1: Planning)
**Fecha**: 2026-11-18
**Estado**: AWAITING_APPROVAL — plan listo; esperando aprobación explícita para generar código
**Workspace root**: `/home/jhoseph/Documents/TAI/TAI_Proyecto/sentinel` (de `aidlc-state.md`)
**Patrón**: Greenfield multi-unit (monolith) → `src/{unit-name}/` = **`src/sentinel/discovery/`**, tests = **`tests/unit/discovery/`** (+ `tests/unit/test_config_validation.py`, `tests/unit/test_nmap_args.py` según rutas de los BR) + **`tests/integration/`** + **`tests/property/`**
**Este plan es la única fuente de verdad de Code Generation para U4.**

---

## 1. Contexto de la unidad

- **Historias**: ST-M1-01..04 + ST-M2-01..06 (story map U4: 7 `implemented`, 3 `documented-only`).
  - ST-M1-01 Helm-configurable scope and scheduling · ST-M1-02 Authorized scope validation · ST-M1-03 sensor_id reserved (**documented-only**) · ST-M1-04 SNMP optional (**documented-only**) · ST-M2-01 Periodic ARP/ICMP/TCP discovery · ST-M2-02 Light service/version probing · ST-M2-03 Asset first seen · ST-M2-04 Asset missing after N cycles · ST-M2-05 Port/service change (**documented-only**) · ST-M2-06 Discovery cycle failure handling.
- **Diseño aprobado**: FD (flujos §3.1–3.8, BR-U4-01..36, D-U4-01..08, §4 ediciones acotadas), NFR Requirements (NFR-U4-*, TS-U4-01..12), NFR Design (P1–P13, componentes), Infrastructure Design (ID-U4-01..10: Dockerfile +nmap, CronJob spec para U9, gate CI separado).
- **Dependencias**: **U1** (`foundation.*`: Batch/Model/ScopeError/ConfigError/with_retries/get_logger/METRIC_FAMILIES) y **U2** (`CycleRunner`/`DiscoveryTimeoutError` en `core/discovery/trigger.py`, API `/api/v1/ingest` y `/api/v1/discovery`, `ScopeError`→400 ya montado en `errors.py`) satisfechas. **U9** (CronJob/values) llega después — este plan solo deja el worker y el handoff documentado.
- **Interfaces/contratos**: CLI `python -m sentinel.discovery --once|--loop`; env `SENTINEL_DISCOVERY_{SCOPE_MODE,HOSTS,CIDRS,PORTS,INTERVAL_MIN,TIMEOUT_SECONDS,SCANNER,NMAP_ARGS}`; `POST /api/v1/ingest` con `{"items":[...], "reconcile":bool}` + Bearer; protocolo `CycleRunner.run(hosts, timeout_seconds) -> int` (U2).
- **Límites**: worker **nunca** importa `sentinel.core.*` ni `sqlite3` (solo `foundation` + HTTP); sin server de métricas propio (FQ1=C); sin SNMP (ST-M1-04 documented-only); sin `PortServiceChanged` (ST-M2-05 documented-only); sin objetos K8s (CronJob/NetworkPolicy = U9/U10).
- **Toolchain**: hereda U1/U2/U3 (ruff E,F,W,I,N,UP,B,SIM, mypy, pytest+cov, TestClient, `MockTransport`, `foundation.testing`); **cero deps nuevas** (TS-U4-12); gates: total `--cov=sentinel ≥70` **+** `coverage report --include='*/discovery/*' --fail-under=70` (P11/Q8=A).

---

## 2. Pasos de generación (numerados, checkbox)

- [x] **Step 1 — Project structure setup**
  Crear `src/sentinel/discovery/__init__.py`, `config.py`, `scope.py`, `domain.py`, `scanner.py`, `worker.py`, `client.py`, `runner.py`, `__main__.py`; `tests/unit/discovery/__init__.py` + `tests/unit/discovery/fixtures/` (XML nmap y salida `ip neigh` de ejemplo); `tests/integration/test_{scope_validation,discovery_failure,gt02_new_host,gt03_host_absent}.py` (placeholders), `tests/property/test_nmap_xml.py` (placeholder).

- [x] **Step 2 — Config estricta (BR-U4-01..05/10/11, TS-U4-04, NFR-U4-TECH-03)**
  Crear `src/sentinel/discovery/config.py`: `DiscoverySettings` (Pydantic `frozen`, `extra="forbid"`) con defaults del FD §3.1 (`SCOPE_MODE=explicit_hosts`, `HOSTS=""`, `CIDRS=""`, `PORTS="22,80,443"`, `INTERVAL_MIN=15`, `TIMEOUT_SECONDS=30`, `SCANNER=auto`, `NMAP_ARGS=""`); `load_discovery_settings(env)` ⇒ fail-fast `ConfigError` (allowlist vacía, puertos 1..65535 sin duplicados, interval ≥1, timeout 1..3600, flags prohibidos por whitelist); constantes de sonda (`PING_TIMEOUT_S=1`, `CONNECT_TIMEOUT_S=1`) y presupuestos de fases (20/30/30/20).

- [x] **Step 3 — Scope C12 (BR-U4-06..09, SEC-01, FD §3.2)**
  Crear `src/sentinel/discovery/scope.py`: `validate_scope`, `validate_ports`, `validate_target(host, config)` → `ValidationResult` (ok/motivo); `ScopeError("host fuera de alcance")` para el worker y para el pre-run de la API; puro, sin I/O.

- [x] **Step 4 — Dominio puro (FD §3.3/§3.5, P13, BR-U4-14..16)**
  Crear `src/sentinel/discovery/domain.py`: `ScopeConfig`, `ScanTarget`, `HostFinding`, `CycleResult`, `CycleStatus`; `resolve_targets(config, cap=1000)` (expansión CIDR acotada, dedup); `merge_findings(...)` — 1 `HostFinding` por host, método preponderante `nmap > tcp > icmp > arp`, puertos combinados (servicio/versión nmap gana); decisión `reconcile` (completed⇒true, partial/timeout⇒false, failed⇒sin lote).

- [x] **Step 5 — Unit tests: config + scope (MNT-02)**
  `tests/unit/test_config_validation.py` (BR rutas: `-k invalid_config / -k strict_env / -k interval_min / -k ports / -k forbidden_scan_methods / -k allowlist_required`); `tests/unit/discovery/test_scope.py` (dentro/fuera de allowlist, puertos inválidos, CIDR, `ScopeError`).

- [x] **Step 6 — Escáner (BR-U4-10..13/17/18, FR-DISC-01/02, ST-M2-02)**
  Crear `src/sentinel/discovery/scanner.py`: protocolo `Scanner`; `build_nmap_argv(targets, ports, extra)` con fijos `-sT -sV --version-light -p <allowlist> -oX -` y whitelist (`-sT -sV --version-light -p -oX -oN -Pn -n` + extras); rechazo de `-O/-sU/-sS/-sC/--script/-A`; `NmapScanner` (subprocess `shell=False`: nmap, `ip neigh`, `ping -W 1`), `FixtureScanner` (lee fixtures XML/ARP), `auto` con fallback (D-U4-05); `ScannerError` en XML inválido (error controlado).

- [x] **Step 7 — Unit tests: nmap argv + scanner (BR-U4-10..12, MNT-02)**
  `tests/unit/test_nmap_args.py` (`-k required_flags`, `-k no_aggressive_flags`, extras no crudos); `tests/unit/discovery/test_scanner.py` (FixtureScanner parsea fixtures, auto⇒fixtures sin nmap, XML corrupto ⇒ `ScannerError`, argv `shell=False`).

- [x] **Step 8 — Worker de ciclo (FR-DISC-01/03, BR-U4-14..24, P4, ST-M2-01/03/04)**
  Crear `src/sentinel/discovery/worker.py`: `run_cycle(settings, scanner, ingest_client, timeout_seconds) -> CycleResult`; fases `arp → icmp → tcp → nmap` con chequeo de deadline (`monotonic`, 20/30/30/20); `ThreadPoolExecutor(max_workers=32)` para ICMP/TCP con shutdown ordenado; ICMP omitida con warning si sin binario/permiso (D-U4-05); fusión por host (BR-U4-16); `sensor_id="sensor-0"` (BR-U4-33); ingest con `reconcile` según estado; `hosts_seen`/`hosts_targeted`; nunca lanza fuera de `ConfigError`/`ScopeError` controlados.

- [x] **Step 9 — Unit tests: worker (MNT-02, GT)**
  `tests/unit/discovery/test_worker.py`: `-k deadline_between_phases`, `-k merge_observation`, `-k reconcile_false_on_partial`, `-k sensor_id_default`, `-k cap_targets`, pool acotado, ICMP omitida no rompe.

- [x] **Step 10 — Cliente de ingesta (SEC-04/P6, TS-U4-05, BR-U4-27..30)**
  Crear `src/sentinel/discovery/client.py`: `IngestClient(base_url, token, transport=None)` con `httpx` + `with_retries` ×5 (reintentos solo en 5xx/timeout de red); `to_observations(findings)` → `DiscoveryObservation` (frontera Pydantic U1, 1/host); `post_ingest(items, reconcile)` → `{"accepted", ...}`; errores definitivos ⇒ excepción (worker ⇒ `failed`).

- [x] **Step 11 — Unit tests: client (MNT-02)**
  `tests/unit/discovery/test_client.py` (`MockTransport`: happy path con `reconcile`, retry ×5 en 500, 4xx sin retry, payload 1 por host, Bearer presente).

- [x] **Step 12 — Runner bridge (FD Q15, P9, protocolo U2)**
  Crear `src/sentinel/discovery/runner.py`: `CycleRunnerImpl(settings, scanner, client, timeout_seconds)` — cumple `CycleRunner.run(hosts, timeout_seconds) -> int`; `ScopeError`/errores ⇒ excepción (U2 ⇒ `failed`); deadline ⇒ ingerir parciales con `reconcile=false` + lanzar `DiscoveryTimeoutError` (U2 ⇒ `timeout`); seams por constructor (defaults reales: `load_discovery_settings()`, `NmapScanner/FixtureScanner` por `auto`, `IngestClient`).

- [x] **Step 13 — Unit tests: runner (AVAIL, P1)**
  `tests/unit/discovery/test_runner.py`: éxito ⇒ devuelve `hosts_seen`; timeout ⇒ `DiscoveryTimeoutError` **y** POST parcial con `reconcile=false`; `ScopeError` propaga; sin runner real en red (mocks).

- [x] **Step 14 — CLI (TS-U4-06, ST-M1-01, AVAIL-01/02)**
  Crear `src/sentinel/discovery/__main__.py`: `argparse` `--once` | `--loop --interval <min>`; `ConfigError` ⇒ log + exit 1; ciclo ⇒ exit 0/1; logs `component=discovery.*` (snake_case, D-U4-02); `--loop` respeta `INTERVAL_MIN`/`SENTINEL_DISCOVERY_INTERVAL_MIN`.

- [x] **Step 15 — Unit tests: CLI (MNT-02)**
  `tests/unit/discovery/test_cli.py`: `--once` happy (runner inyectado/mocked) ⇒ exit 0; fallo ⇒ exit 1; `--loop` al menos 2 ciclos con intervalo mínimo; config inválida ⇒ exit 1.

- [x] **Step 16 — Edición acotada U1: `Batch.reconcile` (FD §4, Q7=A)**
  Editar `src/sentinel/foundation/models.py`: `class Batch` + `reconcile: bool = Field(default=True)` (retrocompatible).

- [x] **Step 17 — Edición acotada U1: métrica de fallos (FD §4, Q8=A, P10)**
  Editar `src/sentinel/foundation/metrics_contract.py`: `METRIC_FAMILIES` + `"sentinel_discovery_cycles_failed_total"` (verificar test de catálogo de U7 `collect.py:102` — añadir la familia mantiene el assert en verde porque itera `METRIC_FAMILIES`).

- [x] **Step 18 — Edición acotada U2: reconcile del lote (FD §4, ST-M2-04 AC2)**
  Editar `src/sentinel/core/ingestion/service.py`: `if has_discovery and batch.reconcile:` antes de `reconcile_missing` (un ciclo parcial/timeout jamás incrementa `miss_count`).

- [x] **Step 19 — Edición acotada U2: app — scope condicional + runner lazy + counter (D-U4-04/Q15/Q8)**
  Editar `src/sentinel/core/api/app.py`: parámetro `scope_validator=None`; si el proceso tiene `SENTINEL_DISCOVERY_*` ⇒ construir validador de U4 (import perezoso, `try/except`); `runner=None` ⇒ import perezoso `CycleRunnerImpl` (igual patrón que `gui`); inyectar `CycleCounter` nuevo en `DiscoveryTrigger(db, runner=..., counter=..., scope_validator=...)`.

- [x] **Step 20 — Edición acotada U2: pre-run scope en la API (FD §3.2, SEC-01)**
  Editar `src/sentinel/core/api/routes_discovery.py`: antes de crear el run, `scope_validator.validate_scope(hosts)` ⇒ `ScopeError` (handler U2 ⇒ 400 `scope_violation`) + log `scope_violation`; solo si hay validador (env presente).

- [x] **Step 21 — Edición acotada U2: trigger con counter + log de fallo (FD §4, ST-M2-06)**
  Editar `src/sentinel/core/discovery/trigger.py`: `DiscoveryTrigger(..., counter: CycleCounter | None = None, ...)`; al finalizar ciclo manual: `counter.record(status)`; en `failed`/`timeout`: log `event=discovery_cycle_failed` (run_id, causa) con `get_logger(component="discovery.trigger")`.

- [x] **Step 22 — Edición acotada U2: `CycleCounter` (espejo de `ApiRequestCounter`, P10)**
  Editar `src/sentinel/core/metrics/collect.py`: clase `CycleCounter` (`record(status)` → `cycles_total`/`cycles_failed_total` por status) + samples en `collect()`; mantener assert de familias en verde.

- [x] **Step 23 — Integration tests: scope API + fallo de ciclo (SEC-01, ST-M1-02/06)**
  `tests/integration/test_scope_validation.py`: app con `scope_validator` ⇒ host fuera ⇒ **400 `scope_violation` sin run**; host dentro ⇒ run normal; sin env ⇒ sin validación (compatibilidad U2). `tests/integration/test_discovery_failure.py`: runner que lanza ⇒ run `failed` + log `discovery_cycle_failed` + counter `cycles_failed_total=1`; timeout ⇒ `timeout` con parciales `reconcile=false` (sin `AssetMissing`).

- [x] **Step 24 — GT: nuevo host y host ausente (GT-02/GT-03, ST-M2-03/04)**
  `tests/integration/test_gt02_new_host.py`: app completa + `CycleRunnerImpl` con `FixtureScanner` (hosts A,B) ⇒ primer ciclo ⇒ `AssetFirstSeen` + asset visible. `tests/integration/test_gt03_host_absent.py`: fixture sin host B + `reconcile=true` tras N ciclos ⇒ `AssetMissing`; ciclo `reconcile=false` ⇒ **no** emite `AssetMissing` (ST-M2-04 AC2).

- [x] **Step 25 — PBT Nmap XML (P12, MNT-03)**
  `tests/property/test_nmap_xml.py` (hypothesis): parse de XML bien formado extrae hosts/puertos/servicio; basura ⇒ `ScannerError` (nunca excepción cruda); atributos con caracteres hostiles no rompen el parser; idempotencia de parse.

- [x] **Step 26 — CI: gate de cobertura de discovery (P11/Q8=A, TS-U4-08)**
  Editar `.github/workflows/ci.yml` (workspace root): paso nuevo tras el gate de GUI: `- name: Discovery coverage gate (P11)` → `coverage report --include='*/discovery/*' --fail-under=70`; mantener gate total y GUI.

- [x] **Step 27 — Dockerfile: +nmap (ID-U4-01, TS-U4-02)**
  Editar `Dockerfile`: añadir `nmap` a un `apk add --no-cache` (junto a las libs de U3, sin tocar su capa); sin cambios de `CMD`/usuario.

- [x] **Step 28 — README + docs de la unidad**
  Añadir sección **Discovery** en `README.md`: run local (`python -m sentinel.discovery --once|--loop`), tabla de env `SENTINEL_DISCOVERY_*` con defaults, nota de fallback fixtures, handoff CronJob/NetworkPolicy a U9 (ID-U4-02/05), ST-M1-03/04/05 documented-only.

- [x] **Step 29 — Validación local**
  Ejecutar: `ruff check .` · `ruff format --check .` · `mypy src/sentinel` · `pytest tests/unit tests/property tests/integration -q --cov=sentinel --cov-fail-under=70` + `coverage report --include='*/discovery/*' --fail-under=70` — todo en verde.

- [x] **Step 30 — Resumen de generación**
  Crear `aidlc-docs/construction/u4-discovery/code/code-generation-summary.md`: archivos creados/modificados (separados), ediciones acotadas U1/U2 con verificación, desviaciones D-\*, cobertura total y de `discovery/`, historias ST-M1-01..04/ST-M2-01..06 con estado, estado del repo (sin `.git`).

---

## 3. Historias y trazabilidad

| Historia | Steps | Verificación principal | Estado |
|---|---|---|---|
| ST-M1-01 Helm-configurable scope/scheduling | 2, 14, 28 | env estrictas + `--interval`; `helm template` ⇒ U9/Build & Test| [x] |
| ST-M1-02 Authorized scope validation | 3, 5, 20, 23 | worker rechaza fuera de alcance + API 400 `scope_violation` pre-run| [x] |
| ST-M1-03 sensor_id reserved (documented-only) | 9 (`-k sensor_id_default`), 28 | default `sensor-0`; sin clave nueva| [x] |
| ST-M1-04 SNMP optional (documented-only) | 28 | solo documentación (§4 scope)| [x] |
| ST-M2-01 Periodic ARP/ICMP/TCP discovery | 4, 8, 9, 14 | fases ordenadas + deadline + cap 1000| [x] |
| ST-M2-02 Light service/version probing | 6, 7 | argv `-sT -sV --version-light` + whitelist| [x] |
| ST-M2-03 Asset first seen | 16, 18, 24 | ciclo completo ⇒ `AssetFirstSeen` (GT-02)| [x] |
| ST-M2-04 Asset missing after N cycles | 16, 18, 24 | `reconcile=false` jamás emite `AssetMissing` (GT-03)| [x] |
| ST-M2-05 Port/service change (documented-only) | — | sin código (documented-only)| [x] |
| ST-M2-06 Discovery cycle failure handling | 12, 13, 21, 22, 23 | log `discovery_cycle_failed` + `cycles_failed_total` + status `failed`/`timeout`| [x] |

*Estado `[x]` = código + tests generados y en verde en la validación local (Step 29). Los AC con CronJob/helm/demo se confirman en Build and Test.*

---

## 4. Fuera de alcance de este plan

- CronJob, NetworkPolicy, `values.yaml` de `discovery.*` (U9/U10 — handoff en `deployment-architecture.md` §5).
- SNMP (ST-M1-04), `PortServiceChanged`/E-03 (ST-M2-05), sensor_id configurable (ST-M1-03) — documented-only.
- Servidor de métricas propio del worker, reporte de fallos al Core (FQ1=C), heartbeat en fallo.
- Reemplazo de `collect()` (U7), alerting (U8), GUI de discovery avanzada (U3 ya monta el trigger).
- Build & Test: `helm template`, demo en kind, gate total de imagen (al final de la cadena).

---

## 5. Approval Gate

Para iniciar Part 2: Generation, responde **`Aprobado`** (o pide cambios) — la aprobación cubre el plan completo y la secuencia de los 30 steps.
