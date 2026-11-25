# Tech Stack Decisions — U3 (Operator GUI & network report)

**Fase**: CONSTRUCTION — NFR Requirements
**Fecha**: 2026-11-14
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U3 — `src/sentinel/gui/`
**Nota**: decisiones de la **unidad**; hereda TS-01..11 de U1, TS-U2-01..10 de U2 y el stack global de `requirements.md` §4. El stack UI principal está **fijado por NFR-TECH-04** (no se preguntó); aquí se confirman los pins y las decisiones propias de U3.

---

## 1. Tabla de decisiones

| # | Decisión | Elegida | Alternativas descartadas | Justificación | Origen |
|---|---|---|---|---|---|
| TS-U3-01 | Stack de UI | **FastAPI + Jinja2 + HTMX + Tailwind/DaisyUI**, server-rendered, sin build JS | SPA React/Vue/Svelte (build step, estado cliente); Flask+templates (rompe stack FastAPI ya presente); Streamlit/Gradio (no encaja con rutas `/ui` embebidas) | Fijado por NFR-TECH-04; server-rendered = cero pipeline JS | NFR-TECH-04 |
| TS-U3-02 | Consumo de datos | **`httpx` síncrono** → loopback `API_BASE=http://127.0.0.1:8080` | Invocar `QueryService` in-process (rompe "consumes only the Core HTTP API", requirements §6.5); `requests` (ya no está en deps; httpx cubierto por U2) | Requisito literal §6.5 + testeabilidad con `MockTransport` | FD Q2=A |
| TS-U3-03 | Templates | **Jinja2** con **autoescape ON explícito** para `*.html` | Mako/Cheetah (menos integración Starlette); autoescape default implícito (frágil ante cambio de extensión) | Integración nativa Starlette + NFR-U3-SEC-01 | NFR-TECH-04, Plan Q4=A |
| TS-U3-04 | Static assets | **Vendorizados en repo**: `htmx.min.js` + CSS Tailwind/DaisyUI pre-generado en `gui/static/` | CDN (demo depende de red); Tailwind CLI en CI (añade build step a la imagen) | NFR-OPS-04 "baked into the image" + lab sin Internet garantizado | FD Q12=A |
| TS-U3-05 | PDF | **WeasyPrint** (MD → HTML → PDF) + `markdown`; paquetes de sistema `pango`/`cairo`/`gdk-pixbuf` en el Dockerfile | `reportlab` (sin HTML, peor tipografía); `fpdf2` (más limitado); Markdown-only (rompe FR-GUI-06) | Lo anticipa `tech-stack-decisions.md` de U1 ("weasyprint/PDF pertenece a U3"); calidad para la demo | FD Q11=A (corregido) |
| TS-U3-06 | Timeout/reintento HTTP | **30 s, 1 intento, fail-fast** ⇒ 502 | `foundation.retry` en la GUI (enmascara fallos del Core, añade latencia al operador); timeout default httpx 5 s (insuficiente para reporte) | NFR-U3-AVAIL-01, coherente con NFR-U2-REL-03 (sin retry del dueño) | Plan Q3/Q6=A |
| TS-U3-07 | Tests de UI | **TestClient + assertions de substring/regex** + `httpx.MockTransport` para `GuiClient` | Playwright/Cypress (browser en CI, pesado para lab); `selectolax`/`lxml` (dep extra sin necesidad); solo mocks (no verifica HTML) | Los AC ya usan `grep -c`/`-k`; TS-U2-04 sin servidor vivo | Plan Q8=A |
| TS-U3-08 | Gate de cobertura | **≥ 70% en `src/sentinel/gui/`** (`--cov=sentinel.gui --cov-fail-under=70`) | 60% (baja la barra sin razón); solo total del paquete (diluye el gate) | Mismo bar que TS-06 y TS-U2-MNT-02 | Plan Q7=A |
| TS-U3-09 | Configuración | **Sin claves nuevas**: `API_BASE` constante inyectable en tests | `SENTINEL_API_BASE` (GUI y Core siempre en el mismo pod/proceso); claves de reporte (rango siempre explícito) | BR-06 + FD Q13=A | FD Q13=A |
| TS-U3-10 | Logging y métricas | **`foundation.logging`** (`component=gui`) + middleware `ApiRequestCounter` heredado; **sin familias nuevas** | Familia nueva de render time (rompe catálogo `METRIC_FAMILIES` de U1 → afecta U7/U8); sin logging de handlers (inoperable) | BR-20..22 U1, NFR-U3-MNT-04 | Plan Q10=A |
| TS-U3-11 | PBT | **No aplica en U3** | PBT de paginación/secciones (no exigido por NFR-TECH-03; determinismo cubierto por test de integración) | Alcance de PBT fijado en NFR-TECH-03 | Plan Q9=A |

---

## 2. Dependencias que U3 añade (pines exactos, P6)

| Paquete | Uso | Nota |
|---|---|---|
| `jinja2` | Templates de vistas | ya transitivo de Starlette; se fija explícito en `requirements.txt` |
| `markdown` | MD del reporte (secciones → HTML para PDF y para MD crudo) | librería mínima, pure-Python |
| `weasyprint` | PDF (con `pango`/`cairo`/`gdk-pixbuf` apk en Dockerfile) | única dependencia con requisitos de sistema |
| `httpx` | Loopback client | ya presente (U2) |

*No se añaden*: parser HTML, browser automation, JS build tools, frameworks CSS externos (el CSS va vendorizado).

---

## 3. Impacto en artefactos heredados

| Artefacto | Cambio requerido por U3 |
|---|---|
| `requirements.txt` | + `jinja2`, `markdown`, `weasyprint` (pines) |
| `Dockerfile` (U1) | + `apk add pango cairo gdk-pixbuf` (runtime WeasyPrint); `COPY src/` ya incluye `gui/static` y templates |
| `.github/workflows/ci.yml` | job `test`: añadir `--cov=sentinel.gui` con `--cov-fail-under=70` (o gate conjunto, ver Code Generation) |
| `pyproject.toml` | sin cambios (ruff/mypy/pytest ya cubren `src/`) |

---

## 4. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
