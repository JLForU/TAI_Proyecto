# Business Rules & Validation — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-16
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U4 — `src/sentinel/discovery/`
**Traza**: ST-M1-01..04, ST-M2-01..06, FR-DISC-01..06, NFR-TECH-03; plan Q1–Q16 = A + FQ1 = C; `services.md` §2.1/§2.2/§4.

---

## 1. Configuración y arranque (fail-fast)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U4-01 | Loader propio `load_discovery_settings` desde `SENTINEL_DISCOVERY_*` (patrón `foundation.config`); config inválida ⇒ `ConfigError` al arranque — una config inválida no es un estado recuperable | Q2=A, BR-07 U1 | `pytest tests/unit/test_config_validation.py -k invalid_config` |
| BR-U4-02 | **Allowlist vacía ⇒ fail-fast**: `explicit_hosts` con `HOSTS` vacío o `cidr` con `CIDRS` vacío ⇒ `ConfigError`; nada se sondea sin allowlist explícita | Q10=A, FR-DISC-06 | `test_config_validation.py -k empty_allowlist` |
| BR-U4-03 | Defaults de laboratorio: `scope.mode=explicit_hosts`, `ports=22,80,443`, `interval=15 min`, `timeout=30 s`, `scanner=auto` | Q10=A, FR-DISC-01/03 | `test_config_validation.py -k defaults` |
| BR-U4-04 | `CoreSettings` de U1 **no cambia** (exactamente 4 claves `SENTINEL_*`); el worker usa su loader propio; `SENTINEL_INGEST_TOKEN` se lee sin redefinir | Q2=A, BR-06 U1 | revisión de código + `tests/unit/foundation/test_config.py` (sin regresión) |
| BR-U4-05 | Puertos validados al cargar: enteros 1..65535, sin duplicados, no vacíos | C12 `validate_ports` | `test_config_validation.py -k ports` |

## 2. Alcance autorizado — C12 (ST-M1-02)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U4-06 | `validate_target`: `explicit_hosts` ⇒ match exacto en `HOSTS`; `cidr` ⇒ IP dentro de alguno de `CIDRS`; fuera ⇒ `ScopeError("host fuera de alcance")` (`code=scope_violation`) | FR-DISC-06, Q1=A | `tests/integration/test_scope_validation.py -k mode_cidr` / `-k mode_explicit` |
| BR-U4-07 | **Worker**: todo target pasa `validate_target` **antes** de enviar paquetes; fuera de alcance ⇒ sin paquetes + log `event="scope_violation"` + `event="discovery_cycle_failed"` (cause=`scope_violation`) + exit 1 (standalone) / run `failed` (in-process) | ST-M1-02 AC1 | `test_scope_validation.py -k out_of_scope` (log contiene `scope_violation`) |
| BR-U4-08 | **API**: si el proceso Core tiene config de scope, `POST /discovery` con host fuera ⇒ **400** `{"code":"scope_violation"}` **antes** de crear el run (run_id no se genera); sin config en el proceso ⇒ la validación la garantiza el worker (D-U4-04) | services.md §4, Q1=A | `test_scope_validation.py -k api_pre_run_400` |
| BR-U4-09 | Solo se escanean los puertos de la allowlist (`scope.ports`); targets fuera de la allowlist jamás reciben probes | FR-DISC-01, C12 | `test_scope_validation.py -k ports` |

## 3. Métodos de escaneo y argumentos (FR-DISC-02, ST-M2-02)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U4-10 | `validate_scan_options`: whitelist estricta de flags (`-sT`, `-sV`, `--version-light`, `-p`, `-oX`, `-oN`, `-Pn`, `-n` + extras); `-O`, `-sU`, `-sS`, `-sC`, `--script*`, `-A` o flag desconocido ⇒ rechazo (`ConfigError`/`ValidationError`) | ST-M1-02 AC2 | `test_config_validation.py -k forbidden_scan_methods` |
| BR-U4-11 | El argv de nmap se **construye programáticamente** (`build_nmap_argv`); `SENTINEL_DISCOVERY_NMAP_ARGS` se añade solo si pasa la whitelist; jamás se pasa string crudo del usuario a `subprocess` | ST-M2-02 AC2, Q9=A | `tests/unit/test_nmap_args.py -k no_aggressive_flags` |
| BR-U4-12 | Fijos del ciclo: `-sT -sV --version-light -p <allowlist> -oX -` (conexión TCP, detección ligera, sin OS detection, sin NSE, sin UDP) | FR-DISC-01/02 | `test_nmap_args.py -k required_flags` |
| BR-U4-13 | `os_name=None` + `os_provenance="unknown"` en toda observación de U4 (sin `-O`) | FR-DISC-02, D-U4-06 | `test_worker.py -k no_os_detection` |

## 4. Ciclo, tiempo y semántica de hallazgos

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U4-14 | Fases en orden `arp → icmp → tcp → nmap`, cada una con chequeo de deadline (`monotonic`); excedido ⇒ cortar sin iniciar la siguiente | services.md §4, Q6=A | `tests/unit/test_worker.py -k deadline_between_phases` |
| BR-U4-15 | **Timeout conserva parciales**: al vencer el deadline se ingiere lo acumulado (`reconcile=false`) y el ciclo queda `timeout`; en la ruta in-process el runner ingiere **antes** de lanzar `DiscoveryTimeoutError` | services.md §4, Q6=A | `test_worker.py -k timeout_partial` + `test_gt03_host_absent.py -k partial_cycle` |
| BR-U4-16 | **1 observación fusionada por host por ciclo**: método preponderante `nmap > tcp > icmp > arp`; puertos combinados (servicio/versión nmap gana); `hostname` solo si el escáner lo reporta | Q11=A, D-U4-07 | `test_worker.py -k merge_observation` |
| BR-U4-17 | `hosts_seen` = nº de hosts con **≥1 hallazgo** reportado (no los intentados) | Q16=A | `test_worker.py -k hosts_seen` |
| BR-U4-18 | Escáner `auto`: binario `nmap` presente ⇒ `NmapScanner`; ausente ⇒ `FixtureScanner` + `log warning event="scanner_fallback"` (el ciclo no falla por falta del binario) | Q3=A | `tests/unit/test_scanner.py -k fallback_fixtures` |
| BR-U4-19 | ARP vía tabla del sistema (`ip neigh`/`arp -a`); ICMP vía binario `ping`; TCP vía stdlib connect — todo sin raw sockets ni root | FR-DISC-01, D-U4-05 | `test_scanner.py -k unprivileged` (mock de subprocess) |
| BR-U4-20 | PBT del parser XML de nmap con `hypothesis` (hosts, puertos, estados, servicios, XML malformado ⇒ error controlado) | NFR-TECH-03, requirements §5 | `tests/unit/test_nmap_xml.py -k property` |

## 5. Ingesta y reconciliación (frontera U2)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U4-21 | Un **solo** `POST /api/v1/ingest` por ciclo con Bearer `SENTINEL_INGEST_TOKEN` (lote ≤ 1000 items de U1) | Q5=A, services.md §2.1 | `test_client.py -k single_post_per_cycle` |
| BR-U4-22 | Reintentos con `with_retries` (backoff `min(0.5·2ⁿ, 30)` ± jitter, attempts=5); agotados ⇒ `IngestionError` ⇒ ciclo `failed` con causa en log | services.md §3, Q5=A, D-U4-03 | `test_client.py -k retry_exhausted` |
| BR-U4-23 | `reconcile` según estado: `completed ⇒ true`; `timeout`/parcial ⇒ `false`; `failed` ⇒ sin lote | Q7=A, §3.5 | `test_worker.py -k reconcile_flag` |
| BR-U4-24 | Lote con `reconcile=false`: observaciones persistidas y `last_seen` actualizado **sin** incrementar `miss_count` ⇒ ciclo parcial jamás marca `missing` | ST-M2-04 AC2, BR-U2-15 | `test_gt03_host_absent.py -k partial_cycle` |
| BR-U4-25 | Lote `failed`: **no se envía** ⇒ sin reconciliación ⇒ sin `AssetMissing` | ST-M2-06 AC1 | `test_discovery_failure.py -k no_asset_missing` |
| BR-U4-26 | Frontera: el worker solo importa `sentinel.foundation` y HTTP; nunca `sentinel.core` ni `sqlite3` | unit-of-work §imports | revisión de imports (test de arquitectura) |
| BR-U4-27 | U4 **no** implementa `first_seen`/`missing`/eventos E-01/E-02: los decide `InventoryService` de U2 ante el lote | Q12=A | `test_gt02_new_host.py` (end-to-end, sin código de inventario en U4) |

## 6. Fallos de ciclo, log y métricas (ST-M2-06, FQ1=C)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U4-28 | Ruta in-process: al finalizar un run `failed`/`timeout`, `DiscoveryTrigger` incrementa `sentinel_discovery_cycles_failed_total` y emite `log event="discovery_cycle_failed"` con `run_id` y causa; `completed` incrementa solo `sentinel_discovery_cycles_total` | ST-M2-06, Q8=A | `test_discovery_failure.py -k metrics_increment` + `curl :9108/metrics \| grep -E '^sentinel_discovery_cycles_failed_total [1-9]'` |
| BR-U4-29 | Familia nueva `sentinel_discovery_cycles_failed_total` añadida a `METRIC_FAMILIES` (edición acotada U1); `collect()` la expone desde U4, sin labels de alta cardinalidad | Q8=A, NFR-OPS metrics | `tests/unit/foundation/test_metrics_contract.py` (familias) + `test_metrics_render` |
| BR-U4-30 | Ruta standalone (`--once`/CronJob): fallo/timeout ⇒ **solo log local** `event="discovery_cycle_failed"` + causa y **exit 1**; **sin reporte HTTP** al Core (`failed_total` no cambia) | **FQ1=C**, D-U4-01 | `test_worker.py -k standalone_failure_log` (sin POST de reporte) |
| BR-U4-31 | `scope_violation` aparece siempre en el log cuando un target está fuera de alcance (worker: causa del fallo; API: warning previo al 400) | ST-M1-02 AC1 | `test_scope_validation.py -k out_of_scope` |
| BR-U4-32 | Códigos de salida del CLI: `completed ⇒ 0`; `timeout`/`failed` ⇒ `1` (el Job se marca fallido en K8s) | ST-M2-06, §3.7 | `test_cli.py -k exit_codes` |

## 7. Frontera y documented-only

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U4-33 | `sensor_id` = default `sensor-0` del modelo U1 en toda observación de U4; **sin** clave `SENTINEL_DISCOVERY_SENSOR_ID` (configurable llega en U9) | Q13=A, FR-DISC-04, ST-M1-03 | `test_worker.py -k sensor_id_default` |
| BR-U4-34 | **Sin código SNMP** en U4: diseño documentado como módulo opcional futuro (v2c/v3, OIDs por Helm) | ST-M1-04 documented-only, Q14=A | revisión de alcance (no existe `snmp` en `src/`) |
| BR-U4-35 | **Sin código** para `PortServiceChanged`: pertenece a la reconciliación futura de U2 (`EventType.PORT_SERVICE_CHANGED` ya existe en U1) | ST-M2-05 documented-only, Q14=A | revisión de alcance |
| BR-U4-36 | Runner por defecto en `create_app` por import perezoso de `discovery.runner` (con override `runner=` en tests); si el paquete falta ⇒ 503 como hoy | Q15=A, GT-02 | `test_api_discovery.py` existente (sin regresión) + `test_gt02_new_host.py` con runner fixture |
