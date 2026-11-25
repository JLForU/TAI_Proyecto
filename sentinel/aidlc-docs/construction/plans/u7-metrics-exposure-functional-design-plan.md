# Functional Design Plan — U7 (Metrics exposure)

**Fase**: CONSTRUCTION — Functional Design (Parte 1: Planning)
**Fecha**: 2026-11-24
**Estado**: Q1–Q11 = Acepto todo (2026-11-24: Q1=A, Q2=A, Q3=C, Q4=A, Q5=A, Q6=A, Q7=A, Q8=A, Q9=A, Q10=B, Q11=A); artefactos FD generados; pendiente de aprobación
**Unidad**: U7 — `src/sentinel/core/metrics/` (sustituir el `collect()` stub de U2 por una agregación real de las 12 familias del contrato U1, integrar los indicadores de U6 vía `ConditionService.metric_samples()`, añadir familias de inventario si se aprueba, y crear el manifiesto ServiceMonitor ST-M6-03)
**Entradas**: `unit-of-work.md` (§U7 Metrics exposure), `unit-of-work-story-map.md` (§U7: ST-M6-01..03, todas `implemented` — endpoint ya alojado en Core), `stories.md` (AC ST-M6-01..03), `implementation-scope.md` (M6: «`/metrics`, ServiceMonitor, reglas…»), `component-methods.md` (§5 MetricsExporter C6), `requirements.md` trazas FR-CORE-02/FR-OBS-01/FR-OBS-02, código existente (`core/metrics/{server,collect}.py`, `foundation/metrics_contract.py`, `baseline/indicators.py`, `ConditionService.metric_samples/collector_up`, `core/health/service.py`, `core/api/app.py` wiring) y tests (`tests/unit/core/test_metrics.py`, `tests/unit/foundation/test_metrics_contract.py`, `tests/unit/baseline/test_indicators.py`).

---

## 1. Contexto de la unidad (Step 1 — analizado)

- **Responsabilidad**: proyectar métricas agregadas de Core en `GET /metrics` (puerto 9108) sin labels de alta cardinalidad, exponer los indicadores de condición de U6 y registrar el ServiceMonitor que permite a Prometheus descubrir el endpoint (ST-M6-03).
- **Hecho ya (costuras dejadas por U2/U6)**:
  - `server.py`: `MetricsServer` hilo daemon, `GET /metrics` → 200 `text/plain; version=0.0.4`, 404 en ruta desconocida, 500 si el render falla — docstring: «U7 sustituye el `collect` sin tocar este servidor».
  - `collect.py`: stub que devuelve **exactamente** `METRIC_FAMILIES` (garantía `names == set(METRIC_FAMILIES)`), midiendo solo `api_requests_total`, `discovery_cycles{,_failed}_total` y `collector_heartbeat_age_seconds`; el resto en cero con `component=core`. Docstring: «U7 sustituye `collect()` sin tocar familias/rutas» (las familias se tocan solo si Q3 lo aprueba).
  - `foundation/metrics_contract.py`: prefijo `sentinel_`, catálogo de 12 familias, denylist `FORBIDDEN_LABELS={src_ip,dst_ip,mac,asset_id}` (BR-21) y allowlist `ALLOWED_LABELS_DEFAULT={component,protocol,interface,rule,state}` (hoy **no** enforced por `assert_labels`).
  - U6: `ConditionService.metric_samples()` (proyección pura bajo demanda, «para U7»), `ConditionService.collector_up(traffic_last_seen)` (1/0 según `collector_timeout_seconds`), familias `sentinel_traffic_threshold_exceeded|baseline_status|baseline_established|collector_up{collector="traffic"}`.
  - Wiring actual en `create_app`: `collect_fn=lambda: collect(api_requests=…, cycles=…, heartbeats=HealthService(db).health().sensor_heartbeats)`.
- **Gap real de la unidad**: el `collect()` no lee inventario/alertas/baselines ni consuma `ConditionService.metric_samples()`; no existen familias de inventario en el contrato (gap vs ST-M6-02 y AC de SN-033); no existe artefacto ServiceMonitor en el repo (`deploy/`, `charts/` inexistentes); el HELP del render dice «(U2 stub)».
- **Frontera (criterio del unit-of-work)**: endpoint con formato Prometheus válido; tests de cardinalidad con fixtures; sin dependencia de red/clúster en pruebas; no evalúa reglas de alerta (U8), no guarda series temporales en Core, no usa IPs/pares como labels.
- **Depende de**: U1 (`METRIC_FAMILIES`, `metric_name`, `assert_labels`), U2 (servidor, contadores, `HealthService`, repos y esquema), U6 (`ConditionService.metric_samples/collector_up`), U5 (observaciones de tráfico/ARP como fuente de contadores).
- **Categoría Frontend**: **no aplica** a U7 (los dashboards Grafana son U8/ST-M7-05; sin UI propia).

---

## 2. Checklist del plan

- [x] Analizar unidad, historias y restricciones (Step 1)
- [x] Generar preguntas de diseño funcional Q1–Q11 (Steps 2–3)
- [x] Guardar plan en `aidlc-docs/construction/plans/u7-metrics-exposure-functional-design-plan.md` (Step 4)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-24: "Acepto todo" ⇒ Q1–Q11 según recomendación)
- [x] Analizar respuestas y resolver ambigüedades — interacciones revisadas (Q1×Q2 coherencia hook/scrape; Q3×Q8 cambio de contrato vía funciones; Q5×Q6×Q10 labels `metric`/`collector` cubiertos por allowlist extendida; Q3 «hook o COUNT» resuelto ⇒ `COUNT(*)` de `events`, monótono sin hook nuevo) ⇒ **sin FQ necesarias**
- [x] Generar `business-logic-model.md`, `business-rules.md`, `domain-entities.md` en `construction/u7-metrics-exposure/functional-design/` (Step 6)
- [ ] Presentar mensaje de completitud y esperar aprobación (Steps 7–8)
- [ ] Registrar aprobación en `audit.md` y marcar etapa en `aidlc-state.md` (Step 9)

---

## 3. Preguntas de diseño funcional

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas **todas las recomendaciones**, responde `Acepto todo` (se aplicará la opción recomendada de cada pregunta).

### Question 1 — Arquitectura de recolección de `collect()`

Contexto: el servidor corre en el mismo proceso que Core (puede leer SQLite y usar refs en memoria); hoy existen contrapartes en proceso (`ApiRequestCounter`, `CycleCounter`) y el precedente del hook `on_accepted` de U6. Las familias `*_total` necesitan contadores y las gauges necesitan estado vigente.

- **A) (Recomendado)** **Híbrido**: contadores en proceso para `api_requests_total`, `discovery_cycles{,_failed}_total` (ya existen) y `flows_total`/`arp_messages_total` (alimentados por hook de ingesta, precedente `on_accepted`); gauges leídas de SQLite al momento del scrape (`alerts_firing`, familias de inventario, `collector_heartbeat_age_seconds`); indicadores de U6 vía `ConditionService.metric_samples()` en el mismo scrape.
- **B)** **Todo scrape-time**: `collect()` consulta SQLite para las 12 familias (los `_total` como `COUNT(*)` persistente). Cero hooks nuevos, pero parseo de payload de observaciones en cada scrape y acoplamiento fuerte a SQL.
- **C)** **Todo en proceso con caché**: estado en memoria actualizado por hooks y refrescado periódicamente; SQLite solo como fuente al arranque. Más complejo y con riesgo de divergencia entre caché y BD.

[Answer]: A (2026-11-24, "Acepto todo")

### Question 2 — Semántica de `sentinel_flows_total`, `sentinel_arp_messages_total` y `sentinel_bytes_per_second`

Contexto: contrato U1 exige las tres familias; U5 persiste observaciones de tráfico (`bytes_per_second`, `protocol`, `interface`) y ARP en `observations`; no existe repo de consultas de tráfico.

- **A) (Recomendado)** `flows_total` y `arp_messages_total` = contadores de observaciones ingeridas (hook; el reset al reiniciar lo absorbe Prometheus); `bytes_per_second` = gauge con la **media de la última ventana de tráfico** leída de la última observación `traffic` en DB, con labels `interface`+`protocol` (misma clave que las series de U6).
- **B)** Los tres derivados de DB al scrape: `COUNT(*)` acumulado de observaciones desde el arranque (persiste entre reinicios) y media de las últimas N ventanas.
- **C)** Dejar `flows_total`/`arp_messages_total`/`bytes_per_second` en cero durante U7 (el contrato se satisface con zeros como hoy) y poblirlas en U8.

[Answer]: A (2026-11-24, "Acepto todo")

### Question 3 — Familias de inventario (gap del contrato U1)

Contexto: `METRIC_FAMILIES` (U1) no tiene familias de inventario, pero ST-M6-02 menciona «métricas agregadas de inventario» y el AC de SN-033 exige que el dashboard muestre «métricas agregadas de inventario/cambios y última ejecución» desde Prometheus (el detalle por activo va por export CSV/JSON, no por labels).

- **A)** Agregar **solo** `sentinel_assets_total` (gauge: nº de activos, labels `component`/`state`) al contrato U1.
- **B)** Mantener exactamente las 12 familias actuales; el inventario se consulta por API/export y el dashboard de inventario se limita a lo que ya existe (riesgo: SN-033 no podrá mostrar agregados de inventario/cambios).
- **C) (Recomendado)** Agregar **`sentinel_assets_total`** (gauge, nº de activos) **y `sentinel_asset_changes_total`** (contador de eventos de cambio de inventario — `first_seen`/`missing`/`ArpMappingChanged` — alimentado por hook o `COUNT` de `events`), para cubrir íntegramente el AC de SN-033.

[Answer]: C (2026-11-24, "Acepto todo")

### Question 4 — Labels de `sentinel_alerts_firing`

Contexto: `alerts` guarda estado `firing`; el catálogo de condiciones de U6 es pequeño y acotado; U8 (alertas Prometheus) usa labels `alertname`/`scope`/`sensor_id` en **alertas** de Prometheus, no en estas métricas.

- **A) (Recomendado)** Conteo **global** de alertas en `firing` (labels `component=core`); el detalle por condición/activos se consulta en `GET /api/v1/alerts` (U3/GUI y export).
- **B)** Desglose por `rule`: `sentinel_alerts_firing{rule="<condition_id>"}` — cardinalidad acotada por el catálogo, pero añade una serie por condición activa.

[Answer]: A (2026-11-24, "Acepto todo")

### Question 5 — Integración de los indicadores de U6 en el scrape

Contexto: U6 ya publica `ConditionService.metric_samples()` — «Proyección para U7 (bajo demanda, sin caché — Q7 NFR-Design)» — con `states`, `active_alerts` y `collector_up` internos; el docstring de `indicators.py` dice «U6 produce; U7 expondrá vía `/metrics`».

- **A) (Recomendado)** `collect()` recibe el `ConditionService` (inyección en `create_app`, precedente del lambda actual) y llama `metric_samples()` **en cada scrape** — sin caché, coherente con el diseño de U6.
- **B)** Suscribirse a los cambios de condición y cachear los samples en memoria; el scrape solo lee la caché (más rápido, pero diverge del contrato «sin caché» de U6 y añade invalidación).
- **C)** Muestrear con un hilo period propio (intervalo independiente del scrape) y publicar el último snapshot.

[Answer]: A (2026-11-24, "Acepto todo")

### Question 6 — Fuente de `sentinel_collector_up`

Contexto: `ConditionService.collector_up(traffic_last_seen)` ya implementa la semántica SN-029 (1 si `age <= collector_timeout_seconds`, 0 si `None`/vencido) y `metric_samples()` ya lo emite con `collector="traffic"`; por separado existe `collector_heartbeat_age_seconds` (gauge de edad, familia distinta).

- **A) (Recomendado)** Reutilizar `ConditionService.collector_up` a través de `metric_samples()` (Q5) — una sola semántica de vigencia, la de U6.
- **B)** Recalcular en U7 a partir de `HealthService.sensor_heartbeats` con el umbral (duplica la regla de timeout en dos módulos).
- **C)** Derivar `collector_up` del valor de `collector_heartbeat_age_seconds` dentro del render (acoplamiento entre familias).

[Answer]: A (2026-11-24, "Acepto todo")

### Question 7 — Ubicación y selectores del ServiceMonitor (ST-M6-03)

Contexto: no existe `charts/` ni `deploy/` en el repo; el AC de ST-M6-03 pide `kubectl get servicemonitor sentinel-core -n sentinel` con selector `app.kubernetes.io/name=sentinel-core` y target `up`; el chart de Helm de Sentinel se construye en U9; PRD SN-031..035 (U8) creará `deploy/monitoring/values.yaml` y `deploy/monitoring/rules/`; kube-prometheus-stack suele exigir el label `release: <nombre>` en ServiceMonitors.

- **A) (Recomendado)** Manifiesto standalone `deploy/monitoring/servicemonitor.yaml` (namespace `selector.namespace: sentinel`, `matchLabels: app.kubernetes.io/name: sentinel-core`, label `release: monitoring`), aplicable con `kubectl apply -f` — coherente con el directorio `deploy/monitoring/` que usarán U8/U9 y sin depender del chart de U9.
- **B)** Template `charts/sentinel/templates/servicemonitor.yaml` con gate `serviceMonitor.enabled` en values — el chart es dueño del scrape, pero `charts/` se crea en U9 y ST-M6-03 quedaría sin artefacto hasta entonces.
- **C)** Ambos: manifest standalone en U7 **y** template en U9 (riesgo de duplicidad a reconciliar en U9).

[Answer]: A (2026-11-24, "Acepto todo")

### Question 8 — Forma del código C6 (MetricsExporter)

Contexto: `component-methods.md` §5 define C6 como clase con `collect() -> list[MetricFamily]` y `render_prometheus()`; el código real son funciones de módulo (`collect(...)`, `render_prometheus(...)`) y los docstrings ya anuncian «U7 sustituye `collect()` sin tocar familias/rutas».

- **A) (Recomendado)** Mantener **funciones puras** en `core/metrics/` ampliando la firma de `collect()` con los providers nuevos (condition service, repos/consultas, contadores de ingesta); `create_app` sigue ensamlando el `collect_fn` (mínimo diff, sin clases nuevas).
- **B)** Introducir la clase **`MetricsExporter`** (forma C6) que encapsule fuentes y exponga `collect()`/`render_prometheus()` como métodos; `create_app` la instancia una vez.
- **C)** Fachada `MetricsExporter` delgada que **delega** en las funciones actuales (satisfice C6 en el diagrama sin mover lógica).

[Answer]: A (2026-11-24, "Acepto todo")

### Question 9 — Manejo de errores durante el scrape

Contexto: el handler ya captura excepciones del render → 500 y log `metrics_error`; Prometheus marcaría el target `down` si el scrape falla; no hay caché de último valor bueno.

- **A) (Recomendado)** **Mantener 500** ante fallo de render/DB: señal clara de que el exporter está roto (target `down`), sin valores fabricados; se añade test del camino de error.
- **B)** Degradar a render **parcial** con las familias no calculables en 0 y responder 200 (target sigue `up` aunque Core tenga problemas de BD) + log de error.
- **C)** 200 solo con las familias de contadores en proceso (siempre disponibles) y las demás omitidas del body.

[Answer]: A (2026-11-24, "Acepto todo")

### Question 10 — Enforcement de labels: denylist vs allowlist

Contexto: U6 emite labels `metric` y `collector` que **no** están en `ALLOWED_LABELS_DEFAULT`; `assert_labels()` solo aplica la denylist (BR-21). La allowlist hoy no la valida nadie en runtime — cualquier label no prohibido pasa (p. ej. `src_port` sería aceptado).

- **A)** Dejar solo la denylist en runtime y documentar `collector`/`metric` como labels acotados excepcionales del contrato (sin tocar foundation).
- **B) (Recomendado)** Ampliar `ALLOWED_LABELS_DEFAULT` con `collector` y `metric` y hacer que `collect()`/`render_prometheus()` validen **cada sample contra la allowlist** (además de la denylist) — falla temprano ante cualquier label fuera de catálogo; toca `metrics_contract.py` + tests de contrato.
- **C)** Re-etiquetar U6 para encajar en la allowlist actual (p. ej. `component=collector`, `state=up|down`) — cambia código y tests de U6 (fuera del alcance natural de U7).

[Answer]: B (2026-11-24, "Acepto todo")

### Question 11 — HELP/TYPE del render

Contexto: hoy el HELP dice `Sentinel <family> (U2 stub)` para todas; `_type_of()` ya infiere `counter` por sufijo `_total` y `gauge` en caso contrario.

- **A) (Recomendado)** Dict de HELP por familia en `core/metrics/` con texto descriptivo real (uno por familia, incluidas las nuevas de Q3) y mantener `_type_of()` para TYPE.
- **B)** HELP genérico único («Sentinel metrics») para todas las familias.
- **C)** Eliminar HELP (solo `# TYPE`) — Prometheus lo tolera, pero pierde documentación en el endpoint.

[Answer]: A (2026-11-24, "Acepto todo")
