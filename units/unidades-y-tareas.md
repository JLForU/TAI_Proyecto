# Sentinel — Unidades y tareas

**Entregable:** consolidación de Units Generation y Code Generation · **Versión:** 3.0 · **Fecha:** 2026-11-05

> Este documento resume las fronteras y el orden de ejecución. La especificación normativa de cada historia (descripción, criterio de aceptación, evidencia y dependencias) está únicamente en `specs/backlog.md`. La titularidad y cobertura se auditan en `units/unit-of-work-story-map.md`. El plan de implementación detallado de U4 está en `units/U04-captura-trafico-code-generation-plan.md`.

## Panorama de unidades

| Unidad | Responsabilidad | Historias | Depende de |
|---|---|---|---|
| U1 — Base y contratos de dominio | establecer estructura del repositorio, modelos tipados, configuración del alcance autorizado, logs estructurados y contrato de métricas. | SN-001, SN-002, SN-003, SN-004, SN-005 | ninguna. |
| U2 — Plataforma Kubernetes y empaquetado | preparar los namespaces, imagen, Helm chart, Deployment del Core, Service, PVC, health checks y cliente Python para consultar el estado de las cargas propias. | SN-006, SN-007, SN-008, SN-009, SN-010 | U1. |
| U3 — Descubrimiento de activos | observar dispositivos dentro de los CIDR autorizados mediante ARP en el mismo dominio de broadcast y sondeos IP/TCP/Nmap limitados; normalizar IP, MAC, puertos, servicios y la certeza de identificación del SO. | SN-011, SN-012, SN-013, SN-014, SN-015 | U1, U2. |
| U4 — Sensor de tráfico y ARP | leer PCAP/fixtures o una fuente de captura autorizada, extraer metadatos IP/ARP y calcular agregados de tráfico IP en ventanas de 5 s y tasa de mensajes ARP. | SN-016, SN-017, SN-018, SN-019, SN-020 | U1, U2. |
| U5 — Inventario, historial y comparación | recibir del Core los datos normalizados de U3/U4, mantener inventario actual e historial SQLite, comparar ciclos completos y exitosos, y registrar cambios de activos, puertos/servicios y asociaciones IP↔MAC. | SN-021, SN-022, SN-023, SN-024, SN-025 | U3, U4. |
| U6 — Motor de condiciones deterministas | transformar mediciones e historial en indicadores de dominio reproducibles, sin duplicar eventos persistidos ni mantener el ciclo de vida de las alertas. | SN-026, SN-027, SN-028, SN-029, SN-030 | U5. |
| U7 — Observabilidad y visualización | instalar `kube-prometheus-stack`, configurar scrape pull mediante ServiceMonitor (endpoint por nombre de puerto `metrics`), desplegar dashboards y reglas Prometheus, y configurar agrupación/silencios/enrutamiento en Alertmanager. | SN-031, SN-032, SN-033, SN-034, SN-035 | U2, U4, U6. |
| U8 — Seguridad y permisos | separar ServiceAccounts, aplicar RBAC mínimo, definir NetworkPolicies según el CNI, endurecer Pods y probar las capabilities estrictamente necesarias para captura. | SN-036, SN-037, SN-038, SN-039, SN-040 | U2, U3, U4. |
| U9 — Entrega y validación integral | integrar CI, construcción/escaneo de imágenes, despliegue reproducible, ground truth, pruebas de tráfico/ARP y documentación de demostración. | SN-041, SN-042, SN-043, SN-044, SN-045, SN-046, SN-047 | U7, U8. |

## Definición operativa y tareas

### U1 — Base y contratos de dominio

- **Responsabilidad:** establecer estructura del repositorio, modelos tipados, configuración del alcance autorizado, logs estructurados y contrato de métricas.
- **Entradas:** decisiones del PRD y convenciones de implementación.
- **Salidas:** modelos `Asset`, `Observation`, `DiscoveryCycle`, `TrafficWindow`, `ArpObservation`, `InventoryEvent`, `AlertCondition` y configuración validada.
- **Qué NO hace:** no sondea redes, no captura paquetes, no consulta Kubernetes, no persiste datos operativos y no evalúa reglas de negocio.
- **Criterio de frontera:** los modelos y validadores se prueban sin sockets, clúster ni base de datos.
- **Historias:** SN-001, SN-002, SN-003, SN-004, SN-005
- **Depende de:** ninguna.

**Tareas trazadas:**

| Orden | Tarea | Historia | Predecesoras directas | Comprobación resumida |
|---:|---|---|---|---|
| 1 | Crear estructura de repositorio | SN-001 | — | tree -L 3 |
| 2 | Definir contratos de dominio | SN-002 | SN-001 | pytest -q tests/unit/test_models.py |
| 3 | Validar configuración de alcance | SN-003 | SN-002 | pytest -q tests/unit/test_config.py |
| 4 | Crear logger JSON | SN-004 | SN-002 | pytest -q tests/unit/test_logging.py |
| 5 | Definir contrato de métricas | SN-005 | SN-002 | pytest -q tests/unit/test_metrics_contract.py |

**Puerta de salida:** todas las historias de U1 cumplen íntegramente los criterios y evidencias de `specs/backlog.md`.

### U2 — Plataforma Kubernetes y empaquetado

- **Responsabilidad:** preparar los namespaces, imagen, Helm chart, Deployment del Core, Service, PVC, health checks y cliente Python para consultar el estado de las cargas propias.
- **Entradas:** contratos de U1.
- **Salidas:** Core desplegable, API interna en `8080`, endpoint `/metrics` en `9108`, SQLite sobre PVC y cliente Python que consulta Pods, Jobs y CronJobs con permisos de lectura definidos por U8.
- **Qué NO hace:** no ejecuta descubrimiento ni captura; el Core no crea, actualiza, modifica o elimina recursos Kubernetes; no administra activos externos.
- **Criterio de frontera:** U2 integra el cliente Python de lectura; U8 crea y verifica sus permisos RBAC. La persistencia SQLite tiene un solo escritor.
- **Historias:** SN-006, SN-007, SN-008, SN-009, SN-010
- **Depende de:** U1.

**Tareas trazadas:**

| Orden | Tarea | Historia | Predecesoras directas | Comprobación resumida |
|---:|---|---|---|---|
| 1 | Preparar clúster y namespaces | SN-006 | SN-001 | kubectl get ns sentinel monitoring |
| 2 | Empaquetar la imagen común de Sentinel | SN-007 | SN-001, SN-002 | docker build -t sentinel:test . |
| 3 | Definir Helm chart de Sentinel | SN-008 | SN-006, SN-007 | helm lint deploy/helm/sentinel |
| 4 | Desplegar Core y PVC | SN-009 | SN-008 | kubectl rollout status deploy/sentinel-core -n sentinel |
| 5 | Consultar estado de cargas desde Python | SN-010 | SN-009 | pytest -q tests/integration/test_kubernetes_readonly_client.py |

**Puerta de salida:** todas las historias de U2 cumplen íntegramente los criterios y evidencias de `specs/backlog.md`.

### U3 — Descubrimiento de activos

- **Responsabilidad:** observar dispositivos dentro de los CIDR autorizados mediante ARP en el mismo dominio de broadcast y sondeos IP/TCP/Nmap limitados; normalizar IP, MAC, puertos, servicios y la certeza de identificación del SO.
- **Entradas:** configuración validada, permisos de red, definición de ciclo y modelos de U1.
- **Salidas:** lote de observaciones de inventario y estado de cobertura del ciclo, enviado al Core por HTTP interno.
- **Qué NO hace:** no sondea rangos o puertos fuera de la allowlist; no instala software en los activos; no inspecciona procesos/configuraciones internas; no compara con el historial y no crea alertas.
- **Criterio de frontera:** el worker produce observaciones de un ciclo; la reconciliación histórica pertenece a U5.
- **Historias:** SN-011, SN-012, SN-013, SN-014, SN-015
- **Depende de:** U1, U2.

**Tareas trazadas:**

| Orden | Tarea | Historia | Predecesoras directas | Comprobación resumida |
|---:|---|---|---|---|
| 1 | Implementar descubrimiento ARP | SN-011 | SN-002, SN-003, SN-006, SN-007 | pytest -q tests/unit/test_arp_discovery.py |
| 2 | Implementar verificación de host | SN-012 | SN-003, SN-011 | pytest -q tests/unit/test_host_probe.py |
| 3 | Integrar Nmap con allowlist | SN-013 | SN-003, SN-007 | pytest -q tests/unit/test_nmap_command.py |
| 4 | Normalizar puertos y servicios | SN-014 | SN-013 | pytest -q tests/unit/test_service_parse.py |
| 5 | Registrar certeza del SO | SN-015 | SN-013, SN-014 | pytest -q tests/unit/test_os_confidence.py |

**Puerta de salida:** todas las historias de U3 cumplen íntegramente los criterios y evidencias de `specs/backlog.md`.

### U4 — Sensor de tráfico y ARP

- **Responsabilidad:** leer PCAP/fixtures o una fuente de captura autorizada, extraer metadatos IP/ARP y calcular agregados de tráfico IP en ventanas de 5 s y tasa de mensajes ARP.
- **Entradas:** fuente de paquetes, interfaz/feed autorizado y modelos/contratos de U1.
- **Salidas:** lote de observaciones y agregados enviado al Core por HTTP interno.
- **Qué NO hace:** no persiste en SQLite directamente, no expone un endpoint Prometheus propio, no compara asociaciones IP↔MAC históricas, no almacena payload, no bloquea/modifica paquetes y no presupone visibilidad de la LAN por el mero hecho de ejecutarse en un Pod.
- **Criterio de frontera:** U4 extrae `op`, `psrc`, `pdst`, `hwsrc`, `hwdst` y datos de paquetes; U5 compara la relación IP↔MAC en el tiempo.
- **Historias:** SN-016, SN-017, SN-018, SN-019, SN-020
- **Depende de:** U1, U2.

**Tareas trazadas:**

| Orden | Tarea | Historia | Predecesoras directas | Comprobación resumida |
|---:|---|---|---|---|
| 1 | Crear abstracción de fuente de paquetes | SN-016 | SN-002 | pytest -q tests/unit/test_packet_source.py |
| 2 | Implementar parser de paquetes | SN-017 | SN-016 | pytest -q tests/unit/test_packet_parser.py |
| 3 | Agregar tráfico en ventanas | SN-018 | SN-017, SN-005 | pytest -q tests/unit/test_traffic_aggregation.py |
| 4 | Integrar agregados de tráfico en métricas de Core | SN-019 | SN-018, SN-005 | kubectl port-forward svc/sentinel-core 9108:9108 -n sentinel |
| 5 | Probar captura en interfaz de laboratorio | SN-020 | SN-016, SN-017, SN-006, SN-007 | Un test de integración registra tráfico conocido en la fuente seleccionada, entrega las observaciones a Core por el p… |

**Puerta de salida:** todas las historias de U4 cumplen íntegramente los criterios y evidencias de `specs/backlog.md`.

### U5 — Inventario, historial y comparación

- **Responsabilidad:** recibir del Core los datos normalizados de U3/U4, mantener inventario actual e historial SQLite, comparar ciclos completos y exitosos, y registrar cambios de activos, puertos/servicios y asociaciones IP↔MAC.
- **Entradas:** lotes de descubrimiento y telemetría, estado de cobertura, ciclo anterior y repositorio SQLite.
- **Salidas:** eventos `AssetFirstSeen`, `AssetMissing`, `PortServiceChanged`, `ArpMappingChanged` y `TrafficWindowObserved`; exportación estructurada de registros.
- **Qué NO hace:** no marca activos ausentes tras un ciclo fallido/parcial; no convierte eventos en conclusiones de amenaza; no acciona sobre endpoints y no reemplaza la evidencia anterior.
- **Criterio de frontera:** solo esta unidad reconcilia observaciones contra el historial persistido; los colectores no escriben directamente a la base de datos.
- **Historias:** SN-021, SN-022, SN-023, SN-024, SN-025
- **Depende de:** U3, U4.

**Tareas trazadas:**

| Orden | Tarea | Historia | Predecesoras directas | Comprobación resumida |
|---:|---|---|---|---|
| 1 | Persistir inventario SQLite | SN-021 | SN-002, SN-009, SN-011 | pytest -q tests/integration/test_inventory_repository.py |
| 2 | Comparar observaciones | SN-022 | SN-021, SN-015 | pytest -q tests/unit/test_inventory_diff.py |
| 3 | Registrar cambios IP↔MAC | SN-023 | SN-011, SN-017, SN-021 | pytest -q tests/unit/test_arp_change.py |
| 4 | Guardar eventos de tráfico | SN-024 | SN-018, SN-021 | pytest -q tests/unit/test_traffic_event_store.py |
| 5 | Definir retención y exportación | SN-025 | SN-021, SN-022, SN-024 | pytest -q tests/integration/test_export_retention.py |

**Puerta de salida:** todas las historias de U5 cumplen íntegramente los criterios y evidencias de `specs/backlog.md`.

### U6 — Motor de condiciones deterministas

- **Responsabilidad:** aplicar las condiciones deterministas definidas en el PRD y publicar sus indicadores de forma idempotente. La definición normativa y sus límites están en [`unit-of-work.md`](unit-of-work.md#u6--motor-de-condiciones-deterministas).
- **Entradas:** agregados de U4, historial/eventos de U5, configuración y catálogo de condiciones/umbrales.
- **Salidas:** indicadores para `TrafficThresholdExceeded`, `ArpRateThresholdExceeded`, `ArpMappingChanged` y `SensorUnavailable`, expuestos por Core a Prometheus.
- **Qué NO hace:** no crea una segunda copia persistente de eventos de U5, no define la duración `for` de una alerta, no mantiene estados firing/resolved, no enruta notificaciones, no clasifica amenazas, no determina intención ni bloquea, contiene o modifica tráfico/endpoints.
- **Historias:** SN-026–030.
- **Criterio de frontera:** U5 conserva el evento fuente y su identidad; U6 calcula condiciones y publica indicadores idempotentes; U7 configura las `PrometheusRule`, evalúa la persistencia temporal y configura Alertmanager. Los umbrales finales permanecen `TBD` hasta el POC.
- **Depende de:** U5.

**Tareas trazadas:**

| Orden | Tarea | Historia | Predecesoras directas | Comprobación resumida |
|---:|---|---|---|---|
| 1 | Definir catálogo de condiciones y umbrales | SN-026 | SN-002, SN-003 | pytest -q tests/unit/test_conditions_config.py |
| 2 | Calcular condición de tráfico elevado | SN-027 | SN-018, SN-026 | pytest -q tests/unit/test_traffic_condition.py |
| 3 | Calcular condiciones ARP observadas | SN-028 | SN-018, SN-023, SN-026 | pytest -q tests/unit/test_arp_conditions.py |
| 4 | Calcular disponibilidad del Traffic Sensor | SN-029 | SN-005, SN-016, SN-019, SN-026 | pytest -q tests/unit/test_collector_health_condition.py |
| 5 | Garantizar idempotencia de indicadores derivados | SN-030 | SN-027, SN-028, SN-029 | pytest -q tests/unit/test_condition_metric_idempotency.py |

**Puerta de salida:** todas las historias de U6 cumplen íntegramente los criterios y evidencias de `specs/backlog.md`.

### U7 — Observabilidad y visualización

- **Responsabilidad:** instalar `kube-prometheus-stack`, configurar scrape pull mediante ServiceMonitor (endpoint por nombre de puerto `metrics`), desplegar dashboards y reglas Prometheus, y configurar agrupación/silencios/enrutamiento en Alertmanager.
- **Entradas:** Core `/metrics`, catálogo de indicadores y servicios Kubernetes.
- **Salidas:** series temporales, dashboards de inventario/tráfico y alertas notificables.
- **Qué NO hace:** no captura ni analiza paquetes, no persiste el inventario fuente, no calcula umbrales de negocio, no agrega IP origen/destino como labels de alta cardinalidad y no presupone que Alertmanager sea visible automáticamente desde Grafana.
- **Criterio de frontera:** los datos detallados IP origen/destino se consultan en eventos/exportaciones; Prometheus conserva métricas agregadas.
- **Historias:** SN-031, SN-032, SN-033, SN-034, SN-035
- **Depende de:** U2, U4, U6.

**Tareas trazadas:**

| Orden | Tarea | Historia | Predecesoras directas | Comprobación resumida |
|---:|---|---|---|---|
| 1 | Instalar kube-prometheus-stack | SN-031 | SN-006 | helm upgrade --install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f deploy/monitoring/values.yaml --dry-run |
| 2 | Registrar ServiceMonitor | SN-032 | SN-019, SN-031 | kubectl get servicemonitor -n sentinel |
| 3 | Crear dashboard de inventario | SN-033 | SN-022, SN-032 | python scripts/validate_dashboard.py dashboards/inventory.json |
| 4 | Crear dashboard de tráfico | SN-034 | SN-019, SN-032 | python scripts/validate_dashboard.py dashboards/traffic.json |
| 5 | Publicar reglas Prometheus | SN-035 | SN-026, SN-031, SN-032, SN-030 | promtool check rules deploy/monitoring/rules/sentinel.yml |

**Puerta de salida:** todas las historias de U7 cumplen íntegramente los criterios y evidencias de `specs/backlog.md`.

### U8 — Seguridad y permisos

- **Responsabilidad:** separar ServiceAccounts, aplicar RBAC mínimo, definir NetworkPolicies según el CNI, endurecer Pods y probar las capabilities estrictamente necesarias para captura.
- **Entradas:** manifiestos de U2, workloads de U3/U4 y requisitos del entorno.
- **Salidas:** roles, bindings, políticas, security contexts y pruebas positivas/negativas.
- **Qué NO hace:** no concede escritura sobre endpoints ni permisos Kubernetes globales, no habilita `privileged: true` y no relaja el namespace principal; cualquier excepción queda aislada en `sentinel-capture` con política de admisión complementaria verificable.
- **Criterio de frontera:** RBAC de Kubernetes y capabilities Linux se validan por separado; una excepción de captura se aísla si el POC la requiere.
- **Historias:** SN-036, SN-037, SN-038, SN-039, SN-040
- **Depende de:** U2, U3, U4.

**Tareas trazadas:**

| Orden | Tarea | Historia | Predecesoras directas | Comprobación resumida |
|---:|---|---|---|---|
| 1 | Crear ServiceAccounts separadas | SN-036 | SN-006, SN-009 | kubectl get sa -n sentinel |
| 2 | Aplicar RBAC mínimo | SN-037 | SN-036 | kubectl auth can-i get/list/watch |
| 3 | Aislar red interna del namespace | SN-038 | SN-006, SN-009 | kubectl get networkpolicy -n sentinel |
| 4 | Restringir capabilities de los colectores | SN-039 | SN-013, SN-020, SN-036 | se inspeccionan los securityContext del CronJob de descubrimiento y del Deployment del sensor |
| 5 | Probar ausencia de acciones de escritura | SN-040 | SN-013, SN-017, SN-037 | pytest -q tests/security/test_read_only_boundary.py |

**Puerta de salida:** todas las historias de U8 cumplen íntegramente los criterios y evidencias de `specs/backlog.md`.

### U9 — Entrega y validación integral

- **Responsabilidad:** integrar CI, construcción/escaneo de imágenes, despliegue reproducible, ground truth, pruebas de tráfico/ARP y documentación de demostración.
- **Entradas:** componentes funcionales, reglas, observabilidad y controles de U1–U8.
- **Salidas:** pipeline reproducible, registros de pruebas, evidencias de despliegue y guion de demostración.
- **Qué NO hace:** no añade funcionalidades de gestión/respuesta ni presenta los escenarios de laboratorio como detección general de amenazas.
- **Criterio de frontera:** valida el sistema integrado; no sustituye los criterios unitarios de cada unidad.
- **Historias:** SN-041, SN-042, SN-043, SN-044, SN-045, SN-046, SN-047
- **Depende de:** U7, U8.

**Tareas trazadas:**

| Orden | Tarea | Historia | Predecesoras directas | Comprobación resumida |
|---:|---|---|---|---|
| 1 | Configurar pipeline CI | SN-041 | SN-001, SN-008 | El workflow ejecuta pytest, lint y helm lint; un PR con fallo queda no aprobado. |
| 2 | Escanear la imagen común de Sentinel | SN-042 | SN-007, SN-041 | CI construye una imagen sentinel:<tag-inmutable> reutilizada por Core y colectores y genera reporte de scanner/SBOM; … |
| 3 | Desplegar manifests por GitOps | SN-043 | SN-008, SN-031, SN-041 | Si Argo CD está habilitado, Application queda Synced/Healthy tras commit; si se excluye, queda documentado el procedi… |
| 4 | Construir ground truth de laboratorio | SN-044 | SN-011, SN-018 | pytest -q tests/e2e/test_ground_truth.py |
| 5 | Ejecutar prueba de tráfico alto | SN-045 | SN-020, SN-027, SN-034, SN-044 | un generador de prueba controlado produce una tasa por encima del umbral; la condición y alerta aparecen dentro de la… |
| 6 | Ejecutar prueba ARP controlada | SN-046 | SN-018, SN-020, SN-028, SN-033, SN-044 | en una red aislada, dos dispositivos Android, un equipo macOS y un equipo Windows consultan la página HTTP del servid… |
| 7 | Preparar sustentación y límites | SN-047 | SN-035, SN-039, SN-040, SN-043, SN-045, SN-046 | checklist documenta despliegue, permisos, casos positivos/negativos, topología (cinco activos base y un sexto activo … |

**Puerta de salida:** todas las historias de U9 cumplen íntegramente los criterios y evidencias de `specs/backlog.md`.

## Secuencia de construcción recomendada

1. **Fundación:** U1 y U2; establecer contratos, construir la imagen común y desplegar Core/PVC.
2. **Recolección en paralelo:** U3 y U4 tras completar U2; ejecutar desde el principio el POC de visibilidad de red.
3. **Persistencia y comparación:** U5; reconciliar únicamente ciclos completos y exitosos.
4. **Condiciones y seguridad de plataforma:** U6 y U8; U8 puede avanzar en paralelo tan pronto existan manifiestos y workloads.
5. **Observabilidad:** U7; configurar scraping pull, reglas, dashboards y Alertmanager.
6. **Integración:** U9; cerrar CI/CD, despliegue declarativo, escenarios controlados y evidencias.

## Camino crítico

El grafo de unidades se verifica con `python scripts/verify_unit_dag.py`. Una ruta de mayor profundidad es `U1 → U2 → U3 → U5 → U6 → U7 → U9`; otra ruta equivalente sustituye U3 por U4. U8 es una rama obligatoria que debe completarse antes de U9.

La cadena crítica del backlog se calcula con `python scripts/verify_traceability.py`; no debe inferirse concatenando rangos de historias. El script imprime la secuencia resultante y falla ante dependencias inexistentes, asignaciones incorrectas o ciclos.

## Walking skeleton

1. Crear contratos de dominio y configuración autorizada.
2. Desplegar Core en Kubernetes con SQLite/PVC y puertos internos `8080` y `9108`.
3. Ejecutar descubrimiento con fixtures y enviar observaciones al Core.
4. Procesar PCAP sintético y enviar agregados IP/ARP al Core.
5. Persistir datos y comparar dos ciclos completos.
6. Publicar métricas en Core y comprobar el scrape HTTP GET de Prometheus.
7. Evaluar una condición de prueba y comprobar el flujo Prometheus → Alertmanager.
8. Consultar en Grafana métricas agregadas y obtener detalle CSV/JSON desde Core.
9. Validar una fuente de captura real antes de presentar cobertura de LAN.

## Límites de aceptación global

- Cero escrituras intencionales sobre los activos monitorizados.
- Todo sondeo se limita a rangos/puertos autorizados, con rate limit y timeout.
- El SO se registra con método/certeza; `desconocido` cuando no hay evidencia suficiente.
- No se persiste payload completo.
- ARP se contabiliza por separado de bytes/s IP.
- Una ausencia se registra solo tras ciclos completos y exitosos.
- Core es el único escritor SQLite.
- Prometheus no recibe IP origen/destino como labels de alta cardinalidad.
- Ninguna gráfica o alerta atribuye por sí sola intención maliciosa.
- RBAC Kubernetes y capabilities Linux se verifican por separado.
- No se utiliza `privileged: true` como atajo.
- Prometheus realiza scrape pull de `/metrics`; los colectores entregan observaciones al Core.
- U5 conserva el evento fuente y su `event_id`; U6 proyecta ese hecho una sola vez en indicadores; Prometheus evalúa reglas y mantiene el estado temporal; Alertmanager agrupa, silencia y enruta notificaciones.
- Los controles de seguridad del despliegue protegen Sentinel y no modifican los endpoints observados.
- Cada historia se cierra con criterio y evidencia completos del backlog.

## Archivos normativos y verificadores

- PRD: `specs/prd.md`.
- Arquitectura: `specs/arquitectura.md`.
- Backlog normativo: `specs/backlog.md`.
- Definición de unidades: `units/unit-of-work.md`.
- Grafo: `units/unit-of-work-dependency.md`.
- Mapa de historias: `units/unit-of-work-story-map.md`.
- Plan de construcción de U4: `units/U04-captura-trafico-code-generation-plan.md`.
- Validación: `scripts/verify_unit_dag.py` y `scripts/verify_traceability.py`.
