# Code Generation Summary — U3 (Operator GUI & network report)

**Unidad**: U3 · **Fecha**: 2026-11-16 · **Plan**: `aidlc-docs/construction/plans/u3-gui-code-generation-plan.md` (23/23 steps `[x]`)
**Traza**: ST-M10-01..07, FR-GUI-01..08, FR-EXP-02, NFR-TECH-04, NFR-OPS-04/05, NFR-U3-* · FD Q1–Q13/FQ1/FQ2 = A · NFR Req/Design/Infra = aprobados.

## 1. Archivos creados

| Área | Archivos |
|---|---|
| Paquete GUI | `src/sentinel/gui/{__init__,client,validation,viewmodels,routes,templates,errors}.py` |
| Reporte | `src/sentinel/gui/report/{__init__,sections,service,pdf}.py` |
| Templates | `src/sentinel/gui/templates/{base,assets,asset_detail,events,alerts,health,discovery,discovery_panel,error,report_pdf}.html` |
| Static (vendorizado) | `src/sentinel/gui/static/js/{htmx.min.js,discovery.js}`, `static/css/{tailwind.min.css,daisyui.min.css,styles.css}`, `static/favicon.svg` |
| Tests | `tests/unit/gui/{conftest,test_validation,test_viewmodels,test_client,test_views,test_report,test_static_br}.py`, `tests/integration/gui/{__init__,test_gui_flow}.py` |
| Docs | `aidlc-docs/construction/u3-gui/code/code-generation-summary.md` (este archivo) |

## 2. Archivos modificados

| Archivo | Cambio |
|---|---|
| `src/sentinel/core/api/app.py` | Bloque try/except en `create_app` (Q10=A): routers `/ui` + `/api/v1/report`, handlers 502, `/static`; params `api_base`/`http_client` → `app.state.gui_config` |
| `requirements.txt` | Pines: `Jinja2==3.1.6`, `Markdown==3.11.3`, `weasyprint==70.0` + transitorios, `python-multipart==0.0.33` |
| `Dockerfile` | `apk add --no-cache pango cairo gdk-pixbuf fontconfig ttf-dejavu` (ID-U3-01); `COPY src/` ya incluye `gui/` |
| `.github/workflows/ci.yml` | Paso `coverage report --include='*/gui/*' --fail-under=70` (mismo `.coverage`, P8) |
| `pyproject.toml` | `per-file-ignores`: `src/sentinel/gui/*.py = ["B008"]` (Depends, patrón U2) |
| `README.md` | Sección GUI (rutas `/ui/*`, curl reporte, port-forward ST-M10-07) + gate doble en comandos de calidad |

## 3. Desviaciones (D-*)

| ID | Desviación | Justificación |
|---|---|---|
| D-U3-01 | `python-multipart==0.0.33` añadido a `requirements.txt` | Starlette exige la librería para `request.form()` en `POST /ui/discovery`; no estaba en los 3 pines de TS-U3-02 |
| D-U3-02 | Rama JSON de errores compartidos responde **sin** clave `code` (idéntico a U2) | Los tests de U2 comparan el body exacto (`{"detail": "not found"}`); el `code` sí se muestra en la página HTML de la GUI |
| D-U3-03 | Secciones del reporte con títulos fijos sin numerar (`## Inventory summary`, …) | FD §2 + BR-U3-20 son autoritativos; el patrón P2 ilustraba `## 1.`…`## 5.`. El AC `grep -c '^## '` se cumple (5 ≥ 4) |
| D-U3-04 | Mensaje inline de `scope_violation` en discovery = «host fuera de alcance» | Texto de la tabla FD §5 (mapeado por `response_code`); 409/503 usan sus textos FD |

Sin skip de PDF: WeasyPrint renderiza en el host y en la imagen (`docker build` OK, `import weasyprint` OK). htmx/Tailwind/DaisyUI vendorizados en repo (sin CDN, sin build step).

## 4. Validación local (Step 22 — todo verde)

```text
ruff check .                  → All checks passed
ruff format --check .         → 123 files already formatted
mypy src/sentinel             → Success: no issues found (64 files)
pytest tests/unit tests/property tests/integration
  --cov=sentinel --cov-fail-under=70
  → 279 passed · total coverage 95.26% (gate ≥70 ✓)
coverage report --include='*/gui/*' --fail-under=70
  → gui/ coverage 95% (732 stmts, 36 miss; gate ≥70 ✓) ✓
docker build -t sentinel:test . → Successfully built (apk + WeasyPrint OK)
```

Tests U3: 107 nuevos (vistas 19, reporte 18, validación/viewmodels/client 57 previos, static/BR 9, integración 4, resto combos).

## 5. Historias

| Historia | Steps | Estado |
|---|---|---|
| ST-M10-01 Asset inventory view | 8, 15, 17 | [x] |
| ST-M10-02 Asset detail view | 9, 15, 17 | [x] |
| ST-M10-03 Events and alerts timeline | 10, 15, 17 | [x] |
| ST-M10-04 Trigger discovery | 11, 15 | [x] |
| ST-M10-05 System health view | 11, 15, 17 | [x] |
| ST-M10-06 Network report and export | 12, 13, 16, 17 | [x] |
| ST-M10-07 Non-public GUI access | 21 | [x] (doc port-forward en README; AC de demo en Build & Test) |

Los AC con curl/demo en clúster se confirman en **Build & Test** (etapa única al final).

## 6. Estado del repo

- `sentinel/` sigue **sin `.git`** (anomalía conocida): nada tracked, sin commits hechos (regla: solo cuando el usuario lo pida).
- Cadena U3→U4: al aprobar esta etapa se inicia **U4 Functional Design**.
