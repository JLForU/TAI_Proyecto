# NFR Design Patterns — U1 (Foundation)

**Fase**: CONSTRUCTION — NFR Design (Parte 2: Generation)
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación formal
**Unidad**: U1 — `src/sentinel/foundation/`
**Decisiones (plan Q1–Q4)**: A en todas — primitiva `foundation.retry` compartida; límites de entrada como constantes de modelo; cliente HTTP en cada colector (no en foundation); Dependabot solo alertas/PRs.
**Entradas**: `nfr-requirements/*` (NFR-U1-PERF/REL/SEC/MNT, TS-01..TS-11), Functional Design de U1.

---

## 1. Patrones aplicados por NFR

### P1 — Fail-fast en el borde de configuración (→ NFR-U1-REL-02)

| Elemento | Diseño |
|---|---|
| Mecanismo | `load_settings()` valida `Settings` al inicio de cada entrypoint; `ConfigError` ⇒ log JSON de una línea en stdout + `sys.exit(1)` |
| Dónde | `foundation.config` + hook de arranque documentado en el FD (§4 Flujo de arranque) |
| Verificación | Test de startup con env inválida ⇒ exit 1, mensaje JSON con `event="config_error"` |
| No hace | No reintenta ni degrada: una config inválida no es un estado recuperable |

### P2 — Validación acotada en la frontera (→ Security, Q2=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Constantes en `foundation.models`: `MAX_BATCH_ITEMS = 1000`, `MAX_STRING_LEN = 255` (hostname/service), `MAX_PORTS_PER_OBSERVATION = 65535`…; validadas por Pydantic (`max_length`, `max_length` de lista) ⇒ `ValidationError` con campo y límite |
| Alcance | Todas las variantes de `Observation` y los payloads de lote (`Batch` wrapper con `items: list[Observation]` y validación de cardinalidad) |
| Por qué fijo y no por env | Coherencia con BR-06 (`foundation.config` solo claves comunes); si U2 necesita tunear el límite de lote, lo hace en su config validando contra la constante, no re-definiéndola |
| Verificación | Test: lote de `MAX_BATCH_ITEMS+1` ⇒ error; string de 256 chars ⇒ error |

### P3 — Reintento con backoff exponencial + jitter (→ Resilience, Q1=A)

| Elemento | Diseño |
|---|---|
| API | `foundation.retry.with_retries(fn, *, attempts=5, base_delay=0.5, max_delay=30.0, jitter=True, retry_on=(Exception,))` → devuelve resultado o última excepción envuelta en `IngestionError` |
| Diseño | Stdlib puro (`time.sleep`, `random.uniform`); backoff `min(base_delay * 2**n, max_delay)` ± jitter; **sin** side effects en import |
| Consumidores | U4/U5: envío de lotes al Core (`POST /api/v1/ingest`); U3 puede usarlo para trigger de discovery si lo necesita |
| No hace | No conoce HTTP (el `fn` lo aporta el colector); no persiste lotes (reintento de lote perdido es responsabilidad del colector con su buffer) |
| Verificación | Test con fn fallida ⇒ N intentos y delays crecientes (mock de `time.sleep`); test con fn que falla 2 veces ⇒ éxito al 3er intento |

### P4 — Logging estructurado garantizado (→ MNT/REL, BR-09..BR-12)

| Elemento | Diseño |
|---|---|
| Mecanismo | `JsonFormatter` con campos obligatorios y fallback (`event="unnamed"`); handler único por logger idempotente |
| Patrón asociado | `LoggerAdapter` implícito: `get_logger("discovery")` fija `component` |
| Verificación | Test de cada línea parseable como JSON con los 5 campos |

### P5 — Gate de calidad en CI (→ MNT-01..05, TS-07)

| Elemento | Diseño |
|---|---|
| Jobs | `lint` (ruff check + format) → `typecheck` (mypy gradual) → `test` (pytest unit + property + `--cov-fail-under=70`) → `build` (docker, solo si los anteriores pasan) |
| Patrón | Estado checks en PR: cualquiera rojo ⇒ merge bloqueado (EN-01 AC) |
| Cobertura | `pytest-cov` limitado a `src/sentinel/foundation/` (el gate aplica donde foundation ya existe; se amplía por unidad a medida que crece — ver nota §3) |
| Verificación | PR con test inducido rojo ⇒ status `failure` |

### P6 — Supply chain fijo (→ SEC-01/02, TS-03/TS-09, Q4=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `requirements.txt` con versiones exactas (`name==x.y.z`) instaladas en CI; `.github/dependabot.yml` con `package-ecosystem: pip` + `github-actions`, `open-pull-requests-limit` bajo, revisione manual |
| Política | Solo alertas/PRs automáticos — **sin job de escaneo de dependencias** (coherente con Q5=B); PRs de Dependabot se revisan como parte normal de review |
| Verificación | Presencia de `.github/dependabot.yml` y `==` en cada línea de `requirements.txt` |

### P7 — Contrato inmutable de dominio (→ MNT, Q1 FD)

| Elemento | Diseño |
|---|---|
| Mecanismo | Modelos Pydantic `frozen=True` + `extra="forbid"`; copias con `model_copy(update=…)` en vez de mutación |
| Beneficio NFR | Elimina efectos secundarios compartidos (estado mutable global) — fiabilidad de concurrencia futura sin locks |
| Verificación | Test de asignación a campo ⇒ `ValidationError`/`FrozenInstanceError` |

### P8 — Deuda de seguridad explícita (→ SEC-04, Q5=B)

| Elemento | Diseño |
|---|---|
| Mecanismo | Sección "Trabajo futuro de seguridad" en `docs/` (redactada en U11): SAST (ruff S/bandit, CodeQL), secret scanning, escáner de imagen (EN-04), con condiciones para activarlas |
| Por qué | Decisión Q5=B: pipeline base se mantiene en lint/test/build; el baseline blocking se cubre con controles de diseño (U9/U10) |
| Verificación | Presencia del documento y mención en la demo/evidencia (U11) |

---

## 2. Patrones explícitamente NO aplicados (y por qué)

| Patrón | Razón de omisión |
|---|---|
| Circuit breaker / bulkhead / failover | La red entre colectores y Core se diseña en U4/U5; foundation solo aporta `with_retries` (P3) |
| Cachés, colas, rate limiting | Sin estado y sin I/O en U1; volumen de lab (PERF-01) |
| Escalado horizontal / load boundaries | Librería stateless; corresponde a U9 (workloads) |
| Optimización de hot-path (slots, buffers) | NFR-U1-PERF-01: sin optimización prematura |
| Degradación controlada (feature flags) | Alcance demo; sin requisito |

---

## 3. Nota de evolución

El gate de cobertura ≥70% aplica desde U1 sobre `src/sentinel/foundation/`; al completar cada unidad siguiente, el alcance de `--cov` se amplía acumulativamente (decisión de implementación en su `code-generation-plan`), manteniendo el mismo umbral — sin cambios de NFR.

---

## 4. Approval Gate

**Estado**: GENERATED — pendiente de aprobación formal (ver mensaje de completitud).
