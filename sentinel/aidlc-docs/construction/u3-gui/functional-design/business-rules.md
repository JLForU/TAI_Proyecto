# Business Rules & Validation — U3 (Operator GUI & network report)

**Fase**: CONSTRUCTION — Functional Design
**Fecha**: 2026-11-13
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U3 — `src/sentinel/gui/`
**Traza**: ST-M10-01..07, FR-GUI-01..08, FR-EXP-02, NFR-TECH-04, NFR-OPS-04/05; plan Q1–Q13 = A (Q11 corregida) + FQ1/FQ2 = A.

---

## 1. Inventario (ST-M10-01, FR-GUI-01/08)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U3-01 | `GET /ui/assets` renderiza tabla **paginada** con columnas IP, MAC, hostname, SO (+procedencia), último avistamiento, estado; cada fila lleva `data-asset-row` | ST-M10-01 AC1, FR-GUI-01 | `curl -s localhost:8080/ui/assets \| grep -c 'data-asset-row'` > 0; `pytest tests/integration/test_gui_assets.py -k columns` |
| BR-U3-02 | SO desconocido muestra `desconocido` (+procedencia `unknown`); **nunca** un valor inventado | ST-M10-01 AC2, FR-GUI-08 | `pytest tests/integration/test_gui_assets.py -k unknown_os` |
| BR-U3-03 | Procedencia del SO se etiqueta en 4 estados: `observed→observado`, `inferred→inferido`, `declared→declarado`, `unknown→desconocido` | FR-GUI-08, PRD §6.5 | test de mapeo de etiquetas |
| BR-U3-04 | OS y procedencia por fila se obtienen con `GET /assets/{id}` por fila visible (N+1 ≤100/pág); `source` de la fila = `source` distintos de sus `recent_observations` (discovery/traffic/arp) | FQ1=A | test con detalle inyectado por fila |
| BR-U3-05 | Paginación server-side: `limit=100`, `?page=N ⇒ offset=(N-1)·100`, total/páginas desde `Page.total` | Q4=A | test de página 2 (offset 100) |

## 2. Detalle de activo (ST-M10-02, FR-GUI-02)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U3-06 | `GET /ui/assets/{id}` presenta secciones **observaciones, eventos, tráfico y ARP** con datos del detalle correlacionados por IP + ventana | ST-M10-02 AC1, FR-GUI-02 | `pytest tests/integration/test_gui_asset_detail.py -k sections` |
| BR-U3-07 | Activos sin observaciones de tráfico muestran `sin datos` en la sección de tráfico — **cero inventado prohibido** | ST-M10-02 AC2, services.md §4 | `pytest tests/integration/test_gui_asset_detail.py -k no_traffic` |

## 3. Línea de tiempo (ST-M10-03, FR-GUI-03)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U3-08 | `GET /ui/events` con filtros activo/severidad/regla/rango muestra **solo** coincidencias (eventos filtrados server-side por U2; alertas filtradas en el handler) | ST-M10-03 AC1, Q5=A | `pytest tests/integration/test_gui_timeline.py -k filters` |
| BR-U3-09 | Cada alerta distingue `firing` de `resolved`; `resolved` muestra su `resolved_at` | ST-M10-03 AC2 | `pytest tests/integration/test_gui_timeline.py -k resolved_state` |
| BR-U3-10 | La API de U2 **no se modifica** para los filtros de alertas (asset/rule/severity se aplican en el handler U3) | Q5=A | revisión de contrato: cero cambios en `src/sentinel/core/` |

## 4. Disparo de discovery (ST-M10-04, FR-GUI-04, IP4)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U3-11 | `POST /ui/discovery` (form `host=<ip>`) ⇒ proxy a `POST /api/v1/discovery` con `hosts=[host]` ⇒ **202** | ST-M10-04 AC1 | `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8080/ui/discovery -d 'host=192.168.1.10'` ⇒ 202 |
| BR-U3-12 | Host fuera del alcance autorizado ⇒ **400** con `code=scope_violation` (passthrough del handler `ScopeError` de U2) | ST-M10-04 AC2, services.md §4 | `pytest tests/integration/test_gui_discovery.py -k out_of_scope` |
| BR-U3-13 | Estado del run visible por polling HTMX a `GET /api/v1/discovery/{run_id}`: `running → completed \| timeout \| failed` | FR-GUI-04 "show cycle status and result" | test de polling con run simulado |
| BR-U3-14 | `409` (ciclo en curso) y `503` (runner ausente, U4 pendiente) se muestran como mensajes inline, sin 500 | U2 BR-U3-32/34, services.md §4 | tests 409/503 en la GUI |
| BR-U3-15 | Modo **lista completa** del trigger: contrato diferido a U4 (IP4/ST-M1-01); U3 deja el form preparado y documenta la expansión pendiente | Q7=A, FQ revisión | documentado en FD §3.4; AC solo prueba host individual |

## 5. Salud (ST-M10-05, FR-GUI-05)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U3-16 | `GET /ui/health` muestra estado del Core, hora del último ciclo exitoso y heartbeat por sensor (datos de `GET /api/v1/health`) | ST-M10-05 AC1 | `pytest tests/integration/test_gui_health.py -k healthy` |
| BR-U3-17 | Sensor sin heartbeat ⇒ badge **`sensor caído`**; el inventario vacío **nunca** se presenta como "red sin activos" | ST-M10-05 AC2, services.md §4/§2.6 | `pytest tests/integration/test_gui_health.py -k sensor_down` |
| BR-U3-18 | U3 no lee la API de K8s (estado de Pods/Jobs es de U9/U10) | Q6=A, unit-of-work §U3 | revisión de imports: sin `kubernetes` |

## 6. Reporte (ST-M10-06, FR-GUI-06, NFR-OPS-05)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U3-19 | `GET /ui/report?from&to[&format]` y `GET /api/v1/report` comparten `ReportService.generate`; `from`/`to` **requeridos** (`YYYY-MM-DD`); `format=md` default | Q8=A, Q10=A | `curl -s "localhost:8080/ui/report?from=2026-11-01&to=2026-11-07" -o report.md` |
| BR-U3-20 | El reporte tiene **exactamente 5 secciones `## `** en orden fijo: Inventory summary, Changes, Top talkers (o `sin datos`), Alerts, Evidence range (≥4 exigido por el AC) | Q9=A, ST-M10-06 AC1 | `grep -c '^## ' report.md` ≥ 4 |
| BR-U3-21 | **Determinismo**: mismos `from`/`to` + mismos datos ⇒ secciones idénticas byte a byte; la marca `Generated at …` vive **fuera** de las secciones `## ` | NFR-OPS-05, ST-M10-06 AC2, Q10=A | `pytest tests/integration/test_report_determinism.py` |
| BR-U3-22 | Top talkers se agrega desde `GET /assets/{id}` (payloads `bytes_per_second`/pares, FQ2=A); sin tráfico expuesto ⇒ `sin datos` (services.md §2.5) | FR-GUI-06, FQ2=A | test con/sin observaciones de tráfico |
| BR-U3-23 | `Changes` = eventos del rango con tipo ∈ {`asset_first_seen`, `asset_missing`, `port_service_changed`, `arp_mapping_changed`} | component-methods §6 `build_changes_section` | test de sección con eventos mixtos |
| BR-U3-24 | `format=pdf` ⇒ MD → HTML → **WeasyPrint** → `application/pdf` (misma MD que `format=md`) | Q11=A (corregido), FR-GUI-06 | test: PDF empieza con `%PDF` y proviene de la misma MD |
| BR-U3-25 | El botón de exportación enlaza `GET /api/v1/export?format=csv\|json&from&to` de U2 (no reimplementa export) | FR-EXP-02, ST-M10-06 AC3 | `curl ... "localhost:8080/api/v1/export?format=csv&from=…&to=…"` ⇒ 200 |

## 7. Acceso y empaquetado (ST-M10-07, FR-GUI-07, NFR-OPS-04)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U3-26 | U3 **no añade autenticación** ni sesiones; la superficie la decide U9 (sin LoadBalancer/NodePort; acceso `kubectl port-forward`) | FR-GUI-07 (Q5=D App Design), NFR-OPS-04 | en Build & Test: `jq` sobre Services + `grep -c 'port-forward' docs/deployment.md` |
| BR-U3-27 | Templates y static **van embebidos en la imagen** (vendorizados en repo: htmx + CSS Tailwind/DaisyUI pre-generado, sin CDN, sin SPA build) | NFR-OPS-04, Q12=A | test: archivo static presente bajo `gui/static/`; plantillas sin `<script src="http…cdn` |
| BR-U3-28 | Stack de vistas: FastAPI + Jinja2 + HTMX + Tailwind/DaisyUI server-rendered | NFR-TECH-04 | revisión de dependencias/imports |

## 8. Arquitectura y frontera (Q2/Q13, requirements §6.5)

| ID | Regla | Origen | Verificación |
|---|---|---|---|
| BR-U3-29 | Todo U3 (vistas **y** ReportService) consume **solo** `httpx` → `/api/v1` por loopback; cero imports de `core.db`, repos o servicios de U2 | Q2=A, requirements §6.5 | test/arquitectura: `gui/` no importa `sentinel.core.db`/`…repos`/`…service` |
| BR-U3-30 | Sin claves `SENTINEL_*` nuevas: `API_BASE` constante (`http://127.0.0.1:8080`), inyectable en tests | Q13=A, BR-06 | revisión de `gui/` (sin loader de config) |
| BR-U3-31 | Fallo de loopback ⇒ página **502** "Core API no disponible" sin stacktrace; errores U2 pasan con su `detail`/`code` | business-logic §5 | test con API apagada |
| BR-U3-32 | Log de la GUI en JSON por `foundation.logging` (mismo formato que U1/U2), sin imprimir HTML/errores a stdout | BR-09..12 U1 | test de log en handler con error |

## 9. Anti-requisitos de la unidad

- No abre SQLite ni importa la capa de persistencia de U2 (BR-U3-29).
- No autentica, no registra usuarios, no amplía el Service (BR-U3-26).
- No ejecuta sondeo ni parsing Nmap/ARP (eso es U4); solo dispara vía API.
- No evalúa condiciones ni escribe `alerts`/`baselines` (U6).
- No genera PDF con librerías distintas de WeasyPrint (Q11=A).
- Sin worker asíncrono de reportes (App Design Q6=A: síncrono).
