# NFR Requirements — U1 (Project foundation & CI skeleton)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 2: Generation)
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U1 — `src/sentinel/foundation/`
**Decisiones (plan Q1–Q8)**: A en todas salvo **Q5=B** (análisis de seguridad extra solo documentado para futuras mejoras e implementaciones más completas).
**Entradas**: Functional Design de U1 (aprobado), `requirements.md` §3/§4/§5, `implementation-scope.md`, `DECISIONES_PENDIENTES.md`.

---

## 1. Alcance

NFR **específicos de la unidad U1** (librería pura, stateless). Los NFR de capacidad, latencia y disponibilidad del sistema completo se evalúan en U2 (API) y U9 (runtime); aquí solo se registran los que imponen restricciones verificables sobre foundation, la toolchain y el pipeline.

---

## 2. Requisitos no funcionales de U1

### 2.1 Rendimiento (Performance)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U1-PERF-01 | Validación Pydantic y logging JSON se aceptan **sin optimización**: el volumen de laboratorio (10–50 activos, ventanas de 5 s, lotes pequeños) está muy por debajo de los objetivos no vinculantes NFR-PERF-01..03 | Plan Q6=A | Sin gate de perf en CI; revisión en U11 si la demo muestra latencia |
| NFR-U1-PERF-02 | `import sentinel.foundation` no realiza E/S ni trabajo pesado (solo definiciones); tiempo de importación objetivo **< 1 s** (no vinculante) | Plan Q7=A, BR (FD) | Test manual/CI opcional: `python -c "import sentinel.foundation"` |

### 2.2 Fiabilidad (Reliability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U1-REL-01 | **Cero efectos secundarios al importar**: no lee env, no configura logging, no escribe stdout — todo explícito vía `load_settings()` / `get_logger()` | Plan Q7=A | Test: `import sentinel.foundation` con env basura ⇒ sin excepción ni salida |
| NFR-U1-REL-02 | Config inválida ⇒ `ConfigError` + exit 1 **antes** de arrancar el servicio (fail-fast) | Functional Design BR-07 | Test de startup con `SENTINEL_LOG_LEVEL=invalid` |
| NFR-U1-REL-03 | Un logger tiene exactamente un handler JSON (sin duplicados ni handlers raíz heredados) | FD BR-12 | `test`: doble `get_logger` ⇒ `len(logger.handlers) == 1` |

### 2.3 Seguridad (Security)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U1-SEC-01 | **Pinning estricto**: todas las dependencias (directas y transitivas) fijadas por versión exacta en `requirements.txt`; CI instala solo desde ese archivo | Plan Q4=A | `pip install -r requirements.txt` sin resolución flotante; diff de pin en review |
| NFR-U1-SEC-02 | **Dependabot** activado para alertas de vulnerabilidades en el repositorio | Plan Q4=A | Pestaña Dependabot / archivo `.github/dependabot.yml` |
| NFR-U1-SEC-03 | **Sin secretos ni claves** en foundation (ni en ningún archivo del repo); `DECISIONES_PENDIENTES.md` §6 (token en Secret de K8s) se cumple en U9/U10 | Reglas de seguridad generales | Revisión + git history scan manual |
| NFR-U1-SEC-04 | Análisis de seguridad **extra** en CI (reglas S de ruff/bandit, secret scanning, CodeQL, escáner de imagen EN-04) queda **documentado como deuda/futura mejora**, fuera del pipeline base lint/test/build | Plan **Q5=B** (nota del usuario: "solo documentarlo para futuras mejores e implementaciones más completas"), `implementation-scope.md` §2/§3 | `docs/troubleshooting.md` + "trabajo futuro" en U11; el baseline SECURITY *blocking* se cumple con los controles de diseño (RBAC/PSA/no-privilege en U10, NFR-SEC-02 en imagen) |
| NFR-U1-SEC-05 | Base Alpine + usuario no-root en la imagen construida por U1 | EN-05, NFR-SEC-02, BR-25 | `docker run … grep Alpine`; `runAsNonRoot` (verificado en U9/U10) |

### 2.4 Mantenibilidad (Maintainability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U1-MNT-01 | `ruff check` + `ruff format --check` en verde en CI (gate de merge) | Plan Q2 (FD Q6=A), BR-02 | job `lint` |
| NFR-U1-MNT-02 | **mypy gradual** (sin `--strict`) ejecutado en CI sobre `src/sentinel/foundation/` | Plan Q2=A | job `typecheck` o etapa dentro de `test`; errores ⇒ fallo |
| NFR-U1-MNT-03 | Cobertura de tests **≥ 70%** en `src/sentinel/foundation/`; por debajo el job `test` falla | Plan Q3=A | `pytest --cov=sentinel/foundation --cov-fail-under=70` |
| NFR-U1-MNT-04 | Docstrings en toda la API pública de foundation; contratos (modelos, métricas, errores) documentados en `docs/` y verificados en U11 | Plan Q8=A, EN-03 | revisión + checklist EN-03 en U11 |
| NFR-U1-MNT-05 | PBT (hypothesis) activo en CI para las áreas designadas construidas (Nmap XML, normalización, baseline) | FD Q8=A, NFR-TECH-03 | `pytest tests/property` dentro del job `test` |

### 2.5 Disponibilidad y escalabilidad

**No aplican a U1**: la librería no tiene uptime propio (fail-fast cubierto en REL-02) ni estado que escalar; la disponibilidad del Core y el escalado de workloads se evalúan en U2/U9 (NFR-AVAIL-01/02, NFR-PERF-*).

---

## 3. Trazabilidad con NFR globales

| NFR global | Contribución de U1 |
|---|---|
| NFR-TECH-02 (Python 3.11+) | Fijado en toolchain (Q9 FD) y verificado en CI/Docker |
| NFR-TECH-03 (PBT designado) | MNT-05 + `foundation.testing` |
| NFR-SEC-01 (SECURITY blocking) | SEC-01..03, SEC-05; baseline de admisión/controles en U10 |
| NFR-SEC-02 (Alpine, non-root) | SEC-05 (imagen construida desde U1) |
| NFR-SEC-03 (scan en CI) | **Alcance reducido**: EN-04 documented-only; SEC-04 lo deja explícito (Q5=B) |
| NFR-OPS-02 (pipeline CI) | Base lint/test/build implementada; helm-test/deploy documentados (scope §2) |
| NFR-OPS-03 (docs Markdown) | MNT-04 |

---

## 4. Criterios de aceptación del assessment

- [x] Categorías del plan evaluadas con justificación de omisiones (scalability/availability/usability).
- [x] Respuesta no ambigua en Q5=B (deuda de seguridad documentada, no gate nuevo).
- [x] Todo NFR tiene forma de verificación (ninguno "estándar/típico" sin medición).
- [x] Sin contradicción con `implementation-scope.md` (EN-02 parcial, EN-04 documentado, pipeline base lint/test/build).

---

## 5. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
