# Tech Stack Decisions — U1 (Foundation)

**Fase**: CONSTRUCTION — NFR Requirements
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U1 — `src/sentinel/foundation/`
**Nota**: decisiones de la **unidad**; el stack global del producto (FastAPI, scapy, nmap, SQLite, Jinja/HTMX/Tailwind) está fijado en `requirements.md` §4 y se consume desde U2–U9.

---

## 1. Tabla de decisiones

| # | Decisión | Elegida | Alternativas descartadas | Justificación | Origen |
|---|---|---|---|---|---|
| TS-01 | Lenguaje y versión | **Python 3.11** (`requires-python = ">=3.11,<3.12"`) | 3.12 (más rápido, menos probado en el entorno); matriz dual (duplica CI) | Cumple NFR-TECH-02 (3.11+); compatibilidad con scapy/nmap/k8s client; una sola versión = CI simple | FD Q9=A |
| TS-02 | Modelos de dominio | **Pydantic v2** (`frozen=True`, `extra="forbid"`) | dataclasses + schemas (conversión en cada frontera); attrs (ecosistema disperso con FastAPI) | Una sola fuente de verdad dominio/API; validación declarativa; coherente con C2 | FD Q1=A |
| TS-03 | Gestión de dependencias | **`pyproject.toml` + `requirements.txt` con todas las versiones exactas**; CI: `pip install -r requirements.txt` | `uv`+lock (herramienta externa); `poetry` (pesado para 1 desarrollador); sin fijado (no reproducible) | Reproducibilidad total sin añadir toolchain; pip siempre disponible | Plan Q1=A |
| TS-04 | Lint + formato | **ruff** (`check` + `format --check`) | black+flake8 (2 tools); pylint (lento, sin formatter) | Una toolchain, rápido, config en `pyproject.toml`; sustituye a isort/black/flake8 | FD Q6=A |
| TS-05 | Type checking | **mypy gradual** (sin `--strict`) en CI | Solo ruff (sin chequeo de tipos); `--strict` (bloquea adopción gradual) | Tipos ya vienen por Pydantic; gradual da valor sin frenar; strict posible como deuda | Plan Q2=A |
| TS-06 | Tests | **pytest + pytest-cov (≥70% en foundation) + hypothesis (áreas designadas)** | unittest (verbose); sin gate de cobertura (sin señal de calidad) | EN-01 exige pytest; cobertura = verificable; PBT exigido por NFR-TECH-03 | FD Q8=A, Plan Q3=A |
| TS-07 | CI | **GitHub Actions**: jobs `lint` (ruff), `typecheck` (mypy), `test` (pytest+cov+property), `build` (docker) | GitLab CI (repo en GitHub); script local único (sin status checks); pipeline con scan/helm-test/deploy (excede scope §2) | Repo ya en GitHub; status checks bloquean merge; etapas exactas = lint/test/build | FD Q5=A |
| TS-08 | Logging | **stdlib `logging` + JsonFormatter a stdout** | structlog (dependencia extra sin necesidad); print JSON (sin niveles/handlers) | Cero dependencias; cumple FR-EXP-01; control total del formato | FD Q4=A |
| TS-09 | Cadena de suministro | **Pinning exacto + Dependabot** | Solo directas (transitivas rotas); resolución en cada CI (drift) | Reproducibilidad + alertas de vulnerabilidades sin gate nuevo | Plan Q4=A |
| TS-10 | Seguridad extra en CI | **Documentada como deuda** (sin job SAST/secret-scan/imagen en el pipeline base) | Reglas S ruff + secret scanning en lint (más gate); CodeQL/trivy job (excede lint/test/build) | **Q5=B**: "solo documentarlo para futuras mejores e implementaciones más completas"; el baseline blocking se cubre con controles de diseño (U9/U10) | Plan Q5=B, scope §2/§3 |
| TS-11 | Formato de logs/métricas | JSON Lines (logs) y texto Prometheus (métricas) definidos por contrato en foundation | Formatos binarios/custom | Consumidores estándar (K8s logging, Prometheus) | FD §2.2/§2.3 |

---

## 2. Dependencias previstas de foundation (todas fijadas en `requirements.txt`)

| Paquete | Rol | Notas |
|---|---|---|
| `pydantic` (v2) | Modelos/validación | Única dependencia runtime de foundation |
| `pytest` | Tests | dev |
| `pytest-cov` | Cobertura ≥70% | dev |
| `hypothesis` | PBT designado | dev (NFR-TECH-03) |
| `mypy` | Type checking | dev |
| `ruff` | Lint/formato | dev |

> FastAPI, httpx, scapy, jinja2, etc. pertenecen a U2–U5; foundation no los importa (BR-19).

---

## 3. Decisiones explícitas pendientes para otras unidades (no se toman aquí)

| Tema | Unidad que decide |
|---|---|
| Web framework y OpenAPI (FastAPI) | U2 |
| Esquema SQLite, migraciones, tamaño de PVC/retención | U2 / U9 |
| Algoritmo final de umbral (`μ+k·s` vs absoluto) — `DECISIONES` §4 | U6 (NFR Design) |
| Capabilities del sensor y namespace `sentinel-capture` | U10 (Infrastructure/NFR Design) |
| Mecanismo de visibilidad de red (mirror/TAP) | U5 (documentado) / POC |

---

## 4. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
