# Integration Test Instructions

## Purpose
Test interactions between units/services (API real + SQLite temporal +
`TestClient`) to ensure they work together correctly — sin mocks de red:
los límites son `Database`, `IngestionService`, wiring de `create_app` y el
GUI montado sobre la misma app.

## Test Scenarios

Todos viven en `tests/integration/` (13 archivos + `gui/`); corren dentro del
suite completo o aisladamente con `pytest tests/integration -q`.

### Scenario 1: Ingesta idempotente (U2 + U5 + U6)
- **Files**: `test_ingest_idempotency.py`
- **Description**: reenvío byte-a-byte ⇒ `accepted=0`, `deduplicated=N`,
  ids de eventos estables (uuid5); lote mixto traffic+arp
- **Expected**: 202 idempotente; contadores sin cambios
- **Hook U6**: cada aceptada dispara el `ConditionService` (sin efectos
  adversos: deduplicadas no llegan al hook)

### Scenario 2: Supresión y ciclo de vida R-01 (U6 → U2)
- **File**: `test_baseline_suppression.py` (4 tests)
- **Steps**:
  1. 5 obs traffic dentro de la ventana (`condition_clock` falso) ⇒
     `baselines` con `established=1`, **cero filas `alerts`**
  2. reloj > `t_first+25s` + bps alto ⇒ fila `alerts` firing `rule=R-01`
     con evidence exacto (9 claves)
  3. firing → resolved (misma fila) → re-fire (**fila nueva** con
     `alert_id` distinto) — BR-U6-17
- **Expected**: supresión prioritaria sin falsos positivos; identidad uuid5
- **Cleanup**: BD temporal por test (`tmp_path`)

### Scenario 3: Discovery (U4)
- **Files**: `test_discovery_failure.py`, `test_scope_validation.py`,
  `test_gt02_new_host.py`, `test_gt03_host_absent.py`
- **Expected**: scope inválido ⇒ 403/errores tipados; alta/baja de activos
  según GT-02/GT-03; timeouts degradados sin romper el Core

### Scenario 4: Traffic export (U5 → U2)
- **File**: `test_traffic_export.py`
- **Expected**: ventana emitida ⇒ observaciones persistidas + heartbeat

### Scenario 5: Export y consulta (U2/U3)
- **Files**: `test_export_on_demand.py`, `test_query_filters.py`,
  `test_structured_logs.py`, `test_arp_mapping_change.py`,
  `test_persistence_restart.py`
- **Expected**: export MD/JSON on-demand; filtros de query; eventos JSON con
  `component`/`event`; checkpoint y reanudación tras restart; mapeo IP↔MAC

### Scenario 6: E2E de operador (U3 GUI)
- **File**: `gui/test_gui_flow.py`
- **Expected**: flujo completo UI montada en la app (reporte, export,
  ingest simulado) — pasa en el suite normal

## Contract Tests (sección — microservicios N/A en monolito)
- **Status**: cubiertos **dentro** de los tests de API unitarios/integración
  (`tests/unit/core/test_api_*.py`): contrato OpenAPI de FastAPI,
  códigos 202/401/403/404/422/503 y shape de respuestas (`IngestResult`,
  health, query) validados con `TestClient`
- **Comando**: `pytest tests/unit/core/test_api_ingest.py tests/unit/core/test_api_health.py -q`

## Security Tests (sección)
- **Status**: Pass a nivel unit (sin scanner de deps nuevas — restricción
  de proyecto)
- **Cobertura**:
  - Auth: bearer inválido ⇒ 401/403 (`test_api_*`)
  - Input: Pydantic U1 rechaza payloads inválidos antes de la transacción
  - Config estricta U6: env desconocida/rango inválido ⇒ `ConfigError`
    (`tests/unit/baseline/test_config.py`)
  - Superficie: sin endpoints/deps nuevas en `baseline/`
    (`test_boundaries.py`); labels prohibidos BR-21 (`test_indicators.py`)
- **Comando**: `pytest tests/unit/core/test_api_ingest.py tests/unit/baseline -q`

## Run Integration Tests

### 1. Execute Integration Test Suite
```bash
pytest tests/integration -q            # 36 tests
# con gates de cobertura (como CI):
pytest tests/unit tests/property tests/integration -q \
  --cov=sentinel --cov-fail-under=70
```

### 2. Verify Service Interactions
- **Expected Results**: 36 passed, 0 failed; sin puertos abiertos
  (`metrics_port=None` en tests); logs estructurados solo en stdout
- **Logs Location**: salida de pytest (`caplog` assertions incluidas)

### 3. Cleanup
```bash
# las BD son temporales por test (tmp_path); no hay servicios que parar
rm -rf .pytest_cache .coverage   # opcional
```
