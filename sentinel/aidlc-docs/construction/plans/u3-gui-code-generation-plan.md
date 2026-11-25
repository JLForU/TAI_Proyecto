# Code Generation Plan — U3 (Operator GUI & network report)

**Fase**: CONSTRUCTION — Code Generation (Part 1: Planning)
**Fecha**: 2026-11-14
**Estado**: AWAITING_APPROVAL — plan listo; esperando aprobación explícita para generar código
**Workspace root**: `/home/jhoseph/Documents/TAI/TAI_Proyecto/sentinel` (de `aidlc-state.md`)
**Patrón**: Greenfield multi-unit (monolith) → `src/{unit-name}/` = **`src/sentinel/gui/`**, tests = **`tests/unit/gui/`** + **`tests/integration/gui/`**
**Este plan es la única fuente de verdad de Code Generation para U3.**

---

## 1. Contexto de la unidad

- **Historias**: ST-M10-01..07 (todas `implemented` en el story map; aquí se materializa el código).
  - ST-M10-01 Asset inventory view · ST-M10-02 Asset detail view · ST-M10-03 Events and alerts timeline · ST-M10-04 Trigger discovery (host individual) · ST-M10-05 System health view · ST-M10-06 Network report and export (MD/PDF) · ST-M10-07 Non-public GUI access (port-forward).
- **Diseño aprobado**: Functional Design (flujos §3.1–3.8, BR-U3-01..32), NFR Requirements (NFR-U3-*, TS-U3-01..11), NFR Design (P1–P10, componentes `GuiClient`/`validation`/`viewmodels`/`routes`/`report/*`, composición Q10=A), Infrastructure Design (ID-U3-01..09: Dockerfile, sin manifiestos nuevos, sin claves `values`).
- **Dependencias**: **U1** (`foundation.*`) y **U2** (API `/api/v1/*` en 8080) satisfechas; **U4** llega después (runner ⇒ 503 hasta entonces; allowlist/IP4 para modo lista ⇒ diferido). U3 consume la API por loopback (IP3) y **declara y sirve** `GET /api/v1/report` (C7).
- **Interfaces/contratos**: `GET /api/v1/{assets,assets/{id},events,alerts,health,export,discovery,discovery/{run_id}}` (U2) + `GET /api/v1/report` (U3, C7); rutas `/ui/*` + `/static/*` en 8080; `API_BASE="http://127.0.0.1:8080"` constante inyectable.
- **Límites**: cero acceso a SQLite/repos de U2 (solo HTTP loopback); sin auth de operador; sin flags/env nuevos (TS-U3-07); reportes efímeros; sin lista completa de scope (U4); sin secciones avanzadas de reporte.
- **Toolchain**: hereda U1/U2 (ruff, mypy, pytest+cov, TestClient, `MockTransport`); añade `jinja2`, `markdown`, `weasyprint` (pines exactos, TS-U3-02); gates: total `--cov=sentinel ≥70` **+** `coverage report --include='*/gui/*' --fail-under=70` (P8/Q7).

---

## 2. Pasos de generación (numerados, checkbox)

- [x] **Step 1 — Project structure setup**
  Crear `src/sentinel/gui/__init__.py`, módulos `client.py`, `validation.py`, `viewmodels.py`, `routes.py`, `templates.py`, `errors.py`, paquete `report/` (`__init__.py`, `service.py`, `sections.py`, `pdf.py`), dirs `templates/` y `static/{css,js}/`; `tests/unit/gui/__init__.py`, `tests/integration/gui/__init__.py`. Añadir a `requirements.txt` (pines exactos): `jinja2`, `markdown`, `weasyprint`.

- [x] **Step 2 — Validación de params (SEC-02, P6, Q5=NFR=A)**
  Crear `src/sentinel/gui/validation.py`: parsers puros `parse_date_range(from_, to)` (exigidos, `YYYY-MM-DD`, from≤to), `parse_page(page)` (≥1), `parse_format(fmt)` (`md` default | `pdf`), `parse_host(host)` (forma IP/hostname) → valor o `foundation.errors.ValidationError` ⇒ 400.

- [x] **Step 3 — View models (USAB, BR-U3-17/19/21, FD §3)**
  Crear `src/sentinel/gui/viewmodels.py`: `AssetRowVM` (summary + os/provenance/source desde detail), `AssetDetailVM` (obs/events/tráfico/ARP agrupados por source/kind), `TimelineEntryVM` (kind=event|alert, badge firing/resolved), `HealthVM`, `DiscoveryRunVM` (poll_state: active/backoff/stopped), `PageVM`, `ReportVM`, `ErrorVM`; `from_api`/constructores puros desde schemas Pydantic de U2.

- [x] **Step 4 — Errores de la GUI (P10, Q12=NFR=A, FD §5)**
  Crear `src/sentinel/gui/errors.py`: `CoreUnavailableError`, `render_error(request, status, title, detail, code)` → plantilla `error.html`, `core_unavailable_handler` → **502** `{"detail","code":"core_unavailable"}` + página (sin traceback); log vía `foundation.get_logger(component="gui")`.

- [x] **Step 5 — GuiClient (P7/P10, Q6=NFR=A, TS-U3-09)**
  Crear `src/sentinel/gui/client.py`: constante `API_BASE="http://127.0.0.1:8080"`; `GuiClient` con `httpx.Client(base_url, timeout=10s)`; métodos `get_assets/get_asset/get_events/get_alerts/get_health/post_discovery/get_discovery_run/get_report`; excepciones de red/timeout/5xx ⇒ `CoreUnavailableError` (sin retry, AVAIL-01).

- [x] **Step 6 — Unit tests: validation + viewmodels + client (MNT-02, P7)**
  `tests/unit/gui/test_validation.py` (bordes de cada parser ⇒ `ValidationError`), `test_viewmodels.py` (conversión desde payloads de fixtures U2), `test_client.py` (`MockTransport`: happy path, timeout ⇒ `CoreUnavailableError`, base_url inyectada).

- [x] **Step 7 — Entorno Jinja + base + static (P3, TECH-03, Q3/Q11=NFR=A, BR-U3-27/28)**
  Crear `src/sentinel/gui/templates.py` (`get_templates()`: Environment único, `auto_reload=False`), `templates/base.html` (nav: Inventario/Eventos/Alertas/Salud/Discovery/Reporte/Export, `{% autoescape %}` ON, `{% block %}`), `static/css/styles.css`, `static/js/discovery.js` (polling con backoff P1), vendorizar `static/js/htmx.min.js` (descarga oficial una vez; **sin red ⇒ D-\*** con JS vanilla equivalente), favicon. CSS: vendorizar build de Tailwind/DaisyUI pre-generado si hay red; si no, CSS propio minimalista cubriendo las clases usadas (**D-\*** registrado).

- [x] **Step 8 — Vista de inventario (ST-M10-01, FD §3.1)**
  `gui/routes.py`: `GET /ui/assets?page&status` → `limit=100&offset=(page-1)*100` → N+1 `get_asset` por fila (≤100) → `AssetRowVM[]` + `PageVM` (pages=ceil(total/100)) → `assets.html` con estados vacíos; `data-asset-row` por fila.

- [x] **Step 9 — Vista de detalle (ST-M10-02, FD §3.2)**
  `GET /ui/assets/{asset_id}` → `AssetDetailVM` con secciones Observaciones (≤200), Eventos (≤100), Tráfico (aggregate `source=traffic` o "sin datos"), ARP (`source=arp`); 404 ⇒ página de error de la GUI.

- [x] **Step 10 — Timeline + alertas (ST-M10-03, FD §3.3, Q5=A)**
  `GET /ui/events?asset_id&severity&rule&from&to&page`: fetch `get_events` (server-side) + `get_alerts` (rango) con filtrado local de asset/rule/severity sobre alertas → merge `occurred_at/fired_at DESC` → `TimelineEntryVM`; `GET /ui/alerts` = solo alertas. Badges firing/resolved.

- [x] **Step 11 — Salud + discovery (ST-M10-04/05, FD §3.4/3.5, P1)**
  `GET /ui/health` (badges sensor caído; nunca "red sin activos" por inventario vacío); `POST /ui/discovery` (form `host`) → `post_discovery({"hosts":[host],"timeout_seconds":30})` → 202 ⇒ parcial con `hx-get /api/v1/discovery/{run_id}` cada 2 s (backoff 2→4→8→16, parada a los 5 fallos, `discovery.js`); 400 scope_violation/409/503 ⇒ mensajes FD §5.

- [x] **Step 12 — Section builders + esc() (ST-M10-06, P2/P5, FD §3.6/§6)**
  Crear `src/sentinel/gui/report/sections.py`: `SECTION_ORDER` (5 `##` fijos), `build_inventory_section`, `build_changes_section` (tipos ∈ {asset_first_seen, asset_missing, port_service_changed, arp_mapping_changed}), `build_top_talkers_section` (aggregate traffic o "sin datos"), `build_alerts_section`, `build_evidence_range_section` (rango + conteos de fuentes), **`esc()`** aplicado a todo dato dinámico; builders **puros**.

- [x] **Step 13 — ReportService + PDF + rutas (ST-M10-06, C7, P2, Q9=NFR=A)**
  Crear `gui/report/service.py` (`generate(from,to,client)`: fetch secuencial assets→events→alerts→detalles → builders → `ReportArtifact{md, generated_at}`; fail-fast 502; "Generated at" **fuera** de las secciones `##`) y `gui/report/pdf.py` (`render_pdf`: template HTML intermedio autoescape → WeasyPrint, import perezoso). Rutas: `GET /ui/report` (FileResponse attachment, `format` md|pdf) + `GET /api/v1/report` (router API de U3, contrato C7); determinismo byte-idéntico.

- [x] **Step 14 — Montaje en la app + página de error (Q10/Q12=NFR=A, ID-U3-01)**
  Editar `src/sentinel/core/api/app.py`: bloque `try/except ImportError` en `create_app` → `include_router(gui.routes)` + `include_router(gui.api_routes)` (`/api/v1/report`), `mount("/static", StaticFiles)`, `app.state.gui_config=(api_base, http_client)`, handler `CoreUnavailableError`→502; parámetros `api_base`/`http_client` en la firma. Crear `templates/error.html` (usado por `render_error`).

- [x] **Step 15 — Unit tests de vistas (MNT-02, USAB-02, BR-U3-17/31)**
  `tests/unit/gui/test_routes_*.py` con `TestClient(create_app(..., http_client=MockTransport))`: 200+substring por vista, estados vacíos, paginación, 404 detalle, filtros timeline, form discovery 202/400/409/503, 502 con `ConnectError`, sin traceback, params inválidos ⇒ 400.

- [x] **Step 16 — Unit tests de reporte (PERF-02, SEC-01, determinismo)**
  `tests/unit/gui/test_report.py`: 5 secciones en orden + "Generated at" fuera; determinismo (2 ejecuciones ⇒ idénticas); fallo en la 3ª llamada ⇒ 502 sin MD parcial; `esc()` por campo (`<script>`, `*`, `_`, …); `format=pdf` (skip condicional si WeasyPrint no puede inicializar en el host — **D-\*** si falta; validación real en Build & Test con imagen).

- [x] **Step 17 — Integration tests (tests/integration/gui/, AVAIL-02)**
  `test_gui_over_core.py` (app completa U2+U3 con SQLite temporal + fixtures: vistas con datos reales, reporte de rango con datos, export enlace); `test_gui_api_down.py` (Core detenido ⇒ shell de la GUI sirve y vistas ⇒ 502); `test_empty_states.py` (DB vacía ⇒ "sin datos" en inventario/timeline).

- [x] **Step 18 — Static/BR checks (BR-U3-27, NFR-OPS-04)**
  Tests: archivos static presentes bajo `gui/static/`; templates sin `<script src="http…cdn` ni URLs externas; `auto_reload is False`; identidad del Environment entre renders.

- [x] **Step 19 — CI: doble gate de cobertura (P8/Q7=NFR=A, TS-U3-08)**
  Editar `.github/workflows/ci.yml`: añadir paso tras pytest `coverage report --include='*/gui/*' --fail-under=70` (mismo `.coverage`); mantener gate total ≥70 y mypy.

- [x] **Step 20 — Dockerfile (ID-U3-01, TS-U3-02/03)**
  Editar `Dockerfile`: `apk add --no-cache pango cairo gdk-pixbuf fontconfig ttf-dejavu`; `pip install` de los 3 pines nuevos; verificar `COPY src/` incluye `gui/static` y `gui/templates`; sin cambios de `CMD`.

- [x] **Step 21 — README + docs**
  Añadir sección GUI en `README.md`: run local (`uvicorn sentinel.core.api.app:app`), rutas `/ui/*`, curl del reporte (`-o report.md`), nota de port-forward (ST-M10-07) y de que `GET /api/v1/report` es servido por U3.

- [x] **Step 22 — Validación local**
  Ejecutar: `ruff check .` · `ruff format --check .` · `mypy src/sentinel` · `pytest tests/unit tests/property tests/integration -q --cov=sentinel --cov-fail-under=70` + `coverage report --include='*/gui/*' --fail-under=70` — todo en verde.

- [x] **Step 23 — Resumen de generación**
  Crear `aidlc-docs/construction/u3-gui/code/code-generation-summary.md` (archivos creados/modificados, desviaciones D-\* — p.ej. CSS/htmx sin red o PDF skip en host —, cobertura total y de `gui/`, historias ST-M10-01..07 `[x]`, estado del repo).

---

## 3. Historias y trazabilidad

| Historia | Steps | Verificación principal | Estado |
|---|---|---|---|
| ST-M10-01 Asset inventory view | 8, 15, 17 | 200 + filas + paginación + empty state | [x] |
| ST-M10-02 Asset detail view | 9, 15, 17 | 4 secciones + "sin datos" + 404 | [x] |
| ST-M10-03 Events and alerts timeline | 10, 15, 17 | merge ordenado + filtros + badges | [x] |
| ST-M10-04 Trigger discovery | 11, 15 | form ⇒ 202 + polling/backoff; 400/409/503 | [x] |
| ST-M10-05 System health view | 11, 15, 17 | badges + sensor caído | [x] |
| ST-M10-06 Network report and export | 12, 13, 16, 17 | 5 secciones + determinismo + 502 + escape + PDF | [x] |
| ST-M10-07 Non-public GUI access | 21 | doc port-forward + sin auth (FR-GUI-07) | [x] |

*Estado `[x]` = código + tests generados y en verde en la validación local (Step 22). Los AC con curl/demo se confirman en Build and Test.*

---

## 4. Fuera de alcance de este plan

- Modo "lista completa" del trigger y allowlist real (U4, IP4/ST-M1-01); `scope_violation` real sigue sin dispararse.
- Auth de operador, TLS, LoadBalancer/NodePort (prohibidos; U9/U10).
- Lectura de K8s para salud; secciones avanzadas de reporte; estilo corporativo de PDF.
- `helm template`/demo AC (Build and Test, chart de U9); sustitución de `collect()` (U7); alerting (U8).

---

## 5. Gate de aprobación

1. Revisa los 23 steps y la trazabilidad.
2. Responde **`Aprobado`** (o pide cambios) para iniciar Part 2: Generation.
3. Cada step se marcará `[x]` al completarse; desviaciones se registrarán como `D-*` en el resumen.

**No se genera ningún código hasta esta aprobación.**
