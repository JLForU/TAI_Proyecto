# NFR Design Plan — U1 (Project foundation & CI skeleton)

**Fase**: CONSTRUCTION — NFR Design (Parte 1: Planning)
**Fecha**: 2026-11-11
**Estado**: ARTIFACTS_GENERATED — respuestas 4/4=A; pendiente de aprobación formal
**Unidad**: U1 — `src/sentinel/foundation/`
**Entradas**: `construction/u1-foundation/nfr-requirements/*` (aprobado: NFR-U1-PERF/REL/SEC/MNT, TS-01..TS-11), Functional Design de U1 (aprobado)

---

## 1. Contexto del assessment (Step 1 — analizado)

Cómo incorporar los NFR aprobados de U1 en **patrones de diseño y componentes lógicos** concretos de la librería. U1 no tiene estado ni I/O: los patrones de sistema completo (reintentos de red, failover, escala de workloads) pertenecen a U2/U5/U9 — aquí solo se diseña lo que foundation aporta como **primitiva compartida** o **garantía de calidad**.

**Categorías evaluadas**:

| Categoría | Aplica a U1 | Tratamiento |
|---|---|---|
| Resilience Patterns | Parcialmente | Q1 — primitiva de retry/backoff compartida para colectores |
| Scalability Patterns | No | **Sin pregunta**: librería stateless sin estado que escalar; límites de cardinalidad ya cubiertos por BR-21/BR-22; capacidad = U2/U9 |
| Performance Patterns | No | **Sin pregunta**: NFR-U1-PERF-01 ya fija la política "sin optimización prematura" (Q6 requirements); no hay hot-path propio en foundation |
| Security Patterns | Sí | Q2 (límites de entrada en modelos), Q4 (política de Dependabot) |
| Logical Components | Sí | Q3 (cliente HTTP de colectores: dónde vive) |

---

## 2. Checklist del plan

- [x] Analizar NFR requirements aprobados
- [x] Generar preguntas de diseño NFR (Q1–Q4)
- [x] Recoger respuestas a los `[Answer]:`
- [x] Analizar respuestas y resolver ambigüedades (seguimientos si aplica) — 4/4=A; sin ambigüedades
- [x] Generar `nfr-design/nfr-design-patterns.md`
- [x] Generar `nfr-design/logical-components.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas.

### Question 1 — Patrón de reintento (Resilience Patterns)

Contexto: `services.md` define "reintentos con backoff" para que los colectores (U4/U5) le envíen observaciones al Core sin perder lotes.

A) Primitiva compartida `foundation.retry` (`with_retries(fn, attempts, base_delay, jitter)`, stdlib puro, sin dependencias); U4/U5 la importan *(recomendado)*

B) Cada colector implementa su propio backoff (sin helper compartido)

C) Solo documentar el patrón en `docs/`; sin código en foundation

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Límites de entrada en modelos (Security Patterns)

Contexto: los lotes de observaciones llegan de colectores por HTTP; sin límites, un payload enorme consumiría memoria en la validación.

A) Constantes de límite en los modelos (`MAX_BATCH_ITEMS`, longitudes máximas de string/MAC/hostname) con error `ValidationError` si se exceden; valor fijo, no configurable desde env *(recomendado)*

B) Sin límites explícitos: el volumen de lab no lo justifica (confiar en el tamaño de lote de U2)

C) Límites configurables por env/Helm — requeriría ampliar `foundation.config` (rompe BR-06: solo claves comunes)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Cliente HTTP de colectores (Logical Components)

Contexto: U4 y U5 deben enviar lotes al Core con token y reintentos. ¿Dónde vive ese cliente?

A) En cada módulo colector (`sentinel/discovery/client.py`, `sentinel/traffic/client.py`), reutilizando `foundation.retry` y los modelos; foundation **no** importa HTTP (mantiene BR-19) *(recomendado)*

B) Cliente único `foundation.http` compartido (viola BR-19 — requeriría re-aprobar la frontera de foundation)

C) Nuevo paquete `sentinel/shared/` fuera de foundation para el cliente (añade un componente no previsto en las unidades)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Política de Dependabot (Security Patterns)

Contexto: TS-09/NFR-U1-SEC-02 activan Dependabot; Q5=B dejó el resto de seguridad extra como deuda documentada.

A) Solo **alertas y PRs automáticos** de Dependabot, sin gate de CI nuevo — revisión manual del desarrollador *(recomendado, coherente con Q5=B)*

B) Bloquear CI en vulnerabilidades `high`/`critical` (job adicional de escaneo de dependencias)

C) Dependabot desactivado; revisión manual de `requirements.txt`

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Artefactos obligatorios (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `construction/u1-foundation/nfr-design/nfr-design-patterns.md` | Patrones aplicados por NFR (fail-fast, validación acotada, retry, gate de calidad CI, logging estructurado) con mecanismo y verificación |
| `construction/u1-foundation/nfr-design/logical-components.md` | Componentes lógicos de foundation + bordes con otras unidades (quién importa qué, dónde vive el cliente HTTP, helper de testing) |

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los artefactos de NFR Design y presentaré el mensaje de completitud.

**No se genera ningún artefacto de NFR Design hasta completar este gate.**
