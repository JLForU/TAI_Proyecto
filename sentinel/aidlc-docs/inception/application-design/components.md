# Components — Sentinel

**Fase**: INCEPTION — Application Design
**Fecha**: 2026-11-07
**Estado**: GENERATED — pendiente de aprobación
**Decisiones base**: Q1=A (monolito modular + colectores del mismo proyecto), Q2=A (discovery en proceso, acotado), Q3=A (GUI embebida), Q4=A (REST/JSON), Q5=D (sin auth en la demo), Q6=A (reporte síncrono), Q7=A (HTTP + reintentos), Q8=A (métodos de alto nivel).

---

## 1. Principios de diseño

- **MVP y mínimo privilegio**: Core monolito modular; Discovery y Sensor son workloads separados del mismo proyecto/imagen por necesidad operativa (CronJob y captura).
- **Un solo escritor**: solo el Core escribe en SQLite; los colectores envían observaciones por HTTP.
- **Sin IA**: todo el comportamiento es determinista y basado en reglas.
- **Sin auth en la demo**: la GUI se accede únicamente por `kubectl port-forward`.
- **Contratos simples**: REST/JSON versionado en `/api/v1`; `/metrics` para Prometheus.

---

## 2. Inventario de componentes

| ID | Componente | Tipo | Responsabilidad principal |
|---|---|---|---|
| C1 | Sentinel Core | Deployable (Deployment) | Proceso central: API, ingesta, inventario, condiciones, métricas, reporte y GUI |
| C2 | API Layer | Módulo de C1 | Exponer REST/JSON `/api/v1`, `/metrics` y rutas `/ui` |
| C3 | IngestionService | Módulo de C1 | Validar y normalizar lotes de discovery, tráfico y ARP |
| C4 | InventoryService | Módulo de C1 | Reconciliar inventario y registrar eventos/cambios |
| C5 | ConditionService | Módulo de C1 | Calcular línea base mínima y condiciones deterministas |
| C6 | MetricsExporter | Módulo de C1 | Proyectar métricas agregadas para Prometheus |
| C7 | ReportService | Módulo de C1 | Generar reporte de red Markdown/PDF bajo demanda |
| C8 | Operator GUI | Módulo de C1 | Vistas Jinja + HTMX para el operador |
| C9 | Discovery Worker | Deployable (CronJob / Job) | Descubrimiento programado o manual sobre hosts autorizados |
| C10 | Traffic Sensor | Deployable (Deployment) | Captura de metadatos IP/ARP con fallback simulado |
| C11 | SQLite Persistence | Recurso (PVC) | Persistencia de activos, observaciones, eventos y ejecuciones |
| C12 | Scope & Config Validator | Módulo compartido | Validar alcance, hosts, puertos y parámetros Helm |
| X1 | Prometheus | Externo | Scraping de `/metrics` y evaluación temporal de reglas |
| X2 | Alertmanager | Externo | Agrupación/silencio/enrutamiento de alertas |
| X3 | Grafana | Externo | Dashboards de inventario, tráfico y salud |
| X4 | Kubernetes API | Externo (solo lectura) | Estado de Pods/Jobs/CronJobs para la vista de salud |

---

## 3. Detalle por componente

### C1 — Sentinel Core
- **Propósito**: único punto de verdad y único escritor de datos.
- **Responsabilidades**: recibir observaciones, normalizarlas, persistirlas, reconciliar inventario, calcular condiciones, publicar métricas, renderizar la GUI y generar reportes.
- **Interfaces**: API HTTP `/api/v1`, `/metrics` (9108), rutas `/ui` (8080).
- **No hace**: capturar paquetes, crear/modificar recursos de Kubernetes, escribir en activos remotos.

### C2 — API Layer
- **Propósito**: contrato HTTP estable para GUI, colectores, Prometheus y exportación.
- **Responsabilidades**: routing, validación de esquema (Pydantic), códigos de estado, OpenAPI, manejo de errores.
- **Interfaces**: endpoints definidos en `component-methods.md`; OpenAPI en `/docs`.

### C3 — IngestionService
- **Propósito**: aceptar observaciones de colectores.
- **Responsabilidades**: validar lote, deduplicar por identidad estable, normalizar MAC/IP/timestamps, delegar a repositorios y disparar reconciliación/condiciones.
- **Interfaces**: `POST /api/v1/ingest`; métodos internos en `component-methods.md`.

### C4 — InventoryService
- **Propósito**: mantener el inventario actual e historial de cambios.
- **Responsabilidades**: comparar observaciones con el inventario previo, emitir `AssetFirstSeen`, `AssetMissing`, `PortServiceChanged`; respetar ciclos fallidos/parciales.
- **Interfaces**: consultas de activos y eventos; invocado por ingesta y GUI.

### C5 — ConditionService
- **Propósito**: convertir observaciones en condiciones deterministas.
- **Responsabilidades**: línea base mínima (subconjunto de M5), umbral `μ + k·s` con fallback absoluto, supresión durante establecimiento, publicación de indicadores.
- **Interfaces**: evaluado tras ingesta; alimenta `MetricsExporter`.

### C6 — MetricsExporter
- **Propósito**: exponer series agregadas para Prometheus.
- **Responsabilidades**: construir el texto de exposición, controlar cardinalidad (sin `src_ip`/`dst_ip`), incluir salud de colectores y ciclos.
- **Interfaces**: `GET /metrics` en el puerto 9108; consumido por ServiceMonitor/Prometheus.

### C7 — ReportService
- **Propósito**: producir el reporte de red bajo demanda.
- **Responsabilidades**: consultar datos por rango, generar secciones (inventario, cambios, top talkers si hay tráfico, alertas, rango de evidencia), renderizar Markdown y convertir a PDF.
- **Interfaces**: `GET /api/v1/report`; botón en la GUI.

### C8 — Operator GUI
- **Propósito**: interfaz de operador simple y agradable.
- **Responsabilidades**: inventario, detalle de activo, eventos/alertas, salud, disparo de discovery, descarga de reporte/export.
- **Interfaces**: rutas `/ui/*`; consume la API del Core; **nunca** accede a SQLite directamente.
- **Acceso**: solo `kubectl port-forward`; sin autenticación en la demo.

### C9 — Discovery Worker
- **Propósito**: ejecutar descubrimiento sobre hosts autorizados.
- **Responsabilidades**: validar alcance, ejecutar ARP/ICMP/TCP + Nmap `-sT -sV --version-light`, normalizar resultados y enviar observaciones al Core; respetar timeout y un ciclo a la vez.
- **Interfaces**: comando `sentinel discovery`; `POST /api/v1/ingest`.
- **Modos**: `scope.mode: explicit_hosts` (laboratorio) o `cidr`.

### C10 — Traffic Sensor
- **Propósito**: capturar metadatos IP/ARP del segmento autorizado.
- **Responsabilidades**: leer del feed/interfaz, agregar ventanas de bytes/s y mensajes ARP/s, enviar lotes al Core; modo fallback con fixtures para la demo.
- **Interfaces**: comando `sentinel sensor`; `POST /api/v1/ingest`.
- **No hace**: inspección de payload, escritura en activos, respuesta automática.

### C11 — SQLite Persistence
- **Propósito**: almacenar inventario, observaciones, eventos, alertas y ejecuciones.
- **Responsabilidades**: esquema versionado, recuperación tras reinicio, consultas para GUI/reporte.
- **Interfaces**: solo a través de repositorios del Core; montado en PVC.

### C12 — Scope & Config Validator
- **Propósito**: garantizar que solo se sondea lo autorizado.
- **Responsabilidades**: validar `scope.mode`, lista de hosts/CIDR, puertos permitidos, timeouts y parámetros Helm.
- **Interfaces**: invocado por Discovery y por la API de disparo; registra `scope_violation`.

### X1–X4 — Externos
- **Prometheus**: scrape de `/metrics`, evaluación de `PrometheusRule`.
- **Alertmanager**: agrupación y enrutamiento; webhook opcional.
- **Grafana**: dashboards sobre Prometheus.
- **Kubernetes API**: solo lectura para estado de salud; el Core nunca crea/modifica recursos.

---

## 4. Fuera de alcance de este diseño

- Reglas de negocio finas y algoritmos completos de baseline (Functional Design).
- Endurecimiento RBAC/NetworkPolicy y capabilities (NFR Design / Infrastructure Design).
- Captura real de paquetes más allá del POC y su fallback.
- Autenticación de operador, multi-sensor, Loki, GitOps y panel de topología.
