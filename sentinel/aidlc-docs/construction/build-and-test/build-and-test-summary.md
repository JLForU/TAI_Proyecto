# Build and Test Summary

## Build Status
- **Build Tool**: Python 3.11 (sin etapa de compilación) + Docker
- **Build Status**: **Success** — `ruff check` ✅ · `ruff format --check` ✅
  (185 files) · `mypy src/sentinel` ✅ (87 files, 0 issues) ·
  `docker build -t sentinel:test .` ✅ (tag `sentinel:test`,
  `cb523e67c21c`)
- **Build Artifacts**: imagen OCI `sentinel:test`; `.coverage`
- **Build Time**: suite completo ≈ 60 s local; imagen OCI ≈ 2 min (warm)

## Test Execution Summary

### Unit Tests
- **Total Tests**: 477 unit · **24** property · **36** integration
  → **537 en total**
- **Passed**: **537**
- **Failed**: **0**
- **Coverage**: total **94.68%** (gate 70%)
  - `gui` 95% · `discovery` 92% · `traffic` 95% · `baseline` 96%
    (gates 70% cada uno)
- **Status**: **Pass**

### Integration Tests
- **Test Scenarios**: 13 archivos + `gui/` (ingesta idempotente,
  supresión+ciclo R-01, discovery, traffic export, export/query/logs,
  persistence restart, mapeo ARP, **E2E GUI**)
- **Passed**: 36
- **Failed**: 0
- **Status**: **Pass**

### Performance Tests
- **Response Time**: ingest+hook `p50=19.0 ms` / `p95=20.9 ms` (n=100)
  — Target NFR-PERF-03: p95 **< 500 ms** ⇒ **dentro de envolvente**
- **Throughput**: sin requisito numérico aprobado (informativo)
- **Error Rate**: 0% (202/200 en todos los requests medidos)
- **Status**: **Pass** (informativo; sin gate de duración en CI por
  NFR-U6-PERF-01 Q1=A)

### Additional Tests
- **Contract Tests**: **Pass** (contrato OpenAPI validado in-process por
  `test_api_*`; monolito ⇒ sin archivo de contract separado)
- **Security Tests**: **Pass** (auth bearer, validación Pydantic, config
  fail-fast U6, frontera AST sin `core`/`sqlite3`, `scapy`=0, labels BR-21;
  sin scanner de dependencias nuevas — restricción de proyecto)
- **E2E Tests**: **Pass** (`tests/integration/gui/test_gui_flow.py`)
- **Property-Based Tests**: **Pass** (24 propiedades; 8 designadas
  NFR-TECH-03 en `tests/property/test_baseline_statistics.py`)

## Archivos generados en esta etapa
- `build-instructions.md`
- `unit-test-instructions.md`
- `integration-test-instructions.md`
- `performance-test-instructions.md`
- `build-and-test-summary.md`
- Nuevo test informativo: `tests/unit/core/test_ingest_latency_baseline_hook.py`
  (NFR-U6-PERF-01)

## Notas conocidas
- **Primer arranque con BD nueva**: log `baseline_hydration_failed` es
  esperado (las tablas se crean en el lifespan **después** de construir la
  app; el servicio arranca vacío = degradación FD §3.6). En reinicios con
  datos, la hidratación carga estados sin warning.
- `StarletteDeprecationWarning` de httpx en `TestClient` — preexistente
  desde U2, inofensivo.

## Overall Status
- **Build**: **Success**
- **All Tests**: **Pass** (537/537, gates de cobertura verdes)
- **Ready for Operations**: **Yes**

## Next Steps
Proceder a la fase **OPERATIONS** (deployment planning: handoff Helm U9 con
`values.yaml` → env `SENTINEL_BASELINE_*`, ID-U6-07/08) una vez aprobada
esta etapa.
