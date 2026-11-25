# Functional Design Plan — U1 (Project foundation & CI skeleton)

**Fase**: CONSTRUCTION — Functional Design (Parte 1: Planning)
**Fecha**: 2026-11-11
**Estado**: ARTIFACTS_GENERATED — respuestas todas A; artefactos generados; pendiente de aprobación
**Unidad**: U1 — `src/sentinel/foundation/`
**Entradas**: `inception/application-design/unit-of-work.md` (§U1, §3 código), `unit-of-work-story-map.md` (EN-01*, EN-02, EN-05), `requirements.md` (NFR-TECH-02/03, §4 constraints, §5 extensiones), `components.md` (C2 Pydantic), `implementation-scope.md`, `DECISIONES_PENDIENTES.md`

---

## 1. Contexto de la unidad (Step 1 — analizado)

- **Responsabilidad**: layout del repo, imagen OCI única comandos separados, pipeline CI base, base Alpine no-root, modelos tipados, config/logging/contratos compartidos, infraestructura de tests base.
- **Historias**: EN-01 (implemented, etapas lint/test/build), EN-05 (implemented), EN-02 (documented-only en el mapa actual — ver Q8).
- **Frontera**: modelos/validadores se prueban sin sockets, clúster ni BD; no sondea, no captura, no persiste.
- **Stack fijado por requisitos**: Python 3.11+, FastAPI + Jinja2 + HTMX + Tailwind/DaisyUI (GUI en U3), scapy/python-nmap (U4/U5), SQLite (U2), Alpine base, GitHub Actions / GitLab CI permitidos; repo actual en **GitHub** (`JLForU/TAI_Proyecto`).
- **Categoría Frontend**: **no aplica** a U1 (sin UI) — sin preguntas de componentes.

---

## 2. Checklist del plan

- [x] Analizar unidad, historias y restricciones
- [x] Generar preguntas de diseño funcional (Q1–Q9)
- [x] Recoger respuestas a los `[Answer]:`
- [x] Analizar respuestas y resolver ambigüedades (seguimientos si aplica) — todas A; sin ambigüedades; Q8 actualiza `implementation-scope.md` (EN-02 parcial)
- [x] Generar `business-logic-model.md`, `business-rules.md`, `domain-entities.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño funcional

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas.

### Question 1 — Modelos de dominio y validación (Domain Model)

A) Modelos Pydantic compartidos: el dominio usa Pydantic (mismo set que consumirá la API del Core; una sola fuente de verdad, coherente con C2) *(recomendado)*

B) Capa estricta: `dataclasses` para el dominio + schemas Pydantic solo en la frontera API (desacopla dominio de HTTP)

C) `attrs` como modelos de dominio

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Alcance de la config en foundation (Business Logic / Data Flow)

A) Solo config común: `LOG_LEVEL`, `COMPONENT`, `DEBUG` (y loader desde env/Helm values comunes); la config de scope/discovery/traffic vive en U4/U5 *(recomendado)*

B) Esquema completo en foundation: scope, discovery, traffic, gui como fuente única de configuración del proyecto

C) Sin módulo de config en foundation; cada unidad carga su propia config

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Contrato de métricas (Business Rules)

A) Foundation define constantes del prefijo/familias `sentinel_*` y el contrato documentado; U7 los consume al armar `/metrics` *(recomendado)*

B) U7 define todo el contrato; foundation no incluye nada de métricas

C) Solo documentar el contrato en `docs/`, sin constantes en código

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Contrato de logging (Data Flow / Error Handling)

A) stdlib `logging` + formatter JSON a stdout: campos `ts`, `level`, `component`, `event`, `msg` + extras; logger por componente *(recomendado)*

B) `structlog` como dependencia de foundation

C) Función propia `log_json(event, **fields)` sin stdlib logging

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Plataforma de CI (Integration Points)

A) GitHub Actions: etapas `lint`, `test`, `build` (scan documentado, fuera del pipeline base según scope §2); repo ya está en GitHub *(recomendado)*

B) GitLab CI con las mismas etapas

C) Script local `scripts/ci.sh` + GitHub Actions que lo invoca

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Toolchain de lint/formato (Business Rules)

A) `ruff` para lint + formato (una sola herramienta, rápido, config en `pyproject.toml`) *(recomendado)*

B) `black` + `flake8` (clásico, dos herramientas)

C) `pylint` estricto sin formatter automático

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Manejo de errores (Error Handling)

A) Jerarquía `SentinelError` → `ConfigError`, `ScopeError`, `ValidationError`, `IngestionError`, `ProbeError`…; los módulos la extienden, la API traduce a códigos HTTP *(recomendado)*

B) Solo excepciones estándar de Python (`ValueError`, `RuntimeError`…) sin tipo propio

C) Patrón `Result` (valor/errores) sin excepciones

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Property-based testing vs estado de EN-02 (Business Scenarios / Quality)

Contexto: la extensión PBT está **PARTIAL (blocking para áreas designadas)**: Nmap XML parsing, flow normalization, baseline (`requirements.md` §5), pero `implementation-scope.md` no lista EN-02 en el alcance implementado.

A) Aplicar PBT (hypothesis) donde el área esté construida: Nmap XML en U4, flow normalization en U2, baseline mínimo en U6; EN-02 pasa a `implemented` con alcance parcial — implica re-aprobar el ajuste en `implementation-scope.md` *(recomendado)*

B) Mantener EN-02 `documented-only`: las áreas designadas se cubren con tests unitarios parametrizados (fixtures) y la extensión queda como deuda documentada

C) PBT completo para las tres áreas designadas aunque baseline/flow solo tengan el mínimo implementado (sin cambiar EN-02)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 9 — Versión de Python objetivo (Technical / CI)

A) Fijar 3.11 en CI y contenedores (mínimo del constraint; máxima compatibilidad) *(recomendado)*

B) Fijar 3.12 (más rápido, features nuevas)

C) Matriz 3.11 + 3.12 en CI (compatibilidad dual)

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Artefactos obligatorios (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `construction/u1-foundation/functional-design/business-logic-model.md` | Lógica de fundación: loaders, logging, contratos, pipeline de validación, entrypoints de imagen |
| `construction/u1-foundation/functional-design/business-rules.md` | Reglas y restricciones (no-root, JSON logging, prefijo de métricas, toolchain, versiones) |
| `construction/u1-foundation/functional-design/domain-entities.md` | Entidades tipadas, campos, relaciones e identidad |

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los artefactos de Functional Design y presentaré el mensaje de completitud.

**No se genera ningún artefacto de Functional Design hasta completar este gate.**
