# Unit of Work Plan — Sentinel

**Fase**: INCEPTION — Units Generation (Parte 1: Planning)
**Fecha**: 2026-11-07
**Estado**: ANSWERS_COMPLETE — respuestas recibidas (todas A); pendiente aprobación explícita del plan
**Entradas**: `requirements.md` (M1–M10), `stories.md` (ST-M1..M10 + EN-01..07), `application-design.md`, `execution-plan.md`, `implementation-scope.md`

---

## 1. Propósito

Descomponer Sentinel en unidades de trabajo manejables para CONSTRUCTION, asignar todas las historias y fijar dependencias, orden y estrategia de organización del código.

**Definición de unidad**: agrupación lógica de historias para desarrollo. En Sentinel el Core es un monolito modular (una unidad de aplicación con módulos internos); Discovery y Sensor son workloads separados del mismo proyecto/imagen. Por tanto, "unidad" aquí es una unidad de construcción, no necesariamente un servicio desplegable independiente.

---

## 2. Propuesta base (a confirmar con las respuestas)

| Orden | Unidad candidata | Módulos | Depende de |
|---|---|---|---|
| 1 | Project foundation & CI skeleton | EN-01, EN-05 | — |
| 2 | Core API, persistence & export | M4 | 1 |
| 3 | Operator GUI & network report | M10 | 2 |
| 4 | Configuration, scope & Discovery | M1, M2 | 2 |
| 5 | Traffic Sensor & ARP observation | M3 | 1, 2 |
| 6 | Baseline & deterministic conditions | M5 | 2, 5 |
| 7 | Metrics exposure | M6 | 2, 6 |
| 8 | Observability & alerting | M7 | 6, 7 |
| 9 | Kubernetes runtime & Helm | M8 | 1–8 |
| 10 | Security & negative tests | M9 | 1–9 |
| 11 | Documentation & GT evidence | EN-03, EN-06 | 1–10 |

**Nota**: `implementation-scope.md` define qué se implementa para la demo y qué solo se documenta. Las unidades se mantienen para trazabilidad completa.

---

## 3. Checklist del plan

- [x] Analizar requirements, stories, application design y execution plan
- [x] Identificar unidades candidatas y dependencias
- [x] Recoger respuestas a los `[Answer]:`
- [x] Analizar respuestas y resolver ambigüedades (seguimientos si aplica) — todas A; sin ambigüedades; propuesta base confirmada
- [ ] Solicitar aprobación explícita del plan
- [x] Generar `unit-of-work.md`
- [x] Generar `unit-of-work-dependency.md`
- [x] Generar `unit-of-work-story-map.md`
- [x] Documentar estrategia de organización del código (greenfield) — monorepo `src/sentinel/` (§3 de unit-of-work.md)
- [x] Validar límites, dependencias y asignación completa de historias — 58/58 historias, grafo acíclico
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 4. Preguntas de descomposición

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas.

### Question 1 — Granularidad de las unidades

A) Mantener 11 unidades (recomendado): trazabilidad fina, secuencia dependency-first y cierre por unidad

B) Consolidar a 6–7 unidades para reducir overhead de coordinación

C) Usar 3 macro-unidades (Core, Runtime/K8s, Documentación)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Unidades de colectores

A) Discovery y Sensor como unidades separadas (recomendado), aunque compartan imagen y proyecto

B) Una sola unidad "Data collectors" que agrupe Discovery y Sensor

C) Integrarlos dentro de la unidad Core

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Cobertura de historias no implementadas en la demo

A) Asignar todas las historias a unidades, marcando las no implementadas como `documented-only` (recomendado)

B) Asignar solo las historias del alcance implementado y listar el resto aparte

C) Excluir del mapa las historias no implementadas

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Organización del código (greenfield)

A) Monorepo único: `src/sentinel/` para módulos, `charts/`, `tests/`, `docs/` (recomendado)

B) Paquetes separados por unidad (`packages/core`, `packages/discovery`, `packages/sensor`)

C) Directorios por capa (`api/`, `services/`, `collectors/`, `ui/`)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Paralelización

A) Dependency-first, con GUI y Discovery en paralelo tras cerrar Core (recomendado)

B) Estrictamente secuencial, una unidad a la vez

C) Máxima paralelización entre unidades independientes

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Ownership / alineación de equipo

A) Desarrollador único: sin owner formal por unidad (recomendado)

B) Equipo pequeño: asignar un owner por unidad

C) Especialistas: frontend, backend e infraestructura

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Momento de Build & Test

A) Una sola vez al final, sobre las unidades implementadas (recomendado)

B) Por unidad y además al cierre

C) Solo smoke tests de la demo

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Unidad de documentación y evidencia GT

A) Unidad separada al final (recomendado)

B) Documentación incremental dentro de cada unidad, sin unidad final

C) Solo un entregable de cierre para la demo

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 5. Artefactos obligatorios (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `unit-of-work.md` | Definiciones, responsabilidades, orden y estrategia de organización del código |
| `unit-of-work-dependency.md` | Matriz de dependencias, orden de ejecución y puntos de integración |
| `unit-of-work-story-map.md` | Mapa completo historia → unidad, con marca `documented-only` cuando aplique |

---

## 6. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, pediré aprobación explícita del plan antes de generar artefactos.

**No se genera ningún artefacto de Units Generation hasta completar este gate.**
