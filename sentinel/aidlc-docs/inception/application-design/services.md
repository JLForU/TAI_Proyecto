# Services — Sentinel

**Fase**: INCEPTION — Application Design
**Fecha**: 2026-11-07
**Estado**: GENERATED — pendiente de aprobación
**Patrón**: monolito modular (Q1=A); servicios internos del Core + colectores que llaman por HTTP (Q7=A).

---

## 1. Definición de servicios

| Servicio | Componente | Responsabilidad | Orquesta |
|---|---|---|---|
| IngestionService | C3 | Recibir, validar, normalizar y persistir observaciones | Repositorios, InventoryService, ConditionService |
| InventoryService | C4 | Reconciliar inventario y emitir cambios/eventos | Repositorios |
| ConditionService | C5 | Calcular condiciones deterministas | Repositorios, MetricsExporter |
| MetricsService | C6 | Proyectar y renderizar métricas | ConditionService, repositorios |
| ReportService | C7 | Generar reporte de red bajo demanda | Repositorios, renderizador PDF |
| DiscoveryService | C9/C1 | Ejecutar discovery manual acotado | ScopeValidator, colector de discovery, IngestionService |
| HealthService | C1 | Consolidar salud del sistema | Repositorios, K8s API (solo lectura) |
| GuiService | C8 | Renderizar vistas y delegar acciones | Todos los servicios de consulta/acción |

---

## 2. Orquestación por flujo

### 2.1 Flujo de descubrimiento programado (CronJob)

```text
CronJob -> Discovery Worker -> ScopeValidator -> ARP/ICMP/TCP/Nmap
        -> normaliza lote -> POST /api/v1/ingest -> IngestionService
        -> InventoryService.reconcile -> eventos + inventario -> SQLite
        -> ConditionService (si aplica) -> MetricsExporter
```

- El worker no escribe en SQLite; solo el Core persiste.
- Si el Core no responde, reintenta con backoff hasta lograrlo.

### 2.2 Flujo de descubrimiento manual (GUI)

```text
GUI -> POST /api/v1/discovery -> DiscoveryService.trigger
    -> valida alcance -> lock de ejecución única
    -> run_cycle(hosts, timeout_seconds) en segundo plano
    -> observaciones -> IngestionService -> InventoryService
    -> estado: running -> completed | timeout | failed
```

- Un solo ciclo a la vez (`409` si ya hay uno en ejecución).
- Al cumplirse `discovery.timeout_seconds`, el ciclo se detiene y pasa a `timeout`.

### 2.3 Flujo de ingesta y reconciliación

```text
Lote válido -> deduplicar por event_id -> normalizar
           -> persistir observaciones -> reconciliar inventario
           -> emitir eventos -> evaluar condiciones -> actualizar métricas
```

- Lote inválido: `400/422` con campo inválido; no se persiste parcialmente.

### 2.4 Flujo de consulta (GUI)

```text
GUI -> /ui/assets | /ui/assets/{id} | /ui/events | /ui/alerts | /ui/health
    -> GuiService -> API/servicios de consulta -> repositorios -> HTML (Jinja/HTMX)
```

- Solo lectura; no modifica estado salvo el disparo explícito de discovery.

### 2.5 Flujo de reporte

```text
GUI -> GET /api/v1/report?from&to&format
    -> ReportService.generate -> consultas por rango -> secciones
    -> Markdown -> (opcional) PDF -> descarga
```

- Determinista: mismo rango y filtros producen las mismas secciones.
- Sin datos de tráfico, la sección de top talkers indica `sin datos`.

### 2.6 Flujo de salud

```text
GUI -> /ui/health -> HealthService
    -> estado Core, último ciclo exitoso, heartbeat de colectores
    -> (opcional) K8s API solo lectura para Pods/Jobs/CronJobs
    -> si no hay heartbeat: "sensor caído", nunca "red sin activos"
```

---

## 3. Patrones de orquestación

- **Síncrono HTTP**: GUI y colectores llaman al Core; no hay broker (Q7=A).
- **Reintentos**: backoff simple hasta obtener respuesta del Core.
- **Idempotencia**: `event_id` estable y deduplicación en la ingesta.
- **Lock de ejecución**: un solo discovery manual a la vez.
- **Timeout**: `discovery.timeout_seconds` acota el ciclo y define el estado final.
- **Single writer**: solo el Core escribe SQLite; los colectores nunca abren la base.

---

## 4. Manejo de errores

| Situación | Respuesta | Efecto |
|---|---|---|
| Lote inválido | `400/422` | No persiste; registra el campo inválido |
| Host fuera de alcance | `400` + `scope_violation` | No se ejecuta el sondeo |
| Discovery ya en curso | `409` | No se lanza otro ciclo |
| Timeout de discovery | Estado `timeout` | Se conservan observaciones parciales y se marca el ciclo |
| Core no disponible | Reintento con backoff | El colector no pierde el lote |
| Sensor sin heartbeat | `sensor caído` | No se presenta como red sin activos |
| Sin datos de tráfico | `sin datos` | No se inventan ceros |

---

## 5. Servicios fuera de alcance en esta etapa

- Autenticación de operador (demo sin auth).
- Cola/bus de eventos.
- Worker de reportes separado.
- Orquestación multi-sensor.
