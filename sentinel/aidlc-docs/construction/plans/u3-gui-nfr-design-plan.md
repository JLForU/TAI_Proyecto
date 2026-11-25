# NFR Design Plan — U3 (Operator GUI & network report)

**Fase**: CONSTRUCTION — NFR Design (Parte 1: Planning)
**Fecha**: 2026-11-14
**Estado**: ARTIFACTS_GENERATED — Q1–Q12 todas A (2026-11-14); artefactos generados; pendiente de aprobación
**Unidad**: U3 — `src/sentinel/gui/`
**Entradas**: `construction/u3-gui/nfr-requirements/*` (aprobado 2026-11-14T15:35:00Z: NFR-U3-PERF/SCAL/AVAIL/SEC/MNT/TECH/USAB, TS-U3-01..11), Functional Design de U3 (aprobado), `nfr-design` U2 (patrones de referencia) y U1 (`foundation`).

---

## 1. Contexto del assessment (Step 1 — analizado)

Cómo incorporar los NFR aprobados de U3 en **patrones de diseño y componentes lógicos** concretos: cómo se comporta la GUI ante la API loopback caída, cómo se escapan los datos de red en vistas y reporte, cómo se inyecta/testea el cliente HTTP, cómo se monta el módulo `gui/` en la app sin romper la frontera con U2, y cómo se verifican los gates de cobertura en CI.

Ya decidido en etapas previas (NO se pregunta): fail-fast 502 sin retry (NFR-U3-AVAIL-01), N+1 secuencial ≤100/pág sin caché (SCAL-01), timeout 30 s del reporte (PERF-02), autoescape ON + escape en builders (SEC-01), sin sesión/CSRF + validación estricta de params (SEC-02), ≥70% `gui/` (MNT-01), TestClient + substring + `MockTransport` (MNT-02), sin PBT (MNT-03), sin familias nuevas (MNT-04), stack fijado + WeasyPrint + static vendorizado (TECH-01..03), responsive + estados vacíos (USAB-01/02), `API_BASE` constante (TS-U3-09).

**Categorías evaluadas**:

| Categoría | Aplica a U3 | Tratamiento |
|---|---|---|
| Resilience Patterns | Sí | Q1 (backoff del polling), Q2 (integridad del reporte ante fallo) |
| Scalability Patterns | Cerrado | **Sin pregunta**: SCAL-01 (N+1 acotado) ya fijado en NFR Req |
| Performance Patterns | Sí | Q3 (entorno Jinja: auto_reload/caching) |
| Security Patterns | Sí | Q4 (escapado MD/PDF), Q5 (validación de params compartida) |
| Availability | Cerrado | **Sin pregunta**: fail-fast 502 + polling ya fijados (AVAIL-01) |
| Maintainability Patterns | Sí | Q6 (punto de inyección del GuiClient), Q7 (gate de cobertura en CI) |
| Logical Components | Sí | Q8 (capa GUI), Q9 (estructura ReportService), Q10 (montaje en la app), Q11 (static), Q12 (página de error/502) |

---

## 2. Checklist del plan

- [x] Analizar NFR requirements aprobados
- [x] Generar preguntas de diseño NFR (Q1–Q12)
- [x] Recoger respuestas a los `[Answer]:` (todas A, 2026-11-14)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; sin ambigüedades; sin seguimientos
- [x] Generar `nfr-design/nfr-design-patterns.md`
- [x] Generar `nfr-design/logical-components.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Backoff del polling de discovery (Resilience Patterns)

Contexto: NFR-U3-AVAIL-01 exige backoff 2–5 s y detención tras N fallos; el run se consulta con `hx-get` a `GET /api/v1/discovery/{run_id}`.

A) Intervalo **fijo de 2 s** mientras `running`; **backoff exponencial 2→4→8→16 s (tope 30 s)** ante errores de red/5xx; **detención tras 5 fallos consecutivos** con mensaje "estado no disponible" y enlace de reintento manual *(recomendado)*

B) Intervalo fijo 2 s siempre (sin backoff; más simple, más ruido cuando la API cae)

C) Polling continuo indefinido con reintento manual solo en el enlace

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 2 — Integridad del reporte ante fallo parcial (Resilience / Reliability)

Contexto: `generate()` hace llamadas múltiples (activos, eventos, alertas, detalles); PERF-02 fija timeout 30 s ⇒ 502; NFR-OPS-05 exige determinismo; entregar un MD parcial como si fuera completo sería silenciosamente engañoso.

A) **Fail-fast total**: cualquier error/timeout durante `generate()` ⇒ **502** con detail (nunca un reporte parcial); la MD se construye **en memoria** (strings; envolvente lab ≤50 activos < 1 MB) y se emite solo si las 5 secciones se completaron *(recomendado)*

B) Secciones parciales con aviso `## WARNING: datos incompletos` (entrega algo, pero rompe la promesa de completitud)

C) Reintentar por sección antes de fallar (más latencia, complejidad)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 3 — Entorno Jinja (Performance Patterns)

Contexto: templates baked en imagen (TECH-03); server-rendered en cada request; lab reinicia con cada deploy.

A) **Un `Jinja2Templates`/Environment por proceso** con `auto_reload=False` (los templates no cambian sin redeploy) y `cache_size` por defecto — compilación una sola vez, renders subsequentes desde caché *(recomendado)*

B) `auto_reload=True` siempre (más cómodo en dev, recompila en cada request si cambia el archivo)

C) Precompilar templates a Python en el build de la imagen (más piezas, beneficio nulo a escala lab)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 4 — Escapado en los builders del reporte (Security Patterns)

Contexto: SEC-01 exige escape de datos crudos en MD y en el paso a HTML/PDF; los datos de red (hostnames, details de eventos, payloads) pueden contener `<`, `*`, `_`, `#`.

A) Función única **`esc()`** en `gui/report/sections.py` aplicada a **todo** campo dinámico antes de insertarlo en la MD (escape de caracteres Markdown/HTML significativos); el HTML intermedio de WeasyPrint se genera con autoescape del template *(recomendado)*

B) Solo autoescape del HTML de PDF (la MD crudo quedaría con markup sin escapar — rompe SEC-01 para `format=md`)

C) Sanitización agresiva (strip de no-ASCII/recorte de longitudes) en vez de escape

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 5 — Validación de parámetros compartida (Security Patterns)

Contexto: SEC-02 exige validación estricta (`date` `YYYY-MM-DD`, `page ≥ 1`, `host` forma IP/hostname, `format ∈ {md,pdf}`) con errores 400/422 uniformes.

A) Módulo **`gui/validation.py`** con parsers puros reutilizables (`parse_date_range`, `parse_page`, `parse_format`, `parse_host`) que devuelven el valor o lanzan `foundation.errors.ValidationError` ⇒ handler 400 de U2 (misma forma de error que la API) *(recomendado)*

B) Validación inline en cada handler (código duplicado, tests repetidos)

C) Modelos Pydantic para query params (más ceremonia para parámetros simples de URL)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 6 — Punto de inyección del `GuiClient` (Maintainability / Testability)

Contexto: MNT-02 pide `httpx.MockTransport` en tests; U2 ya usa el patrón de parámetros inyectables en `create_app` (`runner`, `metrics_port`).

A) `create_app(..., api_base: str = API_BASE, http_client: httpx.Client | None = None)` → `app.state.gui_client`; los handlers obtienen el client vía **Depends** (`get_gui_client`); tests pasan `http_client=httpx.Client(transport=MockTransport(...))` *(recomendado)*

B) Singleton de módulo (`gui/client.py` con `client = httpx.Client(...)`) — testeable solo con monkeypatch

C) Middleware que adjunta el client al `request.state` (indirecto, difícil de tipar)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 7 — Gate de cobertura de `gui/` en CI (Maintainability Patterns)

Contexto: MNT-01 exige ≥70% en `src/sentinel/gui/`; MNT/TS-U2 fija el gate total ≥70% `--cov=sentinel`; `pytest-cov` solo admite **un** `--cov-fail-under` por invocación; TS-U3-08 mantiene ambos gates.

A) **Una sola invocación** de pytest con `--cov=sentinel --cov-fail-under=70` + paso adicional en el job `test`: `coverage report --include='*/gui/*' --fail-under=70` sobre el **mismo** `.coverage` (cero runtime duplicado, dos gates) *(recomendado)*

B) Segunda invocación de pytest solo con tests de `gui/` y su propio `--cov-fail-under=70` (duplica tiempo de CI)

C) Solo el gate total del paquete (no cumple MNT-01 literal sobre `gui/`)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 8 — Composición de la capa GUI (Logical Components)

Contexto: component-methods §10 define handlers; U2 usa routers + inyección (NFR-U2-…, FD Q7 de U2); TS-U3-02 fija loopback.

A) **Router `gui/routes.py`** (`APIRouter` con prefijo `/ui`) + dependencias (`get_gui_client`, `get_templates`) + **view models** en `gui/viewmodels.py` + **validación** en `gui/validation.py`; los handlers solo: validar ⇒ llamar client ⇒ construir VM ⇒ renderizar *(recomendado)*

B) Handlers de bajo nivel estilo funciones sueltas con decoradores (menos estructura para 8 vistas)

C) Un micro-framework propio de vistas (overengineering)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 9 — Estructura del ReportService (Logical Components)

Contexto: component-methods §6 (`generate` + 4 builders + `render_pdf`); Q4=A fija `esc()`; TECH-05 fija WeasyPrint; determinismo (NFR-OPS-05).

A) Paquete **`gui/report/`**: `service.py` (`generate` orquesta: fetch vía client → builders → artefacto), `sections.py` (builders puros + `esc()` + `SECTION_ORDER`), `pdf.py` (`render_pdf`: MD → template HTML → WeasyPrint) *(recomendado)*

B) Un solo archivo `gui/report.py` con todo (500+ líneas, peor testeable por unidad)

C) Secciones como templates Jinja `.md` (mezcla paradigmas; el escape queda menos explícito)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 10 — Montaje del módulo GUI en la app (Logical Components / frontera U2↔U3)

Contexto: la app se ensambla en `core/api/app.py` (U2); U3 no debe romper su frontera; los impactos en artefactos heredados ya están declarados en `tech-stack-decisions.md` §3 (patrón: ediciones acotadas documentadas, como CI/Dockerfile); el entrypoint `python -m sentinel.core` (CMD de la imagen) debe servir la GUI sin cambios.

A) **Edición acotada de `core/api/app.py`**: dentro de `create_app`, bloque `try/except ImportError` que importa `sentinel.gui.routes` / `gui.report` y añade router `/ui`, monta `/static`, y registra el handler 502 de `CoreUnavailableError`; si `gui` no está instalado, la app funciona solo-API *(recomendado)*

B) Entrypoint envuelto: nuevo `sentinel.gui.app:app` que monta la app de U2 — exige cambiar `__main__.py` y el `CMD` del Dockerfile (más archivos heredados tocados)

C) Descubrimiento por entry-points/plugins de Python (ceremonia innecesaria en un monolito)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 11 — Servido de static assets (Logical Components)

Contexto: TECH-03 fija static vendorizado en `gui/static/`; NFR-OPS-04 los embebe en la imagen; rutas `/static/*`.

A) **`app.mount("/static", StaticFiles(directory=…))`** resolviendo el directorio con `Path(__file__).parent / "static"` (robusto dentro de la imagen y en local) en el mismo bloque de montaje de Q10 *(recomendado)*

B) Rutas `GET /static/{path}` manuales en el router (reinventa `StaticFiles`)

C) Inlining de CSS/JS en `base.html` (sin requests separados, pero pierde caché del navegador y engorda cada HTML)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 12 — Página de error y handler 502 (Logical Components)

Contexto: FD §5 fija tabla de errores con página propia; BR-U3-31 exige 502 sin traceback; U2 ya registra handlers en `core/api/errors.py` (404/409/500/…).

A) Plantilla única **`gui/templates/error.html`** + helper `render_error(request, status, title, detail, code)`; U3 registra **además** el handler de `CoreUnavailableError` → **502** (y reutiliza los demás handlers de U2 para 404/409/422 en respuestas HTML cuando el path es `/ui/*`) *(recomendado)*

B) Mostrar el JSON de error de U2 tal cual en la página (feo para el operador, filtra forma interna)

C) Cada handler renderiza su propia página de error (plantillas duplicadas)

D) Other (describe después de `[Answer]:`)

[Answer]: A
---

## 4. Artefactos obligatorios (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `construction/u3-gui/nfr-design/nfr-design-patterns.md` | Patrones aplicados por NFR (resilience, performance, security, maintainability) con mecanismo concreto, dónde vive y verificación + mapa NFR→patrón→verificación |
| `construction/u3-gui/nfr-design/logical-components.md` | Componentes lógicos de U3 (GuiClient, router, viewmodels, validation, report package, templates/static, error helper) con responsabilidades, relaciones, layering y bordes con U2/U4 + composición de la app |

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los dos artefactos de NFR Design y presentaré el mensaje de completitud.

**No se genera ningún artefacto de NFR Design hasta completar este gate.**
