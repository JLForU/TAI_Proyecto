# Code Generation Summary — U4 (Network Discovery)

**Unidad**: U4 · **Fecha**: 2026-11-18 · **Plan**: `aidlc-docs/construction/plans/u4-discovery-code-generation-plan.md` (30/30 steps `[x]`)
**Traza**: ST-M1-01..04, ST-M2-01..06, FR-DISC-01..06, NFR-TECH-03, NFR-U4-* · FD Q1–Q16/FQ1 · NFR Req Q1–Q9 · NFR Design Q1–Q8 · Infra Q1–Q7 (ID-U4-01..10) · Code Gen plan = `Aprobado`.

## 1. Archivos creados

| Área | Archivos |
|---|---|
| Paquete discovery | `src/sentinel/discovery/{__init__,config,scope,domain,scanner,worker,client,runner,__main__}.py` |
| Tests unitarios | `tests/unit/discovery/{__init__,test_scope,test_scanner,test_worker,test_client,test_runner,test_cli}.py`, `tests/unit/discovery/fixtures/{nmap_sample.xml,arp_sample.txt}`, `tests/unit/test_config_validation.py`, `tests/unit/test_nmap_args.py` |
| Tests integración | `tests/integration/{test_scope_validation,test_discovery_failure,test_gt02_new_host,test_gt03_host_absent}.py` |
| PBT | `tests/property/test_nmap_xml.py` (4 propiedades hypothesis, MNT-03) |
| Docs | `aidlc-docs/construction/u4-discovery/code/code-generation-summary.md` (este archivo) |

## 2. Archivos modificados (ediciones acotadas FD §4 + handoff)

| Archivo | Cambio | Verificación |
|---|---|---|
| `src/sentinel/foundation/models.py` | `Batch.reconcile: bool = True` (retrocompatible) | tests foundation/ingest verdes; GT-03 usa la clave |
| `src/sentinel/foundation/metrics_contract.py` | `METRIC_FAMILIES` + `sentinel_discovery_cycles_failed_total` | assert de familias itera el contrato (395 verdes) |
| `src/sentinel/core/ingestion/service.py` | `if has_discovery and batch.reconcile:` antes de `reconcile_missing` | `test_gt03_host_absent -k partial_cycle` (E2E) |
| `src/sentinel/core/api/app.py` | param `scope_validator`; env `SENTINEL_DISCOVERY_*` ⇒ validador U4; `runner=None` ⇒ import perezoso `CycleRunnerImpl`; `CycleCounter` inyectado | `test_discovery_503_without_runner` (BR-U4-36) sin regresión |
| `src/sentinel/core/api/routes_discovery.py` | pre-run `validate_scope` ⇒ `ScopeError` → 400 `scope_violation` + warning log; sin validador ⇒ sin cambio | `test_scope_validation -k api_pre_run_400` |
| `src/sentinel/core/discovery/trigger.py` | `counter=`/`scope_validator=` (TYPE_CHECKING); `counter.record(status)`; log `discovery_cycle_failed` (run_id, causa) en failed/timeout | `test_discovery_failure -k metrics_increment` |
| `src/sentinel/core/metrics/collect.py` | `CycleCounter` (espejo de `ApiRequestCounter`) + samples de ambas familias | `test_metrics` + gate discovery |
| `.github/workflows/ci.yml` | paso `Discovery coverage gate (P11)` tras el de GUI | `coverage report --include='*/discovery/*' --fail-under=70` en local |
| `Dockerfile` | `nmap` en el `apk add` de U3 (misma capa; sin cambios de CMD/usuario) — ID-U4-01 | `docker build` OK · `nmap 7.99` en la imagen |
| `README.md` | sección **Discovery** (run local, tabla `SENTINEL_DISCOVERY_*`, fallback fixtures, handoff U9/U10, documented-only) + gate en comandos | revisión manual |

## 3. Desviaciones (D-*)

| ID | Desviación | Justificación |
|---|---|---|
| D-U4-01 | `parse_nmap_xml` endurecido: IP/MAC/puerto inválidos se descartan, strings recortados a 255, `protocol` fuera de `{tcp,udp}` ⇒ `other` | PBT MNT-03 exige «atributos hostiles no rompen el parser / nunca excepción cruda»; sin cambios para salida nmap válida |
| D-U4-02 | Cableado de `create_app` condicionado a la presencia de env `SENTINEL_DISCOVERY_*` (en vez de try/except a ciegas) | Equivalente: sin env ⇒ `ConfigError` ⇒ sin validador/runner ⇒ 503 (BR-U4-36); evita warnings duplicados en cada `create_app` de los tests U2 |
| D-U4-03 | `cause` del log `discovery_cycle_failed` = `code` del error (`scope_violation`/`scanner_error`/`timeout`); el `error` en BD conserva el mensaje | Patrón NFR P10 (causa enum) + BR-U4-07; `str(exc)` no era el código canónico |
| D-U4-04 | `to_observations` convierte `ip` con `IPv4Address(...)` | mypy `arg-type`; IP no-IPv4 en allowlist ⇒ ciclo `failed` con error claro (config del operador) |
| D-U4-05 | `resolve_targets` descarta CIDRs no-IPv4 | Alcance IPv4-only coherente con `validate_target` (`IPv4Address`) |
| D-U4-06 | PBT en `tests/property/test_nmap_xml.py` (ruta plan/NFR MNT-03); BR-U4-20 cita `tests/unit/test_nmap_xml.py -k property` | Tests nombrados `test_property_*` ⇒ `-k property` matchea en cualquier ruta; sin duplicar archivos |

Lint de Step 29 motivó autofix menores en archivos de los Steps 1–15 (orden de imports, `_StopLoop`→`_StopLoopError`, `SIM117`) — sin cambio de comportamiento.

## 4. Validación local (Step 29 — todo verde)

```text
ruff check .                  → All checks passed!
ruff format --check .         → 146 files already formatted
mypy src/sentinel             → Success: no issues found (73 files)
pytest tests/unit tests/property tests/integration
  --cov=sentinel --cov-fail-under=70
  → 395 passed · total coverage 93.89% (gate ≥70 ✓)
coverage report --include='*/discovery/*' --fail-under=70
  → discovery 92% (742 stmts, 62 miss; gate ≥70 ✓)
docker build -t sentinel:test . → Successfully built · nmap 7.99 en imagen (ID-U4-01)
scripts/verify_unit_dag.py / verify_traceability.py → OK (9 units, 47 stories)
```

Tests U4: **116 nuevos** (unit discovery 60 + config/nmap_args 21 + integración 15 + PBT 5 + resto combos); 395 totales = 279 de U1–U3 sin regresiones.

## 5. Historias

| Historia | Steps | Estado |
|---|---|---|
| ST-M1-01 Helm-configurable scope/scheduling | 2, 14, 28 | [x] (env estrictas + `--interval`; `helm template` ⇒ U9/Build & Test) |
| ST-M1-02 Authorized scope validation | 3, 5, 20, 23 | [x] (worker sin paquetes + API 400 `scope_violation` pre-run) |
| ST-M1-03 sensor_id reserved | 9, 28 | [x] documented-only (default `sensor-0`, D-U4-08) |
| ST-M1-04 SNMP optional | 28 | [x] documented-only (D-U4-08) |
| ST-M2-01 Periodic ARP/ICMP/TCP discovery | 4, 8, 9, 14 | [x] (fases + deadline + cap 1000) |
| ST-M2-02 Light service/version probing | 6, 7 | [x] (`-sT -sV --version-light` + whitelist) |
| ST-M2-03 Asset first seen | 16, 18, 24 | [x] (GT-02 E2E ⇒ `AssetFirstSeen`) |
| ST-M2-04 Asset missing after N cycles | 16, 18, 24 | [x] (GT-03: completed ⇒ missing; parcial ⇒ nunca) |
| ST-M2-05 Port/service change | 28 | [x] documented-only (D-U4-08) |
| ST-M2-06 Discovery cycle failure handling | 21, 22, 23 | [x] (failed/timeout ⇒ log + counter + exit 1 standalone) |

AC con curl/demo en clúster (`helm template`, CronJob, NetworkPolicy) se confirman en **Build & Test** (etapa única al final).

## 6. Estado del repo

- `sentinel/` sigue **sin `.git`** (anomalía conocida): nada tracked, sin commits hechos (regla: solo cuando el usuario lo pida).
- Cadena U3→U4: al aprobar esta etapa queda **U4 completo** (FD/NFR Req/NFR Design/Infra/Code Gen); siguiente unidad U5 según plan de unidades.
