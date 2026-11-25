# NFR Design Patterns — U3 (Operator GUI & network report)

**Fase**: CONSTRUCTION — NFR Design (Parte 2: Generation)
**Fecha**: 2026-11-14
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U3 — `src/sentinel/gui/`
**Decisiones (plan Q1–Q12)**: **A en todas** — backoff exponencial 2→16 s con parada a los 5 fallos; reporte fail-fast 502 + MD en memoria; entorno Jinja con `auto_reload=False`; `esc()` única en builders; `gui/validation.py` con parsers puros; `GuiClient` inyectado vía `create_app` + Depends; gate doble de cobertura en CI; router `/ui` + viewmodels; paquete `gui/report/` en 3 módulos; edición acotada de `core/api/app.py`; `StaticFiles` montado; `error.html` + helper + handler 502.
**Entradas**: `nfr-requirements/*` (NFR-U3-*, TS-U3-01..11), Functional Design de U3 (BR-U3-01..32), `foundation` (errors, logging), U2 (`core/api/errors.py`).

---

## 1. Patrones de Resilience

### P1 — Backoff del polling de discovery (→ NFR-U3-AVAIL-01, Q1=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | El cliente HTMX de `/ui/discovery` consulta `GET /api/v1/discovery/{run_id}`: **2 s fijo** mientras `status=running`; ante error de red/5xx ⇒ backoff exponencial **2→4→8→16 s (tope 30 s)**; **5 fallos consecutivos** ⇒ se detiene el polling y la vista muestra "estado no disponible" + enlace de reintento manual |
| Dónde | `gui/static/` (JS del partial) + `DiscoveryRunVM` con `poll_state` |
| No hace | Sin retry del `POST /ui/discovery` (BR-U3-07: el trigger es único; el operador reintenta manualmente); sin SSE/websockets (sobrecapa) |
| Verificación | Test de VM: secuencia de 5 errores ⇒ `poll_state=stopped`; con API ok ⇒ `poll_state=active` a 2 s; grep de JS: constantes `2/4/8/16/30` y `MAX_FAILURES=5` |

### P2 — Fail-fast del reporte + construcción en memoria (→ NFR-U3-PERF-02, AVAIL-01, Q2=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `ReportService.generate()`: fetch secuencial (activos → eventos → alertas → detalles) con `httpx` timeout 30 s; **cualquier excepción/timeout ⇒ `CoreUnavailableError`/502** (nunca MD parcial); la MD se construye **en memoria** (strings) y solo se emite si las **5 secciones** (`## 1.`…`## 5.`) se completaron; `format=pdf` solo se renderiza tras emitir la MD completa |
| Por qué total | Un reporte parcial entregado como completo rompería la confianza del operador (NFR-OPS-05) y el determinismo (mismo fallo ⇒ mismo 502, no un artefacto variable) |
| No hace | Sin cache entre reportes (misma entrada ⇒ mismo fetch ⇒ determinismo verificable), sin streaming, sin reintentos por sección |
| Verificación | Test: `MockTransport` que falla la 3ª llamada ⇒ respuesta 502 y body sin `## 3.`; test happy-path ⇒ las 5 secciones presentes; test de determinismo: 2 llamadas misma entrada ⇒ bytes idénticos |

---

## 2. Patrón de Performance

### P3 — Entorno Jinja con caché de compilación (→ NFR-U3-PERF-01, Q3=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Un solo `Jinja2Templates` (o `Environment`) **por proceso**, `auto_reload=False` (los templates van baked en la imagen: TECH-03), `cache_size` por defecto ⇒ compilación única, renders desde caché |
| Dónde | `gui/templates.py` → `get_templates()` (dependencia); invocado por `Depends` |
| Por qué sin auto_reload | En lab los templates cambian solo con redeploy; `auto_reload=True` recompilaría en cada request sin ganancia |
| No hace | No precompila a Python en build (ceremonia sin beneficio a escala lab) |
| Verificación | Test: dos renders seguidos del mismo template usan el mismo `Environment` (identidad del objeto); test de que `auto_reload is False` |

### P4 — N+1 secuencial acotado (heredado de NFR-REQ, sin pregunta)

| Elemento | Diseño |
|---|---|
| Mecanismo | Los listados (`/ui/assets`, `/ui/events`) usan **una** llamada paginada (`limit ≤ 100`); el detalle enriquecido y los top talkers hacen N llamadas **secuenciales** a `/api/v1/assets/{id}` (≤ 100/página) — sin caché, sin paralelismo (NFR-U3-SCAL-01) |
| Verificación | `MockTransport` cuenta llamadas: página de 100 activos ⇒ 1 + 100 (detalle) + 100 (top) exactas, en orden secuencial |

---

## 3. Patrones de Security

### P5 — Escape único de datos dinámicos (→ NFR-U3-SEC-01, Q4=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Función **`esc()`** en `gui/report/sections.py`, aplicada a **todo** campo dinámico insertado en la MD (hostnames, IPs, details de eventos, nombres de servicio): escapa caracteres significativos de Markdown/HTML (`<`, `>`, `*`, `_`, `#`, `` ` ``, `[`, `]`); el paso MD → HTML de WeasyPrint se hace en un template con **autoescape ON** |
| Por qué en builders | `format=md` se entrega crudo al operador: sin `esc()` el contenido de red podría inyectar markup; el autoescape del HTML solo cubre el camino PDF |
| No hace | Sin sanitización agresiva (no recorta ASCII ni longitudes: los datos de red son legítimos) |
| Verificación | Test por campo: `hostname = "<script>*x*"` ⇒ en la MD aparece escapado; test PDF: `render_pdf` produce bytes sin el payload crudo |

### P6 — Validación estricta por parsers puros (→ NFR-U3-SEC-02, Q5=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `gui/validation.py`: `parse_date_range(from, to)`, `parse_page(page)`, `parse_format(fmt)`, `parse_host(host)` — puros (str → valor | `foundation.errors.ValidationError`); el handler de `ValidationError` de U2 devuelve **400** con `code` uniforme; `format` solo acepta `md|pdf`; fechas solo `YYYY-MM-DD`; `page ≥ 1` |
| Por qué no Pydantic | Los params de URL son escalares simples; Pydantic añade ceremonia sin ganar nada sobre parsers de 5 líneas testeables en aislamiento |
| Verificación | Tests unitarios por parser (bordes: fechas malformadas, `page=0`, `format=exe`, host con `../`) + test de integración: `GET /ui/events?from=31/12/2026` ⇒ 400 con forma de error de U2 |

---

## 4. Patrones de Maintainability

### P7 — Inyección del `GuiClient` (→ NFR-U3-MNT-02, Q6=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `create_app(..., api_base: str = API_BASE, http_client: httpx.Client | None = None)` ⇒ `app.state.gui_config`; dependencia `get_gui_client(request)` construye/retiene un `GuiClient` (envuelve `httpx.Client` con `base_url=api_base`, timeout 10 s); handlers lo reciben vía `Depends` |
| Tests | `http_client=httpx.Client(transport=httpx.MockTransport(handler))` inyectado en `create_app` — cero monkeypatch, mismo patrón que `runner`/`metrics_port` de U2 |
| No hace | Sin singleton de módulo (testeable solo con monkeypatch) ni middleware de `request.state` (indirecto) |
| Verificación | Test: app con `MockTransport` ⇒ handler responde con fixtures sin tocar red; test de que `api_base` llega al client (`client.base_url`) |

### P8 — Doble gate de cobertura en CI (→ NFR-U3-MNT-01, TS-U3-08, Q7=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Job `test` de `ci.yml`: **una** invocación `pytest … --cov=sentinel --cov-fail-under=70 --cov-report=term-missing` + paso adicional `coverage report --include='*/gui/*' --fail-under=70` sobre el **mismo** `.coverage` |
| Por qué | `pytest-cov` admite un solo `--cov-fail-under` por invocación; el segundo gate con `coverage report` cuesta ~0 s (sin re-ejecutar tests) y cumple MNT-01 literal sobre `gui/` |
| No hace | Sin segunda invocación de pytest (duplicaría runtime); sin bajar el gate total |
| Verificación | El paso `coverage report --include='*/gui/*' --fail-under=70` está presente en `ci.yml`; en local: `make`/comando documentado en el summary de code-gen |

### P9 — Tests sin PBT, con `foundation.logging` (heredados, sin pregunta)

| Elemento | Diseño |
|---|---|
| Mecanismo | Tests de vista con `TestClient` + aserciones de substring/estado (NFR-U3-MNT-02); **sin** Hypothesis en U3 (MNT-03: la entrada es determinista desde fixtures); logs de la GUI via `foundation.get_logger` con `component="gui"` (MNT-04: cero familias de métricas nuevas); ruff/mypy heredados del repo |
| Verificación | `grep -r hypothesis tests/gui` vacío; `grep -rn 'component.*gui' src/sentinel/gui` presente; CI lint/typecheck |

---

## 5. Patrón de Availability (heredado, cerrado sin pregunta)

### P10 — Fail-fast 502 sin estado propio (→ NFR-U3-AVAIL-01/02)

| Elemento | Diseño |
|---|---|
| Mecanismo | `GuiClient` lanza `CoreUnavailableError` ante timeout/conexión/5xx del loopback; el handler registrado en el bloque de montaje (Q10) devuelve **502** `{"detail":…, "code":"core_unavailable"}` + página `error.html`; **sin** retry, **sin** caché de GUI, **sin** sesión (la GUI no tiene estado propio que perder) |
| Verificación | Test: `MockTransport` que lanza `ConnectError` ⇒ 502 sin traceback; reinicio del Core ⇒ la GUI sigue sirviendo sus vistas (fallan al llamar, no al renderizar) |

---

## 6. Mapa NFR → Patrón → Verificación

| NFR-U3 | Patrón | Verificación principal |
|---|---|---|
| PERF-01 | P3, P4 | Identidad de Environment; conteo de llamadas con MockTransport |
| PERF-02 | P2 | Timeout 30 s ⇒ 502; test de determinismo (2 ejecuciones idénticas) |
| SCAL-01 | P4 | Conteo exacto de llamadas N+1, secuenciales, ≤100/pág |
| AVAIL-01 | P1, P2, P10 | 5 fallos ⇒ parada del polling; error ⇒ 502 total |
| AVAIL-02 | P10 | GUI sirve vistas con API caída (502 al datos, 200 al shell) |
| SEC-01 | P5 | Test de escape por campo (MD) + PDF sin payload crudo |
| SEC-02 | P6 | Tests por parser + integración 400 con forma U2 |
| SEC-03 | (infra U9/U10) | Sin sesión ⇒ sin superficie de cookie; port-forward documentado |
| SEC-04 | P10 | 502 sin traceback (misma aserción que U2) |
| MNT-01 | P8 | `coverage report --include='*/gui/*' --fail-under=70` en CI |
| MNT-02 | P7 | Test con `MockTransport` inyectado en `create_app` |
| MNT-03 | P9 | Sin Hypothesis en `tests/` de GUI |
| MNT-04 | P9 | `component="gui"` en logs; cero familias nuevas |
| MNT-05 | (heredado) | Cero código de purga (la ausencia es la decisión) |
| TECH-01..03 | (FD Q13/FQ1/FQ2) | Stack fijado en TS-U3-01..03; Dockerfile con pango/cairo |
| USAB-01 | (FD §4) | Checks manuales `md:/lg:` + screenshot en evidencia |
| USAB-02 | (FD §5) | Tests de texto de estados vacíos en cada vista |
