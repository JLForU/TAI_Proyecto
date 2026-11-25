# Code Generation Summary — U6 Baseline & deterministic conditions

**Stage**: Construction · Code Generation (Parte 2: Generation, 24/24 steps)
**Fecha**: 2026-11-23
**Plan**: `aidlc-docs/construction/plans/u6-baseline-code-generation-plan.md`

## 1. Archivos creados

### Código (`src/`)
| Archivo | Contenido |
|---|---|
| `src/sentinel/baseline/__init__.py` | Frontera + exports (`ConditionService`, `BaselineSettings`, `SystemClock`, `mean`, `sample_variance`, `select_threshold`, `BASELINE_SAMPLES`) |
| `src/sentinel/baseline/config.py` | `BaselineSettings` estricto (frozen/forbid), `load_baseline_settings()` fail-fast `ConfigError` (BR-U6-02..04) |
| `src/sentinel/baseline/statistics.py` | Puro: `mean`, `sample_variance` (n-1), `select_threshold` (μ+k·s + fallback absoluto) |
| `src/sentinel/baseline/conditions.py` | `ConditionService`: estados, supresión prioritaria, R-01 estricto, hidratación, persistencia degradada, `on_accepted`, `metric_samples` (P1/P6/P7) |
| `src/sentinel/baseline/indicators.py` | Proyección pura a `(familia, labels, valor)` — 4 familias, `assert_labels` (BR-21) |
| `src/sentinel/core/baseline_wiring.py` | Adaptadores `BaselineStore`/`AlertStore` (duck-typing sobre `Database`) + `build_condition_service` con hidratación degradada (`baseline_hydration_failed`) |

### Tests
| Archivo | Cubre |
|---|---|
| `tests/unit/baseline/test_config.py` | Loader estricto, rangos, frozen/forbid |
| `tests/unit/baseline/test_statistics.py` | Media, varianza n-1, umbral estricto |
| `tests/unit/baseline/test_conditions.py` | 19 tests: first-5, congelado, supresión, firing/resolved/no_data, ids uuid5, degradación, hidratación, roundtrip |
| `tests/unit/baseline/test_indicators.py` | Cardinalidad, labels prohibidos, valores por estado, flag collector |
| `tests/unit/baseline/test_boundaries.py` | AST: frontera BR-U6-01 + `scapy`=0 en `src/` |
| `tests/unit/core/test_ingestion_hook.py` | Hook: solo aceptadas, excepción tragada (202), default None |
| `tests/unit/core/test_baseline_wiring.py` | Adaptadores roundtrip, hidratación OK/fallo, `create_app` wiring |
| `tests/integration/test_baseline_suppression.py` | ST-M5-03/GT-04: init-window sin alerts, after-window firing, lifecycle fire→resolve→re-fire, evidence exacto |
| `tests/property/test_baseline_statistics.py` | PBT designado (NFR-TECH-03): 8 propiedades (fuerza bruta, congelado, monotonía k, estricto, estados, suppressed⇒nunca firing) |

## 2. Archivos modificados (ediciones acotadas)

| Archivo | Edición |
|---|---|
| `src/sentinel/foundation/metrics_contract.py` | +3 familias: `sentinel_traffic_threshold_exceeded`, `sentinel_baseline_status`, `sentinel_collector_up` (las existentes intactas) |
| `src/sentinel/core/ingestion/service.py` | Parámetro `on_accepted` + invocación **post-commit** con excepción tragada (`ingestion_hook_failed`) |
| `src/sentinel/core/api/app.py` | Seams `baseline_settings=`/`condition_clock=` (ID-U6-07), `app.state.condition`, hook enlazado |
| `tests/unit/foundation/test_metrics_contract.py` | +3 tests de familias/labels baseline |
| `.github/workflows/ci.yml` | Paso `Baseline coverage gate (U6, P13)` tras traffic |
| `README.md` | Sección **Baseline & conditions (U6)** + gate en comandos de calidad |

## 3. Verificación de frontera

- `tests/unit/baseline/test_boundaries.py` (AST): `baseline/*` importa solo
  `sentinel.foundation*` + `sentinel.baseline*` + stdlib (+ `pydantic` en
  `config.py`); **jamás** `sentinel.core.*` ni `sqlite3`.
- `scapy` = 0 en todo `src/` (test `test_scapy_zero_in_src`).
- Composición core→baseline: los adaptadores que conocen `Database` viven en
  `core/baseline_wiring.py` (P11, precedente `discovery/trigger.py`).

## 4. Desviaciones (D-U6-*)

- **D-U6-01** — `collector_up` (U6→U7): `metric_samples()` deriva el flag del
  heartbeat **en memoria** del proceso (`_last_traffic_seen`, actualizado con
  cada observación de tráfico aceptada). U7 podrá además calcular
  `collector_up(...)` con el heartbeat de `HealthService`/BD (FD §3.5) — el
  contrato de las 4 familias no cambia.
- **D-U6-02** — Tests de integración usan el seam `baseline_settings=` en
  `create_app` en lugar de env `SENTINEL_BASELINE_*`: mismo efecto
  (ID-U6-07), determinista y sin contaminación de env entre tests; el loader
  env real queda cubierto por `tests/unit/baseline/test_config.py`.

## 5. Cobertura y validación (Step 23 — todo en verde)

| Gate | Resultado |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 184 files already formatted |
| `mypy src/sentinel` | Success: no issues in 87 files |
| `pytest tests/unit tests/property tests/integration --cov=sentinel --cov-fail-under=70` | **623 passed**, total **94.68%** (gate 70%) |
| `coverage report --include='*/baseline/*' --fail-under=70` | **96%** (290 stmts, 13 miss) |

## 6. Historias y trazabilidad

- **ST-M5-01..04** permanecen **documented-only** (M5 = mínimo para
  R-01/GT-04): el código generado es el soporte de la unidad — primeras 5
  muestras, media/varianza n-1, supresión prioritaria y ciclo de vida de
  alerta; la instrumentación/operación completa es M5 posterior.
- Trazabilidad plan §3: cada elemento (FR-BASE-01..04, BR-U6-01..27,
  NFR-U6-*, P1..P15, ID-U6-01..08, GT-04) mapeado a sus steps — 24/24 `[x]`.

## 7. Estado del repo

- El workspace raíz `TAI_Proyecto/` es un repo git (rama `main`, 2 commits
  adelante de `origin/main`); `sentinel/` está registrado como gitlink
  (submódulo sin `.git` propio) ⇒ su contenido no se versiona a nivel de
  archivo desde este workspace; `.github/` sin trackear.
- **Sin commits** durante esta unidad (regla: solo cuando se pida
  explícitamente).
