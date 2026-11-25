# Performance Test Instructions

## Purpose
Validate system performance under load to ensure it meets requirements.

## Performance Requirements
- **Response Time (envolvente NFR-PERF-03)**: `POST /api/v1/ingest` p95
  **< 500 ms** por request
- **Hook U6 (NFR-U6-PERF-01)**: operación síncrona O(1) post-commit —
  ≤3 `update_baseline` + 1 `evaluate` + ≤2 upserts por observación traffic
  aceptada; test **informativo** (imprime p50/p95, **sin gate de duración**
  en CI)
- **Throughput / Error Rate**: sin requisito numérico aprobado en
  `aidlc-docs/` (NFR-U2: p95 de rutas de query informativo)

## Setup Performance Test Environment

### 1. Prepare Test Environment
```bash
# mismo venv del proyecto; sin servicios externos:
# los tests de latencia usan TestClient + SQLite temporal (en proceso)
. .venv/bin/activate
```

### 2. Configure Test Parameters
- **Requests medidos**: `N_REQUESTS=100` (ingesta+hook), 10 rondas × 500
  eventos (query baseline, U2)
- **Sin ramp-up / usuarios virtuales**: no hay herramienta de load en
  `requirements.txt` (restricción: sin deps nuevas); la validación de
  envolventes es por p95 de requests secuenciales reproducibles

## Run Performance Tests

### 1. Execute Latency Tests (informativos)
```bash
# U6: ingesta CON hook baseline (imprime p50/p95 — validar NFR-PERF-03 aquí)
pytest tests/unit/core/test_ingest_latency_baseline_hook.py -s

# U2: latencia de rutas de query (informativo, imprime p50/p95)
pytest tests/unit/core/test_latency_baseline.py -s
```

### 2. Expected Results (medido en esta sesión, máquina local)
- **Ingest + hook**: `p50 ≈ 19 ms`, `p95 ≈ 21 ms`, max ≈ 24 ms (n=100)
  ⇒ **dentro** de la envolvente p95 < 500 ms (holgura ~24×)
- **Query routes**: p50/p95 impresos por el test (sin assert de umbral)
- **Error Rate**: 0% — ambos tests asertan 202/200 en cada request

### 3. Analyze Performance Results (procedimiento de lab)
1. Ejecutar ambos con `-s` y anotar la línea `[NFR-U6-PERF-01] …`
2. Si `p95 ≥ 500 ms` en lab: perfilar con `pytest --durations=20` y
   `coverage report --include='*/baseline/*' --show-missing`; revisar
   upserts por observación (patrón de escritura) y tamaño de lote
3. **Stress**: sin herramienta dedicada — escalar `N_REQUESTS` del test
   U6 (p. ej. 1000) manteniendo asserts 202; observar p95
4. Resultados: stdout de pytest (guardar el log en la evidencia de lab)

## Performance Optimization
If performance doesn't meet requirements:
1. Identificar cuellos de botella (`--durations`, profiling cProfile)
2. Optimizar sin romper contratos aprobados (FD/NFR) — p. ej. agregación
   de upserts **solo** con aprobación de diseño
3. Re-ejecutar ambos tests con `-s` y validar p95 < 500 ms

## Nota
No hay gate de duración en CI (decisión NFR-U6-PERF-01 Q1=A): la latencia se
mantiene informativa para no acoplar el suite a hardware de CI.
