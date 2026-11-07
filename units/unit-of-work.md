# Sentinel — Unidades de trabajo

**Fase:** definición de unidades de trabajo  
**Versión:** 3.0 · **Fecha:** 2026-11-05  
**Fuente de alcance:** `specs/prd.md` · **Fuente técnica:** `specs/arquitectura.md`

## Panorama

Sentinel se descompone en nueve unidades. La división responde a responsabilidades técnicas distintas y a límites verificables; no implica que cada unidad deba desplegarse como microservicio independiente.

| Unidad | Nombre | Tipo | Ruta principal | Historias | Dependencias |
|---|---|---|---|---|---|
| U1 | Base y contratos de dominio | Fundación | `src/sentinel/domain/` | SN-001–005 | — |
| U2 | Plataforma Kubernetes y empaquetado | Plataforma | `deploy/helm/sentinel/` | SN-006–010 | U1 |
| U3 | Descubrimiento de activos | Captura de inventario | `src/sentinel/discovery/` | SN-011–015 | U1, U2 |
| U4 | Sensor de tráfico y ARP | Captura de telemetría | `src/sentinel/traffic/` | SN-016–020 | U1, U2 |
| U5 | Inventario, historial y comparación | Persistencia y correlación temporal | `src/sentinel/inventory/` | SN-021–025 | U3, U4 |
| U6 | Motor de condiciones deterministas | Evaluación determinista | `src/sentinel/conditions/` | SN-026–030 | U5 |
| U7 | Observabilidad y visualización | Plataforma transversal | `deploy/monitoring/` | SN-031–035 | U2, U4, U6 |
| U8 | Seguridad y permisos | Plataforma transversal | `deploy/security/` | SN-036–040 | U2, U3, U4 |
| U9 | Entrega y validación integral | Integración | `.github/workflows/`, `tests/e2e/`, `docs/demo/` | SN-041–047 | U7, U8 |

## Definición de las unidades

### U1 — Base y contratos de dominio

- **Responsabilidad:** establecer estructura del repositorio, modelos tipados, configuración del alcance autorizado, logs estructurados y contrato de métricas.
- **Entradas:** decisiones del PRD y convenciones de implementación.
- **Salidas:** modelos `Asset`, `Observation`, `DiscoveryCycle`, `TrafficWindow`, `ArpObservation`, `InventoryEvent`, `AlertCondition` y configuración validada.
- **Qué NO hace:** no sondea redes, no captura paquetes, no consulta Kubernetes, no persiste datos operativos y no evalúa reglas de negocio.
- **Historias:** SN-001–005.
- **Criterio de frontera:** los modelos y validadores se prueban sin sockets, clúster ni base de datos.
- **Depende de:** ninguna.

### U2 — Plataforma Kubernetes y empaquetado

- **Responsabilidad:** preparar los namespaces, imagen, Helm chart, Deployment del Core, Service, PVC, health checks y cliente Python para consultar el estado de las cargas propias.
- **Entradas:** contratos de U1.
- **Salidas:** Core desplegable, API interna en `8080`, endpoint `/metrics` en `9108`, SQLite sobre PVC y cliente Python que consulta Pods, Jobs y CronJobs con permisos de lectura definidos por U8.
- **Qué NO hace:** no ejecuta descubrimiento ni captura; el Core no crea, actualiza, modifica o elimina recursos Kubernetes; no administra activos externos.
- **Historias:** SN-006–010.
- **Criterio de frontera:** U2 integra el cliente Python de lectura; U8 crea y verifica sus permisos RBAC. La persistencia SQLite tiene un solo escritor.
- **Depende de:** U1.

### U3 — Descubrimiento de activos

- **Responsabilidad:** observar dispositivos dentro de los CIDR autorizados mediante ARP en el mismo dominio de broadcast y sondeos IP/TCP/Nmap limitados; normalizar IP, MAC, puertos, servicios y la certeza de identificación del SO.
- **Entradas:** configuración validada, permisos de red, definición de ciclo y modelos de U1.
- **Salidas:** lote de observaciones de inventario y estado de cobertura del ciclo, enviado al Core por HTTP interno.
- **Qué NO hace:** no sondea rangos o puertos fuera de la allowlist; no instala software en los activos; no inspecciona procesos/configuraciones internas; no compara con el historial y no crea alertas.
- **Historias:** SN-011–015.
- **Criterio de frontera:** el worker produce observaciones de un ciclo; la reconciliación histórica pertenece a U5.
- **Depende de:** U1, U2.

### U4 — Sensor de tráfico y ARP

- **Responsabilidad:** leer PCAP/fixtures o una fuente de captura autorizada, extraer metadatos IP/ARP y calcular agregados de tráfico IP en ventanas de 5 s y tasa de mensajes ARP.
- **Entradas:** fuente de paquetes, interfaz/feed autorizado y modelos/contratos de U1.
- **Salidas:** lote de observaciones y agregados enviado al Core por HTTP interno.
- **Qué NO hace:** no persiste en SQLite directamente, no expone un endpoint Prometheus propio, no compara asociaciones IP↔MAC históricas, no almacena payload, no bloquea/modifica paquetes y no presupone visibilidad de la LAN por el mero hecho de ejecutarse en un Pod.
- **Historias:** SN-016–020.
- **Criterio de frontera:** U4 extrae `op`, `psrc`, `pdst`, `hwsrc`, `hwdst` y datos de paquetes; U5 compara la relación IP↔MAC en el tiempo.
- **Depende de:** U1, U2.

### U5 — Inventario, historial y comparación

- **Responsabilidad:** recibir del Core los datos normalizados de U3/U4, mantener inventario actual e historial SQLite, comparar ciclos completos y exitosos, y registrar cambios de activos, puertos/servicios y asociaciones IP↔MAC.
- **Entradas:** lotes de descubrimiento y telemetría, estado de cobertura, ciclo anterior y repositorio SQLite.
- **Salidas:** eventos `AssetFirstSeen`, `AssetMissing`, `PortServiceChanged`, `ArpMappingChanged` y `TrafficWindowObserved`; exportación estructurada de registros.
- **Qué NO hace:** no marca activos ausentes tras un ciclo fallido/parcial; no convierte eventos en conclusiones de amenaza; no acciona sobre endpoints y no reemplaza la evidencia anterior.
- **Historias:** SN-021–025.
- **Criterio de frontera:** solo esta unidad reconcilia observaciones contra el historial persistido; los colectores no escriben directamente a la base de datos.
- **Depende de:** U3, U4.

### U6 — Motor de condiciones deterministas

- **Responsabilidad:** calcular la línea base inicial según `specs/prd.md`, comparar mediciones e historial con los umbrales configurados y publicar indicadores de condiciones de dominio. Para condiciones derivadas de eventos de U5, utiliza el `event_id` fuente para evitar incrementar dos veces un mismo indicador.
- **Entradas:** agregados de U4, historial/eventos de U5, configuración y catálogo de condiciones/umbrales.
- **Salidas:** indicadores para `TrafficThresholdExceeded`, `ArpRateThresholdExceeded`, `ArpMappingChanged` y `SensorUnavailable`, expuestos por Core a Prometheus.
- **Qué NO hace:** no crea una segunda copia persistente de eventos de U5, no define la duración `for` de una alerta, no mantiene estados firing/resolved, no enruta notificaciones, no clasifica amenazas, no determina intención ni bloquea, contiene o modifica tráfico/endpoints.
- **Historias:** SN-026–030.
- **Criterio de frontera:** U5 conserva el evento fuente y su identidad; U6 calcula condiciones y publica indicadores idempotentes; U7 configura las `PrometheusRule`, evalúa la persistencia temporal y configura Alertmanager. Los umbrales finales permanecen `TBD` hasta el POC.
- **Depende de:** U5.

### U7 — Observabilidad y visualización

- **Responsabilidad:** instalar `kube-prometheus-stack`, configurar scrape pull mediante ServiceMonitor (endpoint por nombre de puerto `metrics`), desplegar dashboards y reglas Prometheus, y configurar agrupación/silencios/enrutamiento en Alertmanager.
- **Entradas:** Core `/metrics`, catálogo de indicadores y servicios Kubernetes.
- **Salidas:** series temporales, dashboards de inventario/tráfico y alertas notificables.
- **Qué NO hace:** no captura ni analiza paquetes, no persiste el inventario fuente, no calcula umbrales de negocio, no agrega IP origen/destino como labels de alta cardinalidad y no presupone que Alertmanager sea visible automáticamente desde Grafana.
- **Historias:** SN-031–035.
- **Criterio de frontera:** los datos detallados IP origen/destino se consultan en eventos/exportaciones; Prometheus conserva métricas agregadas.
- **Depende de:** U2, U4, U6.

### U8 — Seguridad y permisos

- **Responsabilidad:** separar ServiceAccounts, aplicar RBAC mínimo, definir NetworkPolicies según el CNI, endurecer Pods y probar las capabilities estrictamente necesarias para captura.
- **Entradas:** manifiestos de U2, workloads de U3/U4 y requisitos del entorno.
- **Salidas:** roles, bindings, políticas, security contexts y pruebas positivas/negativas.
- **Qué NO hace:** no concede escritura sobre endpoints ni permisos Kubernetes globales, no habilita `privileged: true` y no relaja el namespace principal; cualquier excepción debe quedar aislada en `sentinel-capture` con política de admisión complementaria verificable.
- **Historias:** SN-036–040.
- **Criterio de frontera:** RBAC de Kubernetes y capabilities Linux se validan por separado; una excepción de captura se aísla si el POC la requiere.
- **Depende de:** U2, U3, U4.

### U9 — Entrega y validación integral

- **Responsabilidad:** integrar CI, construcción/escaneo de imágenes, despliegue reproducible, ground truth, pruebas de tráfico/ARP y documentación de demostración.
- **Entradas:** componentes funcionales, reglas, observabilidad y controles de U1–U8.
- **Salidas:** pipeline reproducible, registros de pruebas, evidencias de despliegue y guion de demostración.
- **Qué NO hace:** no añade funcionalidades de gestión/respuesta ni presenta los escenarios de laboratorio como detección general de amenazas.
- **Historias:** SN-041–047.
- **Criterio de frontera:** valida el sistema integrado; no sustituye los criterios unitarios de cada unidad.
- **Depende de:** U7, U8.

## Fronteras arquitectónicas

1. **U3 vs. U5:** U3 descubre y reporta observaciones por ciclo; U5 compara ciclos e historial.
2. **U4 vs. U5:** U4 parsea cada paquete y agrega ventanas; U5 compara asociaciones IP↔MAC históricas. U4 no genera `ArpMappingChanged`.
3. **U4 vs. U7:** U4 envía agregados a Core; Core publica `/metrics`; U7 configura Prometheus para consumirlos.
4. **U5 vs. U6 vs. U7:** U5 registra hechos/cambios con `event_id`; U6 calcula condiciones de dominio e indicadores idempotentes sin duplicar la persistencia; U7 define `PrometheusRule`, evalúa la duración temporal y configura Alertmanager.
5. **U2 vs. U8:** U2 implementa los workloads y el cliente Kubernetes de lectura; U8 define/verifica los permisos y controles de seguridad.
6. **Core vs. colectores:** Core es único escritor SQLite; Discovery Worker y Traffic Sensor envían observaciones por API interna.

## Riesgos transversales que pueden bloquear una unidad

- No disponer de un feed/bridge/SPAN/TAP accesible desde el sensor bloquea la captura real de U4, aunque los tests con PCAP funcionen.
- No validar el comportamiento de `CAP_NET_RAW`, `hostNetwork`, NetworkPolicy y Pod Security en el CNI elegido bloquea la aceptación de seguridad de U8.
- Si la línea base no está disponible, U6 no calcula condiciones que dependan de ella; solo puede evaluar una condición basada en umbral absoluto si está configurada expresamente.
- SQLite exige una sola réplica escritora de Core en el MVP.
