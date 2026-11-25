# Code Generation Plan — U1 (Project foundation & CI skeleton)

**Fase**: CONSTRUCTION — Code Generation (Part 1: Planning)
**Fecha**: 2026-11-11
**Estado**: AWAITING_APPROVAL — plan listo; esperando aprobación explícita para generar código
**Workspace root**: `/home/jhoseph/Documents/TAI/TAI_Proyecto/sentinel` (de `aidlc-state.md`)
**Patrón**: Greenfield multi-unit (monolith) → `src/{unit-name}/` = **`src/sentinel/foundation/`**, `tests/{unit-name}/` = **`tests/unit/foundation/`**
**Este plan es la única fuente de verdad de Code Generation para U1.**

---

## 1. Contexto de la unidad

- **Historias**: EN-01 (implemented) — pipeline lint/test/build; EN-05 (implemented) — Alpine non-root; EN-02 (implemented parcial) — infraestructura PBT (`foundation/testing/` + `tests/property/`; las propiedades designadas viven en U2/U4/U6).
- **Diseño aprobado**: Functional Design (`business-logic-model.md`, `business-rules.md`, `domain-entities.md`), NFR Requirements (NFR-U1-*, TS-01..11), NFR Design (P1–P8, componentes lógicos), Infrastructure Design (ID-01..07, `ci.yml` jobs lint/test/build).
- **Dependencias de otras unidades**: ninguna (U1 es raíz del grafo).
- **Interfaces/contratos que expone**: `sentinel.foundation` (models, errors, events, get_logger, load_settings, with_retries, metrics_contract, testing.generators) — consumidos por U2–U11 (ver `logical-components.md` §2).
- **Entidades de base de datos**: ninguna (U2 diseña el esquema SQLite).
- **Límites de servicio**: librería pura — sin FastAPI/SQLite/scapy/nmap/socket (BR-19); sin entrypoint propio (BR-27).
- **Toolchain**: Python 3.11, ruff, mypy gradual, pytest+pytest-cov (≥70% en foundation), hypothesis, versiones fijadas en `requirements.txt` (Q1/Q2/Q3/Q4 de NFR Req; FQ1/Q2/Q3/Q4 de Infra).

---

## 2. Pasos de generación (numerados, checkbox)

- [x] **Step 1 — Project structure setup (greenfield)**
  Crear `pyproject.toml` (metadata, `requires-python = ">=3.11,<3.12"`, config ruff/mypy/pytest/pytest-cov), `requirements.txt` (todas las versiones **exactas**: pydantic, pytest, pytest-cov, hypothesis, mypy, ruff), `src/sentinel/__init__.py`, `src/sentinel/foundation/__init__.py` (placeholder), `tests/__init__.py`, `tests/unit/foundation/__init__.py`, `tests/property/__init__.py`, `tests/fixtures/.gitkeep`, `.gitignore` (venv, `__pycache__`, `.pytest_cache`, `coverage.xml`, `*.db`).

- [x] **Step 2 — Errores y eventos (business logic)**
  Crear `src/sentinel/foundation/errors.py` (jerarquía `SentinelError` + subtipos con `code`: ConfigError, ScopeError, ValidationError, ProbeError, IngestionError, StorageError — FD §2.4, BR-23) y `src/sentinel/foundation/events.py` (enum `EventType`/`EventName` canónicos — FD §2.6, BR-11).
  *Historias: dominio compartido (soporte EN-01/EN-05/EN-02).*

- [x] **Step 3 — Config fail-fast (P1)**
  Crear `src/sentinel/foundation/config.py`: `Settings` Pydantic (`log_level`, `component`, `debug` — exactamente estos campos, BR-06) + `load_settings()` que lanza `ConfigError` (FD §2.1, NFR-U1-REL-02).
  *BR-06, BR-07, BR-08.*

- [x] **Step 4 — Logging JSON (P4)**
  Crear `src/sentinel/foundation/logging.py`: `JsonFormatter` (campos `ts` UTC ISO8601, `level`, `component`, `event`, `msg` + extras; fallback `event="unnamed"`), `get_logger(component)` idempotente con handler único stdout (FD §2.2, BR-09..BR-12, NFR-U1-REL-01/03).

- [x] **Step 5 — Modelos de dominio + límites (P2, P7)**
  Crear `src/sentinel/foundation/models.py`: value objects (`MACAddress`, `UTCDateTime`, enums `OsProvenance`/`AssetStatus`/`CycleStatus`/`ConditionState`/`Protocol`), constantes `MAX_BATCH_ITEMS=1000`, `MAX_STRING_LEN=255`, `MAX_PORTS_PER_OBSERVATION`, entidades Pydantic `frozen=True`/`extra="forbid"`: `Asset`, `DiscoveryObservation`, `TrafficObservation` (+`FlowPair`), `ArpObservation`, `Batch`, `DiscoveryCycle`, `ArpMapping`, `InventoryEvent`, `AlertCondition`, `Baseline` (FD `domain-entities.md` completo; BR-13..BR-17; BR-15 `sensor_id`; BR-18 `OsProvenance`).
  *Nota: `TrafficWindow` se resuelve como `TrafficObservation` con `window_id` opcional (decisión de implementación permitida en `domain-entities.md` §2.4).*

- [x] **Step 6 — Contrato de métricas + retry (P3, P6)**
  Crear `src/sentinel/foundation/metrics_contract.py` (`METRIC_PREFIX`, `FORBIDDEN_LABELS`, `ALLOWED_LABELS_DEFAULT`, catálogo de familias, `metric_name()`, `assert_labels()` — BR-20..BR-22) y `src/sentinel/foundation/retry.py` (`with_retries` backoff+jitter stdlib, envuelve en `IngestionError` — NFR Design Q1=P3).

- [x] **Step 7 — Testing support (EN-02 infra)**
  Crear `src/sentinel/foundation/testing/__init__.py` y `generators.py`: estrategias hypothesis (IPs v4/v6, MACs, timestamps tz-aware UTC, strings de límite, lotes ≤ MAX_BATCH_ITEMS) reutilizables por `tests/property/` de U2/U4/U6 (FD §2.7, NFR-U1-MNT-05).

- [x] **Step 8 — API pública del paquete**
  Completar `src/sentinel/foundation/__init__.py`: re-exports (`Settings`, `load_settings`, `get_logger`, `SentinelError`+subtipos, modelos principales, `EventType`, `metric_name`/`assert_labels`, `with_retries`); `__all__` ordenado; sin side effects al importar (BR-19, NFR-U1-REL-01, P7).
  *También: `python -m sentinel.foundation` debe fallar con "library, not an entrypoint" (BR-27) — log de verificación en el paso de validación.*

- [x] **Step 9 — Unit tests (`tests/unit/foundation/`)**
  Crear tests que cubran los BR verificables (objetivo ≥70% en foundation):
  - `test_models.py` — modelos válidos/inválidos, frozen, extra=forbid, límites MAX_*, MAC/UTC/sensor_id/OsProvenance (BR-13..18)
  - `test_config.py` — settings válidos, env inválida ⇒ `ConfigError` (BR-06/07)
  - `test_logging.py` — 5 campos obligatorios, handler único, event fallback (BR-09..12)
  - `test_errors.py` — jerarquía y `code` estable (BR-23)
  - `test_metrics_contract.py` — prefijo, labels prohibidos (BR-20..22)
  - `test_retry.py` — intentos, delays crecientes con `time.sleep` mockeado (P3)
  - `test_package_import.py` — import sin side effects + `python -m sentinel.foundation` exit≠0 (BR-19/27, NFR-U1-REL-01)
  - `test_generators.py` — estrategias hypothesis producen valores válidos (EN-02 infra)

- [x] **Step 10 — Property tests skeleton (EN-02 parcial)**
  Crear `tests/property/test_smoke.py` con 1–2 propiedades de foundation (p. ej. `metric_name` siempre matchea `^sentinel_[a-z0-9_]+$`; generadores producen MACs válidas) que validan la infraestructura PBT en CI; las propiedades designadas (Nmap XML, flow normalization, baseline) se añaden en U4/U2/U6 usando `foundation.testing`.

- [x] **Step 11 — CI y supply chain (EN-01, Q1/Q4 NFR, FQ1)**
  Crear `.github/workflows/ci.yml` (jobs `lint`: ruff check+format; `test`: pytest unit+property `--cov=sentinel/foundation --cov-fail-under=70` + mypy; `build`: `docker build -t sentinel:test .` con `needs: [lint, test]`; hosted `ubuntu-latest`; **sin caché, sin artifacts**) y `.github/dependabot.yml` (pip + github-actions, alertas/PRs — P6).
  *EN-01 AC: etapas `lint`, `test`, `build` visibles; test rojo ⇒ failure.*

- [x] **Step 12 — Contenedor base (EN-05, ID-02/03, BR-25/26)**
  Crear `Dockerfile`: `FROM python:3.11-alpine`, usuario no-root (`adduser`/`USER`), `WORKDIR /app`, `COPY requirements.txt` + `pip install --no-cache-dir`, `COPY src/`, `ENV PYTHONPATH=/app/src`; documentar entrypoints `python -m sentinel.{core,discovery,traffic}` en comentario de uso (BR-26; entrypoints completos funcionan desde U2/U4/U5). **Sin push** (Q2=A).
  *También `docker/` no aplica — Dockerfile en raíz del workspace.*

- [x] **Step 13 — Documentación mínima (Q8 NFR, parcial EN-03)**
  Docstrings en toda la API pública de `foundation/` (P7/MNT-04) + `README.md` de U1 con: instalación, estructura, comandos (`ruff`, `pytest`, `docker build`), y referencia a `aidlc-docs/construction/u1-foundation/`. (Páginas completas `docs/` = U11.)
  *Creación/modificación: crear `README.md` si no existe en el workspace root; modificarlo si existe.*

- [x] **Step 14 — Resumen de generación**
  Crear `aidlc-docs/construction/u1-foundation/code/code-generation-summary.md` (markdown): archivos creados/modificados, cobertura estimada, historias EN-01/EN-05/EN-02 trazadas, desviaciones (si las hubiera) — **nunca código en aidlc-docs**.

- [x] **Step 15 — Validación local**
  Ejecutar en el workspace root: `pip install -r requirements.txt` (o venv), `ruff check . && ruff format --check .`, `mypy src/sentinel/foundation`, `pytest -q tests/unit tests/property --cov=sentinel/foundation --cov-fail-under=70`, `docker build -t sentinel:test .`. Corregir hallazgos dentro de los pasos anteriores (marcar cada paso `[x]` al completarlo). *La ejecución formal completa (Build and Test) es la etapa posterior; aquí se verifica que lo generado es correcto.*

---

## 3. Historias y trazabilidad

| Historia | Steps | Nota |
|---|---|---|
| EN-01 — CI pipeline | 1, 9, 10, 11 | workflow lint/test/build; verificación AC en Step 15 |
| EN-05 — Alpine non-root | 12 | Dockerfile base + usuario no-root |
| EN-02 (parcial) — PBT infra | 7, 10 | generadores + smoke property; designados en U2/U4/U6 |

Ninguna historia de otras unidades se toca (U1 no implementa ST-*).

---

## 4. Fuera de alcance de este plan

- Código de U2–U11 (API, GUI, colectores, chart, políticas, docs GT).
- Entrypoints ejecutables de core/discovery/traffic (se añaden con sus módulos).
- Push de imagen, scan (EN-04), artifacts de CI, caché buildx (decisiones Q3=B/Q4=B/FQ1=A/Q2=A).
- Ejecución en kind (U9); tests GT (U11).

---

## 5. Gate de aprobación

Aprueba este plan completo (todos los Steps 1–15) para pasar a **Part 2 — Generation**. Responde `aprobado` o solicita cambios.

**No se genera ningún código hasta la aprobación explícita.**
