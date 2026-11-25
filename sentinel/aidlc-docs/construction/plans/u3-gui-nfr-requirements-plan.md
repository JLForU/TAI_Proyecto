# NFR Requirements Plan — U3 (Operator GUI & network report)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 1: Planning)
**Fecha**: 2026-11-14
**Estado**: ARTIFACTS_GENERATED — respuestas todas A (2026-11-14); artefactos generados; pendiente de aprobación
**Unidad**: U3 — `src/sentinel/gui/`
**Entradas**: `construction/u3-gui/functional-design/*` (aprobado 2026-11-14T14:52:00Z), `requirements.md` §3 NFR + §4 constraints + §5, U1 `tech-stack-decisions.md` (TS-01..11), U2 `tech-stack-decisions.md` (TS-U2-01..10), `implementation-scope.md`.

---

## 1. Contexto del assessment (Step 1 — analizado)

U3 es la **única unidad con UI real** y con generación de documentos (MD/PDF). Sus NFR tocan rendimiento de páginas server-rendered (con el N+1 de FQ1), seguridad de la superficie web (XCS/CSRF/sesión — extensión SECURITY es *blocking*), degradación cuando la API loopback falla, mantenibilidad de tests de HTML/plantillas, y usabilidad (responsive laptop, estados vacíos).

**Ya decidido (NO se pregunta)**: stack fijado por NFR-TECH-04 (FastAPI + Jinja2 + HTMX + Tailwind/DaisyUI, server-rendered, sin SPA build); assets/templates baked en imagen (NFR-OPS-04); reporte determinista con 5 secciones y `from`/`to` requeridos (NFR-OPS-05 + FD Q9/Q10); loopback HTTP exclusivo (FD Q2); WeasyPrint para PDF (FD Q11); sin claves de config nuevas (FD Q13); sin auth de operador, port-forward only (FR-GUI-07); sin worker asíncrono de reportes (App Design Q6=A); TS-01..11 de U1; PBT fijado a Nmap XML/flow normalization/baseline (NFR-TECH-03 — ninguno en U3).

**Categorías evaluadas**:

| Categoría | Aplica a U3 | Tratamiento |
|---|---|---|
| Scalability | Parcial | Q2 (envolvente del N+1 en inventario), Q3 (envelope del reporte síncrono) |
| Performance | Sí | Q1 (latencia de páginas, informativa como U2) |
| Availability | Sí | Q6 (degradación ante API loopback caída) |
| Security | Sí | Q4 (XSS/escaping), Q5 (superficie: CSRF/sesión + validación de params) — extensión SECURITY blocking |
| Tech Stack | Fijado | **Sin pregunta de stack** (NFR-TECH-04); pins y strategy en `tech-stack-decisions.md` |
| Reliability | Parcial | Determinismo y errores ya cerrados en FD (BR-U3-21/31); sin pregunta |
| Maintainability | Sí | Q7 (gate de cobertura gui/), Q8 (estrategia de tests de UI), Q9 (aplicabilidad PBT), Q10 (logging/métricas) |
| Usability | **Sí** | Q11 (responsive/laptop), Q12 (estados vacíos/carga) — única unidad donde Usability aplica de lleno |

---

## 2. Checklist del plan

- [x] Analizar Functional Design y NFR globales
- [x] Generar preguntas NFR (Q1–Q12)
- [x] Recoger respuestas a los `[Answer]:` (todas A, 2026-11-14)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; sin ambigüedades; sin seguimientos
- [x] Generar `nfr-requirements/nfr-requirements.md`
- [x] Generar `nfr-requirements/tech-stack-decisions.md`
- [ ] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Latencia de páginas GUI (Performance)

Contexto: NFR-PERF-03 (Core API p95 <500 ms) es *not binding*; U2 ya usa un baseline informativo (`test_latency_baseline.py` imprime p95 sin gate). La GUI añade render + N+1 sobre el mismo loopback.

A) Test **informativo** de latencia para `/ui/assets` y `/ui/report` (registra p50/p95 en la suite, sin bloquear CI) — misma bar que U2 *(recomendado)*

B) Convertir p95<500 ms de páginas GUI en gate de CI (flaky en runners compartidos)

C) Sin medición de latencia en U3

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Envolvente del N+1 en inventario (Scalability)

Contexto: FQ1=A fija ≤100 filas/página × 1 detalle HTTP por fila sobre loopback en el mismo pod; envolvente de lab = 10–50 activos (NFR-U2-PERF-01).

A) Mantener N+1 **secuencial** con `limit=100` fijo; documentar la envolvente (≤100 filas/pág, ≤50 activos totales en lab) como supuesto de capacidad; sin caché ni prefetch *(recomendado)*

B) Fetch **concurrente** de los detalles (httpx + threadpool) para reducir p95 de la página

C) Reabrir `AssetSummary` de U2 (ya rechazado en FQ1 del FD)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Envelope del reporte síncrono (Performance / Reliability)

Contexto: `generate()` hace 1 llamada paginada de activos + eventos + alertas + 1 detalle por activo (top talkers), todo síncrono (App Design Q6=A); WeasyPrint añade coste de render PDF.

A) Síncrono **sin límite artificial de filas**; `timeout` explícito del cliente HTTP = **30 s** ⇒ si se excede, la GUI responde 502 con detail (envolvente lab ≤50 activos documentada); PDF en el mismo tiempo *(recomendado)*

B) Límite duro de activos para el reporte (p. ej. 200) con error claro si se excede

C) Streaming del reporte (chunked) para percibir progreso

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — XSS y escaping (Security — extensión blocking)

Contexto: NFR-SEC-01 refuerza las reglas SECURITY como *blocking*; la GUI renderiza datos de red (hostnames, payloads, details de eventos) que podrían contener markup; el reporte MD embebe esos mismos datos.

A) **Jinja autoescape ON** para `*.html` (explícito, no implícito) + escape de datos crudos en los builders de secciones MD/HTML del reporte + HTMX usa `hx-get` de enlaces (sin `innerHTML` con datos de red) *(recomendado)*

B) A + cabecera `Content-Security-Policy` restrictiva en respuestas `/ui/*`

C) Sin medidas especiales (los datos de la LAN son de confianza)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Superficie: CSRF/sesión y validación de parámetros (Security)

Contexto: FR-GUI-07 = sin auth/sesión (port-forward only); el único `POST /ui/*` es discovery (form-urlencoded); `SECURITY` blocking exige validación de entrada.

A) **Sin cookies/sesiones/tokens CSRF** (no hay sesión que proteger; riesgo residual documentado para U10) + **validación estricta de parámetros** en handlers (`date` `YYYY-MM-DD`, `page ≥ 1`, `host` con forma de IP/hostname, `format ∈ {md,pdf}`) reutilizando los errores 400/422 de U2 *(recomendado)*

B) A + token CSRF dummy en el form de discovery (defensa en profundidad aunque no haya sesión)

C) Solo validación de params, sin documentar el riesgo residual de CSRF

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Degradación ante API loopback caída (Availability)

Contexto: FD BR-U3-31 fija página 502 sin traceback; `foundation.retry` existe (P3 U1) pero U2 decidió **sin retry interno** (REL-03: el dueño del fallo responde rápido).

A) **Fail-fast sin retry** en `GuiClient` (timeout 30 s configurable, 1 intento) ⇒ 502 "Core API no disponible"; el polling HTMX de discovery aplica backoff natural (2–5 s) y se detiene tras N fallos *(recomendado)*

B) 1 reintento con backoff corto (`foundation.retry`) antes de rendir la página

C) Página en blanco/500 genérico sin degradación diseñada

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Gate de cobertura para `gui/` (Maintainability)

Contexto: U1 y U2 fijan ≥70% por paquete (TS-06/TS-U2-MNT-02); la lógica de U3 es view models + reporte (plantillas = templates Jinja, no Python).

A) **≥70% en `src/sentinel/gui/`** en el job `test` de CI (mismo bar; `--cov=sentinel.gui`), heredando ruff/mypy *(recomendado)*

B) 60% (más plantillas, menos rama Python)

C) Sin gate propio (solo el total `--cov=sentinel`)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Estrategia de tests de UI (Tech Stack / Testing)

Contexto: los AC usan `curl | grep -c 'data-asset-row'` y `pytest tests/integration/test_gui_* -k …`; TS-U2-04 usa TestClient sin servidor vivo; no se quiere dependencia pesada de browsers.

A) **TestClient + assertions sobre el HTML** (contención de substrings/regex: `data-asset-row`, badges, `sin datos`) + tests unitarios de view models y builders de secciones; `GuiClient` inyectable con `httpx.MockTransport` para los handlers *(recomendado)*

B) A + parser HTML (`selectolax`/`lxml`) para assertions estructurales

C) Tests solo de handlers con mocks (HTML real nunca se verifica)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 9 — Aplicabilidad de PBT (NFR-TECH-03)

Contexto: NFR-TECH-03 **exige** PBT solo para Nmap XML, flow normalization y baseline (ninguno en U3); U1/U2 ya lo cumplen.

A) **Sin PBT en U3**: el alcance fijado no toca la GUI; la propiedad "mismo rango ⇒ mismas secciones" se cubre con `test_report_determinism.py` (integración) *(recomendado)*

B) PBT adicional propio (p. ej. propiedades de paginación `offset/limit/pages` o de las secciones del reporte)

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 10 — Logging y métricas de la GUI (Maintainability / Operability)

Contexto: `foundation.logging` (JSON) es el logger de U1/U2; el middleware `ApiRequestCounter` de U2 ya cuenta **todas** las respuestas de 8080 (incluye `/ui/*`) hacia `api_requests_total`; el catálogo `METRIC_FAMILIES` de U1 es fijo (U7/U8 dependen de él).

A) Handlers loguean con `get_logger("…")` / `component=gui` en el mismo JSON; **sin familias de métricas nuevas** (los `/ui/*` ya aparecen en `api_requests_total`) *(recomendado)*

B) A + familia nueva `sentinel_gui_page_render_seconds` (rompe el catálogo fijo → requiere cambiar U1/U7)

C) Sin logging propio en handlers (solo los accesos del servidor)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 11 — Responsive y legibilidad en laptop (Usability / NFR-TECH-04)

Contexto: NFR-TECH-04 exige "responsive and readable on a laptop for the defense demo"; Tailwind/DaisyUI ya fijados; sin build step.

A) Layout con breakpoints Tailwind `md:`/`lg:` (target laptop ≥1024 px), tablas con `overflow-x-auto`, tipografía/base de DaisyUI, verificación **manual** en la demo (sin framework de browser) *(recomendado)*

B) A + test automatizado de viewport con Playwright (añade browser a CI, pesado para lab)

C) Desktop-only fijo sin breakpoints

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 12 — Estados vacíos y de carga (Usability)

Contexto: services.md §4 prohíbe presentar vacíos como fallas ("sin datos" ≠ "red sin activos"); FR-GUI-05 exige distinguir red sin activos de falla de telemetría.

A) **Estados vacíos explícitos por vista** con mensaje + acción sugerida (inventario: "sin activos — dispara discovery"; timeline: "sin eventos en el rango"; tráfico: "sin datos"; reporte: secciones con `sin datos`); loading solo en el polling de discovery (badge `running`) *(recomendado)*

B) Tablas vacías sin mensaje (estilo crudo)

C) Skeleton screens completos con HTMX en todas las vistas

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Artefactos obligatorios (tras aprobación de respuestas)

| Artefacto | Contenido |
|---|---|
| `construction/u3-gui/nfr-requirements/nfr-requirements.md` | NFR-U3-* por categoría (PERF, SCAL, AVAIL, SEC, MNT, TECH, USAB) con origen (plan Q# / FD BR# / requirements NFR#) y verificación |
| `construction/u3-gui/nfr-requirements/tech-stack-decisions.md` | TS-U3-*: stack UI fijado, loopback httpx, Jinja2/HTMX/Tailwind vendorizado, WeasyPrint+markdown, TestClient+MockTransport, gate ≥70% gui/, timeout 30 s, sin PBT, sin métricas nuevas — con alternativas descartadas |

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los dos artefactos de NFR Requirements y presentaré el mensaje de completitud.

**No se genera ningún artefacto de NFR Requirements hasta completar este gate.**
