# Infrastructure Design — U1 (Project foundation & CI skeleton)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 2: Generation)
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U1 — `src/sentinel/foundation/` + `Dockerfile` + `.github/workflows/`
**Decisiones (plan Q1–Q4 + FQ1)**: Q1=A (GitHub-hosted, app desplegada en kind local de la máquina del usuario), Q2=A (build local + `kind load`, push documentado), Q3=B (build simple sin caché), Q4=B (solo logs estándar, sin artifacts), **FQ1=A (GitHub Actions simple: sin caché, sin artifacts; se mantiene FD Q5 y EN-01)**.

---

## 1. Mapeo componente lógico → infraestructura real

| Componente lógico (NFR Design) | Infraestructura real | Notas |
|---|---|---|
| CI workflow (P5) | `.github/workflows/ci.yml` en **GitHub-hosted** `ubuntu-latest` | Jobs simples, sin caché ni artifacts (FQ1=A, Q3=B, Q4=B) |
| Dependabot (P6) | `.github/dependabot.yml` (servicio nativo de GitHub) | Solo alertas/PRs; sin job propio |
| Containerfile | **Docker estándar** en el runner (`docker build`) | Sin buildx ni GHA cache (Q3=B) |
| Imagen OCI (P de imagen única) | Artefacto local `sentinel:test` → **`kind load docker-image sentinel:test`** en la máquina del usuario | Sin registro remoto en el pipeline (Q2=A); push a ghcr documentado como futuro |
| Config de toolchain | `pyproject.toml` + `requirements.txt` fijados | Instalación con `pip install -r requirements.txt` en CI |
| Reports de tests | Logs estándar de Actions (job `test`) | Sin artifacts (Q4=B); cobertura visible en log con `--cov-report=term-missing` |
| Ejecución de la app | **kind (o k3s) en la máquina del usuario** | "Todo el proyecto se despliega en mi máquina" (nota Q1) — ver `deployment-architecture.md` |

**No aplican a U1** (con justificación registrada en el plan): storage (SQLite/PVC = U2/U9), messaging (sin broker), networking (puertos/services = U9), shared infrastructure (namespaces/aislamiento = U9/U10 → sin `shared-infrastructure.md`).

---

## 2. Decisiones y justificación

| # | Decisión | Por qué |
|---|---|---|
| ID-01 | CI en GitHub Actions hosted, **sin** self-hosted runner ni `act` | Cero mantenimiento; FQ1=A mantiene EN-01 con status checks reales |
| ID-02 | Pipeline base exacto: `lint` (ruff) → `test` (pytest unit+property+cov ≥70) → `docker build` | Scope §2 (lint/test/build); sin etapas scan/helm-test/deploy/push |
| ID-03 | Build de imagen con `docker build` simple (sin buildx, sin cache remota) | Q3=B: simplicidad sobre velocidad; volumen de capas de foundation es pequeño |
| ID-04 | Transporte de imagen: local → `kind load` | Q2=A: sin credenciales de registro; la demo nunca depende de red externa |
| ID-05 | Sin artifacts de CI (coverage/junit solo en logs) | Q4=B |
| ID-06 | Dependabot = alertas/PRs, no gate | Q4 requirements (NFR Design P6) |
| ID-07 | Entorno de despliegue = kind local en la máquina del usuario | Nota Q1; NFR-TECH-01 (kind/k3s); alineado con `demo-plan.md` |

---

## 3. Recursos consumidos por U1

| Recurso | Propiedad | Coste/mantenimiento |
|---|---|---|
| Runner GitHub (`ubuntu-latest`, 2 vCPU, 7 GB) | GitHub (gratis en repo público; cuota en privado) | Ninguno propio |
| Docker en el runner | Preinstalado en ubuntu-latest | Ninguno |
| kind cluster en la máquina del usuario | Local | Lo crea/mantiene el usuario (comandos documentados en U11) |
| Registro de imágenes | **No usado** (push documentado como futuro) | — |

---

## 4. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
