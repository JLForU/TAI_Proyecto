# Unit Test Execution

## Run Unit Tests

### 1. Execute All Unit Tests
```bash
# suite completo del proyecto (unit + property + integration, como CI)
pytest tests/unit tests/property tests/integration -q \
  --cov=sentinel --cov-fail-under=70 --cov-report=term-missing

# solo unit
pytest tests/unit -q

# con el venv de validación de esta sesión
/tmp/opencode/venv/bin/pytest tests/unit -q
```

### 2. Review Test Results
- **Expected**: **537 tests pass, 0 failures, 0 errors**
  - `tests/unit`: **477** · `tests/property`: **24** · `tests/integration`: **36**
- **Test Coverage** (gate `--cov-fail-under=70`): total **94.68%** (3611 stmts)
  - Gates por área (cada uno `coverage report --include=… --fail-under=70`):

    | Área | Cobertura | Gate |
    |---|---|---|
    | `*/gui/*` | 95% | 70% |
    | `*/discovery/*` | 92% | 70% |
    | `*/traffic/*` | 95% | 70% |
    | `*/baseline/*` | 96% | 70% |
- **Test Report Location**: salida estándar de pytest + `.coverage`
  (informes HTML opcionales: `coverage html`)

### 3. Fix Failing Tests
If tests fail:
1. Revisar la salida de pytest (tail del fallo + `FAILED tests/…`)
2. Reproducir aislado: `pytest tests/<ruta>::<test> -vv`
3. Corregir el código (no el test salvo que el test contradiga un requisito
   aprobado en `aidlc-docs/`)
4. Re-ejecutar el suite completo hasta 0 fallos + gates de cobertura

### 4. Notas por unidad (U6)
- PBT: `tests/property/test_baseline_statistics.py` (hypothesis, 8 propiedades
  designadas NFR-TECH-03) — requiere `hypothesis` (ya en requirements)
- Latencia informativa: `pytest tests/unit/core/test_ingest_latency_baseline_hook.py -s`
  imprime p50/p95 **sin assert de duración**
- Fronteras (AST): `tests/unit/baseline/test_boundaries.py` — falla si
  `baseline/` importa `sentinel.core`/`sqlite3` o si aparece `scapy` en `src/`
