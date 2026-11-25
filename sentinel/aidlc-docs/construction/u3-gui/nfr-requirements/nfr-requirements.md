# NFR Requirements — U3 (Operator GUI & network report)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 2: Generation)
**Fecha**: 2026-11-14
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U3 — `src/sentinel/gui/`
**Decisiones (plan Q1–Q12)**: **A en todas** (2026-11-14).
**Entradas**: Functional Design de U3 (aprobado 2026-11-14T14:52:00Z), `requirements.md` §3/§4/§5, U1/U2 `tech-stack-decisions.md`, `implementation-scope.md`.

---

## 1. Alcance

NFR **específicos de U3** (GUI server-rendered + ReportService MD/PDF sobre loopback). Hereda sin cambio TS-01..11 de U1 y el stack global (FastAPI, Python 3.11). Los NFR de runtime K8s/imagen/pipeline se evalúan en U9/U10; aquí solo los que imponen restricciones verificables sobre el módulo `gui/`.

**Fijados por requisito/aprobados (no se preguntaron)**: NFR-TECH-04 (stack UI), NFR-OPS-04 (assets/templates baked), NFR-OPS-05 (determinismo del reporte), FR-GUI-07 (sin auth, port-forward), FD Q2/Q11/Q12/Q13 (loopback, WeasyPrint, static vendorizado, sin config nueva), App Design Q6=A (reporte síncrono).

---

## 2. Requisitos no funcionales de U3

### 2.1 Rendimiento y capacidad (Performance / Scalability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U3-PERF-01 | Baseline **informativo** de latencia de páginas (`/ui/assets`, `/ui/report`): registra p50/p95 en la suite **sin gate** en CI (misma bar que NFR-U2-PERF-02) | Plan Q1=A | `tests/.../test_latency_gui.py` (imprime percentiles, no assert) |
| NFR-U3-PERF-02 | Reporte **síncrono acotado**: `generate()` sin límite artificial de filas; timeout HTTP explícito **30 s** ⇒ si se excede, la GUI responde **502** con detail; envolvente lab (≤50 activos) documentada como supuesto | Plan Q3=A, App Design Q6=A | test con timeout forzado ⇒ 502; doc de envolvente |
| NFR-U3-SCAL-01 | Inventario con N+1 **secuencial** acotado: `limit=100` fijo por página, ≤100 llamadas de detalle por render, sobre loopback del mismo pod; **sin caché ni prefetch**; crecimiento más allá de 50 activos se revisa en U11 (como NFR-U2-SCAL-01) | Plan Q2=A, FD FQ1=A | revisión de código (`limit` constante); checklist U11 |

### 2.2 Disponibilidad (Availability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U3-AVAIL-01 | **Degradación fail-fast** ante API loopback caída: `GuiClient` 1 intento + timeout ⇒ página **502** "Core API no disponible" sin traceback (sin `foundation.retry` — dueño del fallo responde rápido, como NFR-U2-REL-03); polling HTMX de discovery con backoff 2–5 s y detención tras N fallos | Plan Q6=A, FD BR-U3-31 | test con API apagada ⇒ 502 + sin traceback; test de backoff del polling |
| NFR-U3-AVAIL-02 | La GUI no añade estado persistente: sin sesión, sin caché de plantillas, sin worker propio — el Core se reinicia sin pérdida de la UI (NFR-AVAIL-02 la cubre vía U2) | FR-GUI-07, FD §1 | revisión: cero estado en módulos `gui/` |

### 2.3 Seguridad (Security — extensión SECURITY blocking)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U3-SEC-01 | **XSS de render**: Jinja **autoescape ON explícito** para `*.html`; escape de datos crudos en los builders de secciones MD/HTML del reporte; HTMX solo por `hx-get`/forms (sin inyección de `innerHTML` con datos de red) | Plan Q4=A, NFR-SEC-01 | test: payload `<script>` en hostname/details ⇒ literal escapado en HTML y MD |
| NFR-U3-SEC-02 | **Superficie sin sesión**: sin cookies/tokens/CSRF (no hay sesión que proteger — FR-GUI-07); **validación estricta** de params en handlers (`date` `YYYY-MM-DD`, `page ≥ 1`, `host` con forma IP/hostname, `format ∈ {md,pdf}`) reutilizando errores 400/422; riesgo residual CSRF documentado para threat model de U10 | Plan Q5=A, NFR-SEC-01 | tests de params inválidos ⇒ 400/422; sección de threat model (U10) |
| NFR-U3-SEC-03 | Transporte y exposición: **hereda NFR-U2-SEC-01** (HTTP plano, port-forward + NetworkPolicy default-deny de U9/U10); U3 no abre puertos ni añade Services | NFR-SEC-01, FR-GUI-07 | manifiestos U9/U10 (Build & Test); U3 sin `uvicorn.run` propio |

### 2.4 Mantenibilidad (Maintainability)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U3-MNT-01 | Cobertura **≥ 70%** en `src/sentinel/gui/` en el job `test` (mismo bar que TS-06/TS-U2-MNT-02) | Plan Q7=A | `pytest --cov=sentinel.gui --cov-fail-under=70` |
| NFR-U3-MNT-02 | Estrategia de tests de UI: **TestClient + assertions de substring/regex sobre HTML** + tests unitarios de view models y builders + `httpx.MockTransport` para `GuiClient` (sin browser ni parser HTML) | Plan Q8=A, TS-U2-04 | `tests/unit/gui/`, `tests/integration/test_gui_*`; AC con `grep -c` |
| NFR-U3-MNT-03 | **Sin PBT propio**: el alcance de NFR-TECH-03 (Nmap XML, flow normalization, baseline) no toca U3; la propiedad "mismo rango ⇒ mismas secciones" se cubre con `test_report_determinism.py` de integración | Plan Q9=A, NFR-TECH-03 | `pytest tests/integration/test_report_determinism.py` |
| NFR-U3-MNT-04 | Logging hereda `foundation.logging` (JSON, `component=gui`); **cero familias de métricas nuevas** — los `/ui/*` ya se cuentan en `api_requests_total` vía middleware de U2 (catálogo `METRIC_FAMILIES` fijo para U7/U8) | Plan Q10=A, BR-20..22 U1 | test de log JSON en handler; `collect()` sigue exacto con `METRIC_FAMILIES` |
| NFR-U3-MNT-05 | `ruff check` + `ruff format --check` + `mypy` en verde sobre `gui/` (hereda TS-04/05) | TS-04/05 | job `lint`/`typecheck` de CI |

### 2.5 Stack técnico (Tech Stack)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U3-TECH-01 | Stack UI **fijado**: FastAPI + Jinja2 + HTMX + Tailwind/DaisyUI, server-rendered, **sin SPA build step**; servido por el workload Core (NFR-OPS-04) | NFR-TECH-04 | imports/dependencias; imagen sin etapa de build JS |
| NFR-U3-TECH-02 | PDF con **WeasyPrint** (MD → HTML → PDF) + paquetes de sistema `pango`/`cairo` en el Dockerfile; MD con librería `markdown` (pines exactos, P6) | FD Q11=A (corregido), tech-stack nota | test `%PDF`; `docker build` verde |
| NFR-U3-TECH-03 | Static **vendorizado** en repo (`htmx.min.js` + CSS pre-generado), embebido en la imagen; sin CDN ni build en CI | FD Q12=A, NFR-OPS-04 | archivos presentes en `gui/static/`; plantillas sin CDN |

### 2.6 Usabilidad (Usability — única unidad con UI)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U3-USAB-01 | **Responsive de laptop**: breakpoints Tailwind `md:`/`lg:` (target ≥1024 px), tablas con `overflow-x-auto`, base tipográfica DaisyUI; verificación **manual** en la demo (sin framework de browser) | Plan Q11=A, NFR-TECH-04 | checklist visual en guion de demo (U11) |
| NFR-U3-USAB-02 | **Estados vacíos explícitos** por vista con mensaje + acción sugerida: inventario "sin activos — dispara discovery"; timeline "sin eventos en el rango"; tráfico/reporte `sin datos`; sensor caído ≠ red sin activos | Plan Q12=A, services.md §4/§2.6, FR-GUI-05 | `test_gui_health -k sensor_down`; tests de estado vacío en assets/timeline |

---

## 3. Trazabilidad con NFR globales

| NFR global | Contribución de U3 |
|---|---|
| NFR-PERF-03 (Core API p95 <500 ms, not binding) | PERF-01: baseline informativo extiende la medición a páginas GUI |
| NFR-AVAIL-01 (sin HA) | AVAIL-01/02: degradación controlada, sin estado propio |
| NFR-SEC-01 (SECURITY blocking) | SEC-01/02/03 (autoescape/escape, validación de params, hereda transporte) |
| NFR-TECH-03 (PBT: Nmap/flow/baseline) | MNT-03: confirmación de no aplicabilidad en U3 |
| NFR-TECH-04 (stack GUI) | TECH-01 (fijado, sin pregunta), USAB-01 (responsive laptop) |
| NFR-OPS-04 (assets baked) | TECH-03 (vendorizado, sin CDN) |
| NFR-OPS-05 (determinismo) | hereda FD BR-U3-21; MNT-03 lo verifica por integración |
| NFR-OPS-02 (pipeline CI) | MNT-01/02/05 dentro de lint/test/build heredado |

---

## 4. Criterios de aceptación del assessment

- [x] Las 12 preguntas del plan respondidas sin ambigüedad (todas A).
- [x] Categorías evaluadas con justificación de omisión (Tech Stack fijado; Reliability cerrado en FD).
- [x] Todo NFR tiene forma de verificación (ninguno "estándar/típico" sin medición).
- [x] Sin contradicción con `implementation-scope.md`, FD de U3 (Q1–Q13+FQ), NFR-TECH-04/OPS-04/05 ni TS-01..11.
- [x] Q5=A registrado explícitamente: ausencia de sesión/CSRF = decisión (no hay sesión), no omisión.

---

## 5. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
