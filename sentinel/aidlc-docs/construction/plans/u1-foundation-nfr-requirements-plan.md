# NFR Requirements Plan — U1 (Project foundation & CI skeleton)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 1: Planning)
**Fecha**: 2026-11-11
**Estado**: ARTIFACTS_GENERATED — respuestas completas (Q5=B con nota); pendiente de aprobación
**Unidad**: U1 — `src/sentinel/foundation/`
**Entradas**: `construction/u1-foundation/functional-design/*` (aprobado), `requirements.md` §3 NFR + §4 constraints + §5 extensiones, `implementation-scope.md`, `DECISIONES_PENDIENTES.md`

---

## 1. Contexto del assessment (Step 1 — analizado)

U1 es una **librería pura** (sin I/O, sin red, sin clúster): sus NFR se concentran en calidad de código, cadena de suministro, rendimiento de validación/logging y mantenibilidad. Los NFR de capacidad/escalado del sistema viven en U2 (API) y U9 (runtime).

**Categorías evaluadas**:

| Categoría | Aplica a U1 | Tratamiento |
|---|---|---|
| Scalability | Parcialmente | **Sin pregunta**: foundation es stateless; capacidad/escalado = U2/U9 (NFR-PERF-01..03 no vinculantes) |
| Performance | Sí | Q6 (overhead de validación/logging) |
| Availability | Parcialmente | **Sin pregunta**: fail-fast de config ya decidido en Functional Design (BR-07); librería sin uptime propio |
| Security | Sí | Q4 (pinning de dependencias), Q5 (SAST/secrets en CI) |
| Tech Stack | Sí | Q1 (gestor de paquetes), Q2 (type checking) |
| Reliability | Sí | Q7 (efectos secundarios al importar) |
| Maintainability | Sí | Q3 (gate de cobertura), Q8 (documentación de contratos) |
| Usability | No | **Sin pregunta**: sin UI en U1 (la usabilidad de la GUI se evalúa en U3) |

---

## 2. Checklist del plan

- [x] Analizar Functional Design y NFR globales
- [x] Generar preguntas NFR (Q1–Q8)
- [x] Recoger respuestas a los `[Answer]:`
- [x] Analizar respuestas y resolver ambigüedades (seguimientos si aplica) — Q5=B (nota: seguridad extra documentada para futuras mejoras); resto A; sin ambigüedades
- [x] Generar `nfr-requirements/nfr-requirements.md`
- [x] Generar `nfr-requirements/tech-stack-decisions.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas.

### Question 1 — Gestión de dependencias (Tech Stack)

A) `pyproject.toml` + `requirements.txt` con **todas las versiones fijadas** (directas y transitivas); CI hace `pip install -r requirements.txt` *(recomendado)*

B) `uv` con `uv.lock` (resolución y caché rápidas; dependencia de una herramienta externa)

C) `poetry` con `poetry.lock` (estándar de ecosistema, más pesado)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Type checking estático (Tech Stack / Maintainability)

A) `ruff` (lint+formato) + `mypy` en modo gradual (sin `--strict`) como job de CI *(recomendado)*

B) Solo `ruff`; mypy documentado como deuda futura (sin gate)

C) `ruff` + `mypy --strict` en CI (máximo rigor)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Gate de cobertura de tests (Maintainability)

A) Cobertura mínima del **70%** en `src/sentinel/foundation/` (job `test` falla por debajo) *(recomendado)*

B) Sin gate numérico: solo `pytest` en verde (EN-01 no pide cobertura)

C) Gate global del 80% en todo `src/`

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Cadena de suministro de dependencias (Security — extensión SECURITY blocking)

A) Versiones exactas fijadas en `requirements.txt` + **Dependabot** activado para alertas de vulnerabilidades *(recomendado)*

B) Fijar solo dependencias directas; transitivas flotan

C) Sin fijado explícito (resolución en cada CI)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Análisis de seguridad extra en CI (Security — NFR-SEC-01/03)

A) Activar las reglas **S de ruff (bandit)** dentro del job `lint` + **secret scanning nativo de GitHub**; escáner de imagen (EN-04) queda documentado (scope §2) *(recomendado)*

B) Solo ruff estándar; análisis de seguridad completo como deuda documentada

C) Añadir job propio `security` (CodeQL + trivy) al pipeline base — excede lint/test/build del scope

D) Other (describe después de `[Answer]:`)

[Answer]: B. Sería bueno solo documentarlo para futuras mejores e implementaciones más completas.

### Question 6 — Overhead de validación y logging (Performance)

A) Aceptar el costo de Pydantic + JSON logging: volumen de lab (10–50 activos, ventanas de 5 s) muy por debajo de los objetivos; sin optimización prematura *(recomendado)*

B) Exigir benchmark en CI (`tests/perf/`) para logging y validación de lotes

C) Optimizar desde ya (modelos con `slots`, serializador de logs a mano)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Efectos secundarios al importar (Reliability)

A) `import sentinel.foundation` **sin efectos secundarios**: no configura logging, no lee env, no toca stdout — todo explícito vía `load_settings()`/`get_logger()` *(recomendado)*

B) Auto-configurar logger y settings al importar el paquete (comodidad)

C) Mixed: logging auto-configurado, settings explícitos

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Documentación de contratos (Maintainability)

A) Docstrings en toda la API pública + `docs/` con páginas de contratos (modelos, métricas, errores) generadas/verificadas en U11 *(recomendado)*

B) Solo docstrings; la documentación de contratos la escribe U11 desde cero

C) Solo Markdown en `docs/`, sin docstrings

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Artefactos obligatorios (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `construction/u1-foundation/nfr-requirements/nfr-requirements.md` | NFRs específicos de U1 con métricas/verificabilidad, trazabilidad a NFR globales |
| `construction/u1-foundation/nfr-requirements/tech-stack-decisions.md` | Decisiones de stack con alternativas y justificación |

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los artefactos de NFR Requirements y presentaré el mensaje de completitud.

**No se genera ningún artefacto de NFR Requirements hasta completar este gate.**
