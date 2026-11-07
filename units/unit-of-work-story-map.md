# Sentinel — Mapa de historias por unidad

**Fase:** trazabilidad de unidades · **Versión:** 3.0 · **Fecha:** 2026-11-05

## Regla de titularidad

- Cada historia del backlog tiene una única unidad primaria.
- Las dependencias compartidas no duplican la titularidad.
- `specs/backlog.md` es la fuente normativa del texto, los criterios completos y las evidencias.
- Este mapa presenta cobertura y trazabilidad, sin copiar nuevamente la especificación completa.

## Cobertura por unidad

| Unidad | Historias | Cantidad |
|---|---|---:|
| U1 — Base y contratos de dominio | SN-001, SN-002, SN-003, SN-004, SN-005 | 5 |
| U2 — Plataforma Kubernetes y empaquetado | SN-006, SN-007, SN-008, SN-009, SN-010 | 5 |
| U3 — Descubrimiento de activos | SN-011, SN-012, SN-013, SN-014, SN-015 | 5 |
| U4 — Sensor de tráfico y ARP | SN-016, SN-017, SN-018, SN-019, SN-020 | 5 |
| U5 — Inventario, historial y comparación | SN-021, SN-022, SN-023, SN-024, SN-025 | 5 |
| U6 — Motor de condiciones deterministas | SN-026, SN-027, SN-028, SN-029, SN-030 | 5 |
| U7 — Observabilidad y visualización | SN-031, SN-032, SN-033, SN-034, SN-035 | 5 |
| U8 — Seguridad y permisos | SN-036, SN-037, SN-038, SN-039, SN-040 | 5 |
| U9 — Entrega y validación integral | SN-041, SN-042, SN-043, SN-044, SN-045, SN-046, SN-047 | 7 |

**Total:** 47 historias con titularidad única.

## Matriz de verificación

| Historia (backlog normativo) | Unidad | Comprobación resumida | Evidencia | Dependencias |
|---|---|---|---|---|
| [ SN-001 — Crear estructura de repositorio ](../specs/backlog.md#sn-001--crear-estructura-de-repositorio) | U1 | tree -L 3 | Véase evidencia íntegra de SN-001 en el backlog | — |
| [ SN-002 — Definir contratos de dominio ](../specs/backlog.md#sn-002--definir-contratos-de-dominio) | U1 | pytest -q tests/unit/test_models.py | Véase evidencia íntegra de SN-002 en el backlog | SN-001 |
| [ SN-003 — Validar configuración de alcance ](../specs/backlog.md#sn-003--validar-configuración-de-alcance) | U1 | pytest -q tests/unit/test_config.py | Véase evidencia íntegra de SN-003 en el backlog | SN-002 |
| [ SN-004 — Crear logger JSON ](../specs/backlog.md#sn-004--crear-logger-json) | U1 | pytest -q tests/unit/test_logging.py | Véase evidencia íntegra de SN-004 en el backlog | SN-002 |
| [ SN-005 — Definir contrato de métricas ](../specs/backlog.md#sn-005--definir-contrato-de-métricas) | U1 | pytest -q tests/unit/test_metrics_contract.py | Véase evidencia íntegra de SN-005 en el backlog | SN-002 |
| [ SN-006 — Preparar clúster y namespaces ](../specs/backlog.md#sn-006--preparar-clúster-y-namespaces) | U2 | kubectl get ns sentinel monitoring | Véase evidencia íntegra de SN-006 en el backlog | SN-001 |
| [ SN-007 — Empaquetar la imagen común de Sentinel ](../specs/backlog.md#sn-007--empaquetar-la-imagen-común-de-sentinel) | U2 | docker build -t sentinel:test . | Véase evidencia íntegra de SN-007 en el backlog | SN-001, SN-002 |
| [ SN-008 — Definir Helm chart de Sentinel ](../specs/backlog.md#sn-008--definir-helm-chart-de-sentinel) | U2 | helm lint deploy/helm/sentinel | Véase evidencia íntegra de SN-008 en el backlog | SN-006, SN-007 |
| [ SN-009 — Desplegar Core y PVC ](../specs/backlog.md#sn-009--desplegar-core-y-pvc) | U2 | kubectl rollout status deploy/sentinel-core -n sentinel | Véase evidencia íntegra de SN-009 en el backlog | SN-008 |
| [ SN-010 — Consultar estado de cargas desde Python ](../specs/backlog.md#sn-010--consultar-estado-de-cargas-desde-python) | U2 | pytest -q tests/integration/test_kubernetes_readonly_client.py | Véase evidencia íntegra de SN-010 en el backlog | SN-009 |
| [ SN-011 — Implementar descubrimiento ARP ](../specs/backlog.md#sn-011--implementar-descubrimiento-arp) | U3 | pytest -q tests/unit/test_arp_discovery.py | Véase evidencia íntegra de SN-011 en el backlog | SN-002, SN-003, SN-006, SN-007 |
| [ SN-012 — Implementar verificación de host ](../specs/backlog.md#sn-012--implementar-verificación-de-host) | U3 | pytest -q tests/unit/test_host_probe.py | Véase evidencia íntegra de SN-012 en el backlog | SN-003, SN-011 |
| [ SN-013 — Integrar Nmap con allowlist ](../specs/backlog.md#sn-013--integrar-nmap-con-allowlist) | U3 | pytest -q tests/unit/test_nmap_command.py | Véase evidencia íntegra de SN-013 en el backlog | SN-003, SN-007 |
| [ SN-014 — Normalizar puertos y servicios ](../specs/backlog.md#sn-014--normalizar-puertos-y-servicios) | U3 | pytest -q tests/unit/test_service_parse.py | Véase evidencia íntegra de SN-014 en el backlog | SN-013 |
| [ SN-015 — Registrar certeza del SO ](../specs/backlog.md#sn-015--registrar-certeza-del-so) | U3 | pytest -q tests/unit/test_os_confidence.py | Véase evidencia íntegra de SN-015 en el backlog | SN-013, SN-014 |
| [ SN-016 — Crear abstracción de fuente de paquetes ](../specs/backlog.md#sn-016--crear-abstracción-de-fuente-de-paquetes) | U4 | pytest -q tests/unit/test_packet_source.py | Véase evidencia íntegra de SN-016 en el backlog | SN-002 |
| [ SN-017 — Implementar parser de paquetes ](../specs/backlog.md#sn-017--implementar-parser-de-paquetes) | U4 | pytest -q tests/unit/test_packet_parser.py | Véase evidencia íntegra de SN-017 en el backlog | SN-016 |
| [ SN-018 — Agregar tráfico en ventanas ](../specs/backlog.md#sn-018--agregar-tráfico-en-ventanas) | U4 | pytest -q tests/unit/test_traffic_aggregation.py | Véase evidencia íntegra de SN-018 en el backlog | SN-017, SN-005 |
| [ SN-019 — Integrar agregados de tráfico en métricas de Core ](../specs/backlog.md#sn-019--integrar-agregados-de-tráfico-en-métricas-de-core) | U4 | kubectl port-forward svc/sentinel-core 9108:9108 -n sentinel | Véase evidencia íntegra de SN-019 en el backlog | SN-018, SN-005 |
| [ SN-020 — Probar captura en interfaz de laboratorio ](../specs/backlog.md#sn-020--probar-captura-en-interfaz-de-laboratorio) | U4 | Un test de integración registra tráfico conocido en la fuente seleccionada, entrega las observaciones a Core por el p… | Véase evidencia íntegra de SN-020 en el backlog | SN-016, SN-017, SN-006, SN-007 |
| [ SN-021 — Persistir inventario SQLite ](../specs/backlog.md#sn-021--persistir-inventario-sqlite) | U5 | pytest -q tests/integration/test_inventory_repository.py | Véase evidencia íntegra de SN-021 en el backlog | SN-002, SN-009, SN-011 |
| [ SN-022 — Comparar observaciones ](../specs/backlog.md#sn-022--comparar-observaciones) | U5 | pytest -q tests/unit/test_inventory_diff.py | Véase evidencia íntegra de SN-022 en el backlog | SN-021, SN-015 |
| [ SN-023 — Registrar cambios IP↔MAC ](../specs/backlog.md#sn-023--registrar-cambios-ipmac) | U5 | pytest -q tests/unit/test_arp_change.py | Véase evidencia íntegra de SN-023 en el backlog | SN-011, SN-017, SN-021 |
| [ SN-024 — Guardar eventos de tráfico ](../specs/backlog.md#sn-024--guardar-eventos-de-tráfico) | U5 | pytest -q tests/unit/test_traffic_event_store.py | Véase evidencia íntegra de SN-024 en el backlog | SN-018, SN-021 |
| [ SN-025 — Definir retención y exportación ](../specs/backlog.md#sn-025--definir-retención-y-exportación) | U5 | pytest -q tests/integration/test_export_retention.py | Véase evidencia íntegra de SN-025 en el backlog | SN-021, SN-022, SN-024 |
| [ SN-026 — Definir catálogo de condiciones y umbrales ](../specs/backlog.md#sn-026--definir-catálogo-de-condiciones-y-umbrales) | U6 | pytest -q tests/unit/test_conditions_config.py | Véase evidencia íntegra de SN-026 en el backlog | SN-002, SN-003 |
| [ SN-027 — Calcular condición de tráfico elevado ](../specs/backlog.md#sn-027--calcular-condición-de-tráfico-elevado) | U6 | pytest -q tests/unit/test_traffic_condition.py | Véase evidencia íntegra de SN-027 en el backlog | SN-018, SN-026 |
| [ SN-028 — Calcular condiciones ARP observadas ](../specs/backlog.md#sn-028--calcular-condiciones-arp-observadas) | U6 | pytest -q tests/unit/test_arp_conditions.py | Véase evidencia íntegra de SN-028 en el backlog | SN-018, SN-023, SN-026 |
| [ SN-029 — Calcular disponibilidad del Traffic Sensor ](../specs/backlog.md#sn-029--calcular-disponibilidad-del-traffic-sensor) | U6 | pytest -q tests/unit/test_collector_health_condition.py | Véase evidencia íntegra de SN-029 en el backlog | SN-005, SN-016, SN-019, SN-026 |
| [ SN-030 — Garantizar idempotencia de indicadores derivados ](../specs/backlog.md#sn-030--garantizar-idempotencia-de-indicadores-derivados) | U6 | pytest -q tests/unit/test_condition_metric_idempotency.py | Véase evidencia íntegra de SN-030 en el backlog | SN-027, SN-028, SN-029 |
| [ SN-031 — Instalar kube-prometheus-stack ](../specs/backlog.md#sn-031--instalar-kube-prometheus-stack) | U7 | helm upgrade --install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f deploy/monitoring/values.yaml --dry-run | Véase evidencia íntegra de SN-031 en el backlog | SN-006 |
| [ SN-032 — Registrar ServiceMonitor ](../specs/backlog.md#sn-032--registrar-servicemonitor) | U7 | kubectl get servicemonitor -n sentinel | Véase evidencia íntegra de SN-032 en el backlog | SN-019, SN-031 |
| [ SN-033 — Crear dashboard de inventario ](../specs/backlog.md#sn-033--crear-dashboard-de-inventario) | U7 | python scripts/validate_dashboard.py dashboards/inventory.json | Véase evidencia íntegra de SN-033 en el backlog | SN-022, SN-032 |
| [ SN-034 — Crear dashboard de tráfico ](../specs/backlog.md#sn-034--crear-dashboard-de-tráfico) | U7 | python scripts/validate_dashboard.py dashboards/traffic.json | Véase evidencia íntegra de SN-034 en el backlog | SN-019, SN-032 |
| [ SN-035 — Publicar reglas Prometheus ](../specs/backlog.md#sn-035--publicar-reglas-prometheus) | U7 | promtool check rules deploy/monitoring/rules/sentinel.yml | Véase evidencia íntegra de SN-035 en el backlog | SN-026, SN-031, SN-032, SN-030 |
| [ SN-036 — Crear ServiceAccounts separadas ](../specs/backlog.md#sn-036--crear-serviceaccounts-separadas) | U8 | kubectl get sa -n sentinel | Véase evidencia íntegra de SN-036 en el backlog | SN-006, SN-009 |
| [ SN-037 — Aplicar RBAC mínimo ](../specs/backlog.md#sn-037--aplicar-rbac-mínimo) | U8 | kubectl auth can-i get/list/watch | Véase evidencia íntegra de SN-037 en el backlog | SN-036 |
| [ SN-038 — Aislar red interna del namespace ](../specs/backlog.md#sn-038--aislar-red-interna-del-namespace) | U8 | kubectl get networkpolicy -n sentinel | Véase evidencia íntegra de SN-038 en el backlog | SN-006, SN-009 |
| [ SN-039 — Restringir capabilities de los colectores ](../specs/backlog.md#sn-039--restringir-capabilities-de-los-colectores) | U8 | se inspeccionan los securityContext del CronJob de descubrimiento y del Deployment del sensor | Véase evidencia íntegra de SN-039 en el backlog | SN-013, SN-020, SN-036 |
| [ SN-040 — Probar ausencia de acciones de escritura ](../specs/backlog.md#sn-040--probar-ausencia-de-acciones-de-escritura) | U8 | pytest -q tests/security/test_read_only_boundary.py | Véase evidencia íntegra de SN-040 en el backlog | SN-013, SN-017, SN-037 |
| [ SN-041 — Configurar pipeline CI ](../specs/backlog.md#sn-041--configurar-pipeline-ci) | U9 | El workflow ejecuta pytest, lint y helm lint; un PR con fallo queda no aprobado. | Véase evidencia íntegra de SN-041 en el backlog | SN-001, SN-008 |
| [ SN-042 — Escanear la imagen común de Sentinel ](../specs/backlog.md#sn-042--escanear-la-imagen-común-de-sentinel) | U9 | CI construye una imagen sentinel:<tag-inmutable> reutilizada por Core y colectores y genera reporte de scanner/SBOM; … | Véase evidencia íntegra de SN-042 en el backlog | SN-007, SN-041 |
| [ SN-043 — Desplegar manifests por GitOps ](../specs/backlog.md#sn-043--desplegar-manifests-por-gitops) | U9 | Si Argo CD está habilitado, Application queda Synced/Healthy tras commit; si se excluye, queda documentado el procedi… | Véase evidencia íntegra de SN-043 en el backlog | SN-008, SN-031, SN-041 |
| [ SN-044 — Construir ground truth de laboratorio ](../specs/backlog.md#sn-044--construir-ground-truth-de-laboratorio) | U9 | pytest -q tests/e2e/test_ground_truth.py | Véase evidencia íntegra de SN-044 en el backlog | SN-011, SN-018 |
| [ SN-045 — Ejecutar prueba de tráfico alto ](../specs/backlog.md#sn-045--ejecutar-prueba-de-tráfico-alto) | U9 | un generador de prueba controlado produce una tasa por encima del umbral; la condición y alerta aparecen dentro de la… | Véase evidencia íntegra de SN-045 en el backlog | SN-020, SN-027, SN-034, SN-044 |
| [ SN-046 — Ejecutar prueba ARP controlada ](../specs/backlog.md#sn-046--ejecutar-prueba-arp-controlada) | U9 | en una red aislada, dos dispositivos Android, un equipo macOS y un equipo Windows consultan la página HTTP del servid… | Véase evidencia íntegra de SN-046 en el backlog | SN-018, SN-020, SN-028, SN-033, SN-044 |
| [ SN-047 — Preparar sustentación y límites ](../specs/backlog.md#sn-047--preparar-sustentación-y-límites) | U9 | checklist documenta despliegue, permisos, casos positivos/negativos, topología (cinco activos base y un sexto activo … | Véase evidencia íntegra de SN-047 en el backlog | SN-035, SN-039, SN-040, SN-043, SN-045, SN-046 |

## Verificación reproducible

Desde la raíz del repositorio:

```bash
python scripts/verify_traceability.py
```

El verificador comprueba que todas las historias estén presentes una vez en el mapa, que cada historia tenga un único titular, que las dependencias existan y que ambos grafos sean acíclicos. También verifica que las dependencias entre unidades cubran las relaciones entre sus historias.
