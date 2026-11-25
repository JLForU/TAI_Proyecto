x|1# Functional Design Plan — U3 (Operator GUI & network report)

**Fase**: CONSTRUCTION — Functional Design (Parte 1: Planning)
**Fecha**: 2026-11-13
**Estado**: ARTIFACTS_GENERATED — respuestas todas A (Q11 corregida de D→A vía follow-up; FQ1/FQ2=A); artefactos generados; pendiente de aprobación
**Unidad**: U3 — `src/sentinel/gui/` (vistas Jinja/HTMX + `report/` ReportService)
**Entradas**: `unit-of-work.md` (§U3), `unit-of-work-story-map.md` (ST-M10-01..07), `stories.md` (ST-M10-01..07 + AC), `requirements.md` (FR-GUI-01..08, FR-EXP-02, NFR-TECH-04, NFR-OPS-04/05, §6.5), `component-methods.md` (§1 API, §6 ReportService, §10 GUI handlers), `services.md` (§2.2, §2.4–2.6, §4), `components.md` (C2, C7, C8), `implementation-scope.md` §3, `tech-stack-decisions.md` (nota: `jinja2`/`weasyprint` pertenecen a U3), contratos de U1+U2 aprobados.

---

## 1. Contexto de la unidad (Step 1 — analizado)

- **Responsabilidad**: vistas server-rendered `/ui/*` para el operador (inventario, detalle de activo, línea de tiempo eventos/alertas, salud, disparo de discovery) + `ReportService` (C7) que genera reporte de red Markdown/PDF bajo demanda y enlaza la exportación CSV/JSON de U2.
- **Historias**: ST-M10-01..07 (todas implemented; ST-M10-06 con secciones avanzadas documentadas en `implementation-scope.md` §3).
- **Frontera**: la GUI **nunca abre SQLite** y **consume solo la API HTTP del Core** (`requirements.md` §6.5: *"stateless and consumes only the Core HTTP API"*); no modifica activos; sin auth en la demo (FR-GUI-07: acceso solo `kubectl port-forward`).
- **Depende de**: U2 (API `/api/v1/{assets,events,alerts,health,export,discovery}` + servicios en proceso) — ya aprobado y generado. `GET /api/v1/report` **lo declara U3** (C7; U2 lo dejó fuera, ver FD U2 §business-logic-model).
- **Stack fijado por requisitos** (NO se pregunta): FastAPI + Jinja2 + HTMX + Tailwind/DaisyUI, server-rendered, sin SPA build (NFR-TECH-04); servido por el workload Core con assets embebidos en la imagen (NFR-OPS-04); reporte síncrono (App Design Q6=A); determinismo NFR-OPS-05.
- **Lo que U2 NO valida y U3 debe diseñar**: la GUI dispara discovery vía `POST /ui/discovery` (AC usa form-urlencoded `host=…` ⇒ 202); el scope allowlist (C12) es de U4 — el modo "lista completa" y el 400 `scope_violation` se contractan aquí y se cierran en U4 (IP4).
- **Open questions que esta etapa cierra**: rutas exactas de la GUI, modo de consumo de datos (loopback HTTP), interacciones HTMX, paginación/filtros del timeline, alcance de la vista de salud, contrato del trigger "host o lista", endpoints y secciones del reporte, rango/determinismo, estrategia PDF, entrega de assets estáticos, claves de config de U3.
- **Categoría Frontend**: **aplica** — U3 es la única unidad con UI (NFR-TECH-04).

---

## 2. Checklist del plan

- [x] Analizar unidad, historias y restricciones
- [x] Generar preguntas de diseño funcional (Q1–Q13)
- [x] Recoger respuestas a los `[Answer]:` (todas A; Q11 corregida vía follow-up)
- [x] Analizar respuestas y resolver ambigüedades — 1 ambigüedad (Q11=D sin descripción) + 2 follow-ups FQ1/FQ2 sobre huecos API↔FR; todas resueltas con A
- [x] Generar `business-logic-model.md`, `business-rules.md`, `domain-entities.md` en `construction/u3-gui/functional-design/`
- [ ] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño funcional

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Rutas y vistas de la GUI (UI map / FR-GUI-01..06)

Contexto: `services.md` §2.4 lista `/ui/assets | /ui/assets/{id} | /ui/events | /ui/alerts | /ui/health`; ST-M10-03 pide **una** línea de tiempo de eventos *y* alertas; `component-methods.md` §10 declara handlers para ambas páginas; AC de ST-M10-04/06 usan `POST /ui/discovery` y `GET /ui/report`.

A) Rutas: `GET /ui/assets`, `GET /ui/assets/{asset_id}`, `GET /ui/events` (línea de tiempo unificada eventos+alertas de ST-M10-03, con filtros), `GET /ui/alerts` (vista solo-alertas con filtro de estado), `GET /ui/health`, `POST /ui/discovery`, `GET /ui/report` — cubre services.md §2.4 literal y todos los AC *(recomendado)*

B) Ruta única `/ui/timeline` para eventos+alertas; eliminar `/ui/events` y `/ui/alerts` (desvío de services.md §2.4)

C) Solo páginas separadas `/ui/events` y `/ui/alerts` sin vista unificada (la historia ST-M10-03 se cumple filtrando en ambas)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Consumo de datos por la GUI (Architecture / requirements §6.5)

Contexto: requisito literal *"consumes only the Core HTTP API; it never opens SQLite directly"*; `services.md` §2.4 muestra `GuiService -> API/servicios`; monolito embebido (NFR-OPS-04) donde GUI y Core comparten proceso.

A) **Loopback HTTP con `httpx`** a `http://127.0.0.1:8080/api/v1` (mismo pod/proceso): la GUI habla exclusivamente por la API pública — cumple el requisito literal, testeable con el TestClient contra fixtures y contract-first con U2 *(recomendado)*

B) In-process: los handlers `/ui/*` invocan `QueryService`/`HealthService`/… directamente (más rápido, sin salto de red, pero la GUI no pasa por la API HTTP)

C) Híbrido: lecturas por servicios en proceso y discovery/report por HTTP

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Interacciones HTMX (UI / NFR-TECH-04)

Contexto: NFR-TECH-04 exige HTMX; AC usan `curl` sobre HTML y tests `-k filters`; la demo es laptop/port-forward.

A) HTMX donde aporta: polling del estado de discovery (`hx-get` a `GET /api/v1/discovery/{run_id}`), submits de filtros del timeline/inventario como GET forms, y actualización inline del resultado del trigger; navegación entre páginas con enlaces normales *(recomendado)*

B) HTMX mínimo: solo el polling de discovery; todo lo demás con forms HTML tradicionales (sin JS)

C) HTMX extendido: tabs, paginación lazy e inventario incremental vía `hx-incremental`

D) Other (describe después de `[Answer]:`)

[Answer]:A

### Question 4 — Paginación del inventario (UI / FR-GUI-01)

Contexto: AC1 de ST-M10-01 exige *"tabla paginada"*; U2 ya ofrece `limit` (1..1000) + `offset` con `Page`.

A) Server-side con `limit/offset` de la API: 100 por página, enlaces `?page=N` (offset=(N-1)·100), total de páginas desde el conteo de la página *(recomendado)*

B) Cargar un único bloque grande (limit 1000) y paginar en el cliente con HTMX

C) Scroll infinito con `hx-incremental`

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Filtros de la línea de tiempo (UI / FR-GUI-03)

Contexto: FR-GUI-03 pide filtros por **activo, severidad, regla y rango**; la API de U2 da filtros server-side en `/events` (`from,to,asset_id,rule,severity`) pero `/alerts` solo admite `from,to,state` (aunque `AlertOut` trae `asset_id` y `rule`).

A) `/events` se consulta con los filtros server-side de U2; `/alerts` se consulta por rango+estado y el filtrado por activo/regla/severidad de las alertas se aplica **en el handler de la GUI** sobre lo recibido — sin modificar la API aprobada de U2 *(recomendado)*

B) Ampliar la API de U2 con esos filtros en `/alerts` (cambio aditivo en el contrato de U2)

C) La línea de tiempo solo consume `/events` (las alertas se muestran derivadas de sus eventos)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Vista de salud: alcance de datos (UI / FR-GUI-05)

Contexto: AC pide estado, último ciclo exitoso y heartbeat del sensor; `services.md` §2.6 menciona lectura K8s *(opcional)*; `unit-of-work.md` §U3 asigna la lectura de K8s a U9/U10.

A) Solo datos de `GET /api/v1/health` de U2 (status, último ciclo, heartbeats por sensor, conteos, degraded) + lógica "sensor caído ⇒ aviso, nunca 'red sin activos'"; estado K8s queda para U9/U10 *(recomendado)*

B) A + campos placeholder de estado K8s (rellenados en U9/U10)

C) A + lectura directa de la API de K8s desde U3 (anticipa U9/U10)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Trigger de discovery desde la GUI (FR-GUI-04, IP4)

Contexto: AC1 = `POST /ui/discovery -d 'host=192.168.1.10'` ⇒ **202**; AC2 = host fuera de alcance ⇒ **400 + `scope_violation`** (hoy el handler de `ScopeError` existe en U2 pero nadie lo dispara: el allowlist `explicit_hosts` lo aporta **U4**, IP4); FR-GUI-04 además pide "un host **o la lista completa** configurada" y mostrar estado/resultado.

A) `POST /ui/discovery` (form: `host`) ⇒ proxy a `POST /api/v1/discovery` con `hosts=[host]`, passthrough de 202/400/409/503 y redirige/polling al estado del run; el modo **lista completa** se diseña aquí como form `mode=all` que el GUI traduce a la lista expuesta por U4 — contrato diferido: **U4 añadirá la expansión del alcance** (cierra IP4/ST-M1-01) y U3 lo deja documentado *(recomendado)*

B) Solo host individual en U3 (el AC solo lo prueba); el modo lista completa queda fuera de U3 y se resuelve íntegramente en U4

C) La GUI mantiene su propia copia de la lista de hosts configurada (rompe single-source-of-truth)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Endpoints de reporte (FR-GUI-06 / C7)

Contexto: C7 declara `GET /api/v1/report?from&to&format=md|pdf` (contrato en `component-methods.md` §1/§6); el AC de ST-M10-06 hace `curl "localhost:8080/ui/report?from=…&to=…" -o report.md`; `download_report(...) -> FileResponse` (§10).

A) Ambos: `GET /api/v1/report` (contrato C7, `format=md|pdf`, devuelve el artefacto) **y** `GET /ui/report` (descarga `FileResponse` con `Content-Disposition`, usado por el AC curl); la GUI expone botones que apuntan a ambos *(recomendado)*

B) Solo `GET /ui/report` (el contrato C7 se satisface con la ruta de descarga)

C) Solo `GET /api/v1/report` (el AC curl se ajusta a la ruta de API)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 9 — Secciones del reporte (FR-GUI-06 / component-methods §6)

Contexto: AC1 exige ≥4 secciones `## ` con inventario, cambios, top talkers (si hay tráfico), alertas y rango de evidencia; §6 declara `build_inventory_section`, `build_changes_section`, `build_top_talkers_section`, `build_alerts_section`; `implementation-scope.md` §3 deja las "secciones avanzadas" como mejora documentada.

A) Exactamente 5 secciones `## ` fijas: `## Inventory summary`, `## Changes`, `## Top talkers` (o `sin datos`), `## Alerts`, `## Evidence range` — deterministas y con el orden fijo *(recomendado)*

B) Las 5 base + 1 sección avanzada ya disponible (detalle por activo con sus eventos)

C) Secciones dinámicas según lo que haya en el rango (cambia el número de `## `)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 10 — Rango y determinismo del reporte (NFR-OPS-05)

Contexto: AC1 pasa `from`/`to` explícitos; AC2 exige que los mismos filtros ⇒ secciones idénticas; NFR-OPS-05 prohíbe variación no determinista.

A) `from`/`to` **requeridos** (fecha `YYYY-MM-DD`); el contenido de las secciones es 100% función del rango y los datos persistidos; cualquier marca temporal de generación (`Generated at …`) vive **fuera** de las secciones `## ` para no romper la comparación *(recomendado)*

B) `from`/`to` opcionales con default de los últimos 7 días (consistencia con el export de U2); determinismo igual que A

C) `from`/`to` requeridos e incluir el timestamp dentro de la primera sección

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 11 — Estrategia de generación de PDF (Tech / Report)

Contexto: FR-GUI-06 pide Markdown **y** PDF; `tech-stack-decisions.md` anticipa `weasyprint` para U3; `render_pdf(markdown) -> bytes` (§6); Dockerfile hereda `python:3.11-alpine` (U1); NFR-OPS-05 (determinismo).

A) **WeasyPrint**: MD → HTML (con `markdown` stdlib-adjunto o librería mínima) → PDF vía WeasyPrint; calidad tipográfica real; implica añadir paquetes del sistema (`pango`, `cairo`) al Dockerfile de U1 *(recomendado por tech-stack)*

B) `reportlab` puro: construir el PDF directamente desde las secciones (sin HTML); menos dependencias de sistema, peor tipografía/estilo

C) `fpdf2` (pure-Python, ligero; plantilla simple)

D) Markdown solamente en U3; PDF documentado como mejora (rompe FR-GUI-06 "Markdown and PDF")

E) Other (describe después de `[Answer]:`)

[Answer]: A *(corregido de D vía follow-up 2026-11-13: se confirmó WeasyPrint para cumplir FR-GUI-06/implementation-scope §2)*

### Question 12 — Entrega de assets estáticos (NFR-OPS-04 / NFR-TECH-04)

Contexto: NFR-OPS-04 pide *"static assets and templates baked into the image"*; NFR-TECH-04 prohíbe SPA build step; la demo corre en el lab (posible sin Internet).

A) **Vendorizar en el repo** `src/sentinel/gui/static/`: `htmx.min.js` + CSS de Tailwind/DaisyUI pre-generado (commit del build, no build en CI) + favicon — la imagen es autosuficiente, sin CDN ni red en la demo *(recomendado)*

B) CDN en las plantillas (Tailwind Play CDN + htmx desde unpkg/jsdelivr): cero archivos en repo, pero la demo depende de Internet

C) Build en CI con Tailwind CLI (genera CSS en pipeline) — añade etapa de build a la imagen

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 13 — Claves de configuración de U3 (Business Rules / config)

Contexto: BR-06 (patrón de loader por unidad como `core.config`); GUI y Core corren en el mismo pod (loopback fijo); tests necesitan sobreescribir la base URL.

A) **Sin claves nuevas**: constante `API_BASE = "http://127.0.0.1:8080"` en el cliente de la GUI, sobreescribible por parámetro de `create_app`/fixtures en tests *(recomendado)*

B) Una clave `SENTINEL_API_BASE` (default `http://127.0.0.1:8080`) con loader propio `gui.config` (patrón U2)

C) `SENTINEL_API_BASE` + `SENTINEL_REPORT_DEFAULT_DAYS` (rango default del reporte)

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 3.1 Preguntas de seguimiento (tras analizar respuestas)

### FQ1 — Columnas SO y source en el inventario (FR-GUI-01 vs API de U2)

Contexto: `GET /api/v1/assets` devuelve `AssetSummary` **sin** `os_name`/`os_provenance`/`source` (solo los trae `GET /assets/{id}`; además `AssetDetail` expone OS pero **no** el campo `assets.source` de la tabla). El AC1 de ST-M10-01 exige la columna SO con procedencia en la tabla.

A) Detalle por fila visible (≤100/pág): la GUI llama `GET /api/v1/assets/{id}` por cada fila para OS+procedencia; `source` de la fila se deriva de los `source` de sus `recent_observations` (discovery/traffic/arp). Sin tocar U2 *(elegido)*

B) Ampliar `AssetSummary` de U2 con esos campos (edita código/tests de U2 durante U3)

C) Sin columna SO en la tabla (incumple FR-GUI-01/AC1)

**[Answer]: A**

### FQ2 — Origen de la sección "top talkers" del reporte (FR-GUI-06 vs API de U2)

Contexto: U2 no expone observaciones/ventanas por rango; solo el detalle reciente por activo (cap 200).

A) `ReportService` consulta el detalle de los activos vía API y agrega `bytes_per_second`/pares de las observaciones disponibles; sin tráfico expuesto ⇒ `sin datos`. Sin tocar U2 *(elegido)*

B) Endpoint aditivo `GET /api/v1/observations?from&to` en U2 (edita módulo de U2 durante U3)

C) Sección degradada a `sin datos` siempre

**[Answer]: A**

---

## 4. Artefactos obligatorios (tras aprobación de respuestas)

| Artefacto | Contenido |
|---|---|
| `construction/u3-gui/functional-design/business-logic-model.md` | Flujos: consulta GUI (loopback HTTP), línea de tiempo con filtros, trigger discovery proxy, vista de salud, ReportService (secciones MD/PDF), descarga/export; manejo de errores (passthrough de códigos U2) |
| `construction/u3-gui/functional-design/business-rules.md` | Reglas ST-M10-01..07 + FR-GUI-01..08 con verificación (OS provenance, `sin datos`, firing/resolved, 202/400 scope, determinismo del reporte, port-forward only, assets embebidos) |
| `construction/u3-gui/functional-design/domain-entities.md` | Entidades de presentación: view models (AssetRow, AssetDetailVM, TimelineEntry, HealthVM, ReportArtifact/Section) y contratos consumidos de U2; sin esquema nuevo (U3 no escribe DB) |

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los artefactos de Functional Design y presentaré el mensaje de completitud.

**No se genera ningún artefacto de Functional Design hasta completar este gate.**
