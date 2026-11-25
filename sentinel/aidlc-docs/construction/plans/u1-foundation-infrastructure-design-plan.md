# Infrastructure Design Plan — U1 (Project foundation & CI skeleton)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 1: Planning)
**Fecha**: 2026-11-11
**Estado**: ARTIFACTS_GENERATED — respuestas completas (Q1 resuelta con seguimiento FQ1=A); pendiente de aprobación
**Unidad**: U1 — `src/sentinel/foundation/` + `Dockerfile` + `.github/workflows/`
**Entradas**: Functional Design y NFR Design de U1 (aprobados), `requirements.md` §4 (K8s 1.28+, Alpine, kind/k3s), `implementation-scope.md` §2, `unit-of-work.md` §3

---

## 1. Contexto del assessment (Step 1 — analizado)

U1 **no se despliega** (es librería + imagen base + pipeline). Su infraestructura real es: el **runner de CI**, la **construcción de la imagen OCI** y los **artefactos de verificación**. El despliegue en clúster (chart, PVC, services, namespaces) pertenece a U9; los controles de admisión/RBAC a U10.

**Categorías evaluadas**:

| Categoría | Aplica a U1 | Tratamiento |
|---|---|---|
| Deployment Environment | Parcialmente | Q1 (runner de CI), Q2 (registro/transporte de imagen) |
| Compute Infrastructure | Parcialmente | Q3 (caché de build de imagen) |
| Storage Infrastructure | No | **Sin pregunta**: U1 no persiste — SQLite/PVC en U2/U9 |
| Messaging Infrastructure | No | **Sin pregunta**: sin broker/colas (decisión de diseño #7 de `application-design.md`) |
| Networking Infrastructure | No | **Sin pregunta**: U1 no expone puertos ni servicios (mapa de red = U9) |
| Monitoring Infrastructure | Parcialmente | Q4 (artefactos de CI: reports); logs a stdout ya decididos en FD |
| Shared Infrastructure | No | **Sin pregunta**: sin `shared-infrastructure.md` — namespaces/aislamiento = U9/U10; U1 solo publica artefactos reutilizables (imagen, config de toolchain) |

---

## 2. Checklist del plan

- [x] Analizar Functional y NFR Design
- [x] Generar preguntas de infraestructura (Q1–Q4)
- [x] Recoger respuestas a los `[Answer]:`
- [x] Analizar respuestas y resolver ambigüedades (seguimientos si aplica) — Q1 resuelta vía FQ1=A (GitHub Actions simple); Q2=A, Q3=B, Q4=B; sin ambigüedades pendientes
- [x] Generar `infrastructure-design/infrastructure-design.md`
- [x] Generar `infrastructure-design/deployment-architecture.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de infraestructura

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas.

### Question 1 — Runner de CI (Deployment Environment / Compute)

A) **GitHub-hosted runners** (`ubuntu-latest`) para todos los jobs: sin infraestructura que mantener *(recomendado)*

B) Self-hosted runner en la máquina del laboratorio (control total, pero mantenimiento propio)

C) `act` (ejecución local de workflows) sin CI remoto

D) Other (describe después de `[Answer]:`)

[Answer]: A — GitHub-hosted runner (ubuntu-latest). Nota del usuario: "Todo el Proyecto se va a desplegar en mi máquina" (kind local para dev/demo; el CI corre en hosted runners, ver seguimiento FQ1)

### Question 2 — Transporte de la imagen OCI (Deployment Environment)

Contexto: el pipeline base es lint/test/build (scope §2) y la demo despliega en **kind**.

A) **Build local + `kind load docker-image`** para dev/demo; el push a un registro (ghcr.io) queda documentado como futuro *(recomendado, coherente con scope sin etapa push/deploy)*

B) Push automático a **ghcr.io** en el pipeline (requiere auth y amplía lint/test/build)

C) Docker Hub público (registro externo, credenciales adicionales)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Caché de build de imagen (Compute Infrastructure)

A) **Docker Buildx + caché de GitHub Actions** (capas reutilizadas entre runs; `cache-from/to` en GHA) *(recomendado)*

B) `docker build` simple sin caché (más lento, más simple)

C) Registro con caché remota (ghcr + buildx cache — excede Q2=A)

D) Other (describe después de `[Answer]:`)

[Answer]: B. No me quiero complicar con GitHub Actions.

### Question 4 — Artefactos de verificación de CI (Monitoring Infrastructure)

A) Subir como **artifacts de Actions** el informe de cobertura (`coverage.xml`/txt) y `junit.xml` de pytest; logs estándar para el resto *(recomendado)*

B) Solo logs estándar de Actions (sin artifacts)

C) Publicar resultados de cobertura en el README (badge/estadísticas)

D) Other (describe después de `[Answer]:`)

[Answer]: B

---

## 4. Artefactos obligatorios (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `construction/u1-foundation/infrastructure-design/infrastructure-design.md` | Mapeo componente lógico → infraestructura real (runner, caché, imagen, artifacts), decisiones y justificación |
| `construction/u1-foundation/infrastructure-design/deployment-architecture.md` | Flujo CI/CD de U1: jobs, dependencias, gates, cómo la imagen llega a kind, y qué queda fuera (push/deploy) |

`shared-infrastructure.md` **no aplica** (categoría justificada arriba).

---

## 5. Seguimiento (FQ1 — ambigüedad de Q1/Q3)

**Pregunta**: ¿Cómo ejecutamos CI/lint/tests/build? (Q1 mencionaba despliegue, Q3 decía "no me quiero complicar con GitHub Actions" — posible contradicción con FD Q5=A y EN-01.)

**Respuesta del usuario**: **A) GitHub Actions simple** (sin caché ni artifacts — compatible con Q3=B y Q4=B; NO rompe FD Q5 ni EN-01).

**Efecto**: se mantiene `.github/workflows/ci.yml` con jobs `lint`, `test`, `build` simples (`ruff`, `pytest`, `docker build`); sin buildx cache, sin artifacts subidos, sin self-hosted runner. FQ2 queda anulada (condicionada a la opción B).

---

## 6. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los artefactos de Infrastructure Design y presentaré el mensaje de completitud.

**No se genera ningún artefacto de Infrastructure Design hasta completar este gate.**
