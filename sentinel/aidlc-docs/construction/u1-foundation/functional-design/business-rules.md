# Business Rules & Validation — U1 (Foundation)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U1 — `src/sentinel/foundation/`
**Traza**: EN-01, EN-05, EN-02 (parcial); NFR-TECH-02/03, NFR-SEC-02, NFR-OPS-02 (alcance base); `requirements.md` §5 (PBT blocking); `implementation-scope.md` §2.

---

## 1. Reglas de construcción y toolchain

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-01 | Python fijado a **3.11** (`requires-python = ">=3.11,<3.12"`); CI y Dockerfile usan 3.11 | Q9=A, NFR-TECH-02 | CI corre en 3.11; `pyproject.toml` lo declara |
| BR-02 | `ruff check` y `ruff format --check` en verde antes de merge; una sola toolchain (sin black/flake8) | Q6=A, EN-01 | job `lint` de CI |
| BR-03 | Pipeline CI base = exactamente etapas **lint → test → build**; scan/helm-test/deploy quedan documentados fuera del pipeline base | Q5=A, `implementation-scope.md` §2 | `.github/workflows/ci.yml` |
| BR-04 | Un test roto bloquea merge: `pytest --maxfail=1` ⇒ exit ≠ 0 ⇒ status check `failure` | EN-01 AC | CI con test inducido fallido |
| BR-05 | Configuración única del proyecto en `pyproject.toml` (metadata, ruff, pytest); el workflow solo invoca comandos | Q5=A | revisión del workflow |

## 2. Reglas de configuración

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-06 | `foundation.config` solo define `log_level`, `component`, `debug`; **prohibido** definir en foundation claves `scope.*`, `discovery.*`, `traffic.*`, `gui.*` | Q2=A | test: `Settings.model_fields` == {log_level, component, debug} |
| BR-07 | Config inválida ⇒ `ConfigError` y proceso termina con código 1 **antes** de arrancar el servicio (fail-fast) | business-logic §2.1 | test de startup con env inválida |
| BR-08 | Config llega por variables de entorno (`SENTINEL_*`); Helm values las inyecta como `env` en los workloads | NFR-OPS-01 | values.yaml + manifiestos (U9) |

## 3. Reglas de logging

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-09 | Todo log es **una línea JSON a stdout** con campos obligatorios `ts`, `level`, `component`, `event`, `msg` | Q4=A, FR-EXP-01 | test: parsear stdout, verificar campos |
| BR-10 | `ts` en ISO 8601 **UTC** con offset (`2026-11-11T12:00:00Z`) | convención | test de formato |
| BR-11 | `event` usa el vocabulario canónico de `foundation.events` (sin eventos ad-hoc en cada unidad) | business-logic §2.6 | test: evento desconocido ⇒ warning en review |
| BR-12 | Un logger por `component`; sin handlers duplicados (patrón idempotente de `get_logger`) | Q4=A | test: doble `get_logger` ⇒ 1 handler |

## 4. Reglas de dominio y validación

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-13 | Modelos de dominio = **Pydantic** compartidos con la API; `frozen=True` (inmutables) y `extra="forbid"` | Q1=A | `tests/unit/test_models.py`: mutación y campo extra rechazados |
| BR-14 | MAC normalizada a minúsculas `aa:bb:cc:dd:ee:ff`; IP válida v4/v6; timestamps **tz-aware UTC** (naive rechazado) | DECISIONES, FR-CORE-05 | tests de tipos de campo inválidos |
| BR-15 | Toda observación lleva `sensor_id` reservado (single-sensor MVP; campo presente aunque su valor sea fijo) | FR-DISC-04 | test: campo existe en las 3 variantes de Observation |
| BR-16 | Identidad de activo móvil: no basarse solo en MAC; la identidad de observación compuesta `[INTERNO]` (IP/MAC/ventana) es responsabilidad de U2/U4 — foundation solo expone los campos crudos | DECISIONES §3 | revisión de modelos |
| BR-17 | Cada evento persistible tiene campo `event_id: UUID` (se asigna al persistir, U2); foundation define el tipo, no lo genera | FR-CORE-04 | test de tipo en `InventoryEvent` |
| BR-18 | `Asset.os` usa procedencia explícita `observed | inferred | declared | unknown`; **nunca** presentar `unknown` como confirmado | FR-GUI-08 | test de enum + test de render (U3) |
| BR-19 | Prohibido en foundation: imports de `fastapi`, `sqlite3`, `scapy`, `nmap`, `socket`, `kubernetes` (módulo puro) | criterio de frontera U1 | test de imports / revisión |

## 5. Reglas de métricas (contrato)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-20 | Toda métrica lleva prefijo `sentinel_` y nombre `[a-z0-9_]+` | Q3=A | `test_metrics_contract.py` |
| BR-21 | Labels prohibidos por cardinalidad: `src_ip`, `dst_ip`, `mac`, `asset_id` | PRD §3.2, DECISIONES §4 | `assert_labels` + test |
| BR-22 | Labels permitidos por defecto: `component`, `protocol`, `interface`, `rule`, `state` (extensible con justificación) | FR-OBS-02 | test del catálogo |

## 6. Reglas de errores

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-23 | Fallos de negocio se lanzan como subtipo de `SentinelError` con `code` estable; excepciones genéricas solo para bugs | Q7=A | test: `ScopeError("...").code == "scope_violation"` |
| BR-24 | La traducción a códigos HTTP la hace U2; foundation no conoce FastAPI ni devuelve respuestas | frontera U1 | test de imports (BR-19) |

## 7. Reglas de imagen y contenedores (EN-05)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-25 | Base **Alpine**; usuario **no root** en todos los workloads (excepción de capabilities del Sensor se justifica en U10, no aquí) | EN-05, NFR-SEC-02 | `docker run … grep Alpine`; `runAsNonRoot: true` (U9/U10) |
| BR-26 | Imagen **única**; comandos separados por entrypoint `python -m sentinel.{core,discovery,traffic}` | ST-M8-04, Q4 units | `docker run sentinel:test python -m sentinel.core --help` |
| BR-27 | `python -m sentinel.foundation` termina con mensaje "library, not an entrypoint" y exit ≠ 0 | business-logic §2.8 | test manual/CI |

## 8. Reglas de property-based testing (EN-02 — Q8=A)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-28 | `hypothesis` es dependencia de desarrollo; PBT **solo** en las áreas designadas construidas: Nmap XML (U4), normalización de flujos (U2), baseline (U6) | NFR-TECH-03, Q8=A | `pytest tests/property` en CI job `test` |
| BR-29 | Las propiedades mínimas: rechazo de entradas malformadas, idempotencia/normalización estable, invariantes numéricos (μ en rango, varianza ≥ 0, supresión primeras 5 muestras) | NFR-TECH-03 | cada archivo `tests/property/test_*.py` |
| BR-30 | EN-02 queda `implemented` **parcial** en `implementation-scope.md` (áreas construidas); las áreas no construidas (si las hubiera) no generan PBT | Q8=A | alcance re-aprobado (audit 2026-11-11) |

## 9. Anti-reglas (lo que foundation NO debe contener)

- ❌ Código de red (sockets, scapy, subprocess nmap).
- ❌ Acceso a SQLite o cualquier persistencia.
- ❌ Llamadas HTTP (requests/httpx) o al API server de Kubernetes.
- ❌ Lógica de negocio de discovery/trafico/baseline (solo contratos y tipos).
- ❌ Secretos, tokens o valores de infraestructura en el código.
- ❌ Excepciones lanzadas sin envolver en la jerarquía `SentinelError` para fallos de dominio.

---

## 10. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
