# Fuentes consultadas — Sentinel

**Fecha de consulta:** 2026-11-05.  
**Criterio:** documentación oficial de proyectos y proveedores. Las fuentes demuestran capacidades documentadas; no prueban que Sentinel las haya implementado ni que los productos comparados sean equivalentes en todas sus funciones.

## S01 — kube-prometheus-stack (Prometheus Community)

- URL: https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack
- Uso: propuesta para desplegar Prometheus Operator, Prometheus, Grafana, Alertmanager, dashboards y reglas mediante Helm.
- Límite: el chart no instala todos los componentes del proyecto kube-prometheus; por ejemplo, no incluye el Prometheus Blackbox Exporter ni el Prometheus Adapter. Fijar versión y revisar valores al instalar.

## S02 — Prometheus: Alerting overview

- URL: https://prometheus.io/docs/alerting/latest/overview/
- Uso: sustenta el flujo en el que Prometheus evalúa reglas y envía alertas a Alertmanager; Alertmanager agrupa, inhibe, silencia y enruta notificaciones.
- Límite: se debe configurar explícitamente el receptor de notificaciones; no se presupone correo o webhook disponible por defecto.

## S03 — Prometheus: Metric and label naming

- URL: https://prometheus.io/docs/practices/naming/
- Uso: sustenta nombres con unidad y el cuidado con labels de alta cardinalidad.
- Implicación: los IP origen/destino se conservan en eventos/logs estructurados; no se usan indiscriminadamente como labels Prometheus.

## S04 — Kubernetes: Network Policies

- URL: https://kubernetes.io/docs/concepts/services-networking/network-policies/
- Uso: describe políticas de flujo IP/puerto para Pods y la necesidad de un plugin de red que implemente enforcement.
- Límite: el comportamiento de NetworkPolicy con Pods `hostNetwork` es indefinido y depende de la implementación; la política no crea por sí misma una copia de tráfico LAN.

## S05 — Kubernetes: Service Accounts

- URL: https://kubernetes.io/docs/concepts/security/service-accounts/
- Uso: identidad de workloads, asignación de permisos RBAC y opción `automountServiceAccountToken: false` para cargas que no requieren consultar la API.

## S06 — Kubernetes: Pod Security Standards

- URL: https://kubernetes.io/docs/concepts/security/pod-security-standards/
- Uso: revisar las restricciones de `privileged`, host namespaces, `hostPath` y capabilities permitidas en perfiles Baseline/Restricted.
- Implicación: Baseline no permite añadir `CAP_NET_RAW`; Restricted exige descartar `ALL` y solo permite añadir `NET_BIND_SERVICE`. Mover un Pod a otro namespace no concede la capability: cualquier excepción necesita una configuración explícita de Pod Security Admission y una política complementaria comprobable. Fuente revisada el 2026-11-05.

## S07 — Kubernetes: RBAC

- URL: https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- Uso: diseñar un Role/RoleBinding acotado al namespace `sentinel` para que Core consulte Pods, Jobs y CronJobs mediante `get/list/watch`.
- Implicación: comprobar de forma explícita los verbos permitidos y denegados con `kubectl auth can-i`.

## S08 — Kubernetes Python Client

- URL: https://github.com/kubernetes-client/python
- Ejemplo de configuración dentro del clúster: https://github.com/kubernetes-client/python/blob/master/examples/in_cluster_config.py
- Uso: integrar el cliente oficial desde Sentinel Core y cargar la configuración in-cluster.
- Límite: los permisos efectivos dependen del ServiceAccount y RBAC asignados al Pod.

## S09 — Nmap: OS Detection

- URL: https://nmap.org/book/man-os-detection.html
- Uso: documentar la huella TCP/IP como método de inferencia remota de SO.
- Límite: la precisión depende de las respuestas; Nmap señala que el método es más eficaz cuando se encuentra al menos un puerto TCP abierto y uno cerrado.

## S10 — Nmap: Service and Version Detection

- URL: https://nmap.org/book/man-version-detection.html
- Uso: documentar `-sV` para identificar protocolo, servicio y versión mediante sondas a puertos abiertos; `--version-light` equivale a intensidad 2 y reduce el conjunto de sondas frente al valor predeterminado.
- Límite: incluso en modo ligero el sondeo es activo y puede no identificar algunos servicios; debe limitarse a puertos autorizados y no equivale a un escaneo de vulnerabilidades.

## S11 — Scapy: Usage

- URL: https://scapy.readthedocs.io/en/stable/usage.html
- Uso: candidato de implementación para leer PCAP, filtrar y capturar paquetes por interfaz, incluyendo mensajes ARP.
- Límite: backend, plataforma, interfaz y permisos requeridos deben probarse en el entorno de laboratorio; no se presupone que un Pod pueda capturar cualquier interfaz.

## S12 — Prometheus SNMP Exporter

- URL: https://github.com/prometheus/snmp_exporter
- Uso: opción para obtener métricas SNMP desde switches, routers y puntos de acceso.
- Implicación: usar permisos de lectura. Revisar las propiedades de seguridad del protocolo y preferir SNMPv3 cuando esté soportado.

## S13 — Zabbix: Network discovery

- URL: https://www.zabbix.com/documentation/current/es/manual/discovery/network_discovery
- Uso: alternativa de descubrimiento por rangos IP, servicios y SNMP.
- Implicación: el descubrimiento de red es una función madura y disponible en herramientas existentes.

## S14 — LibreNMS: Auto Discovery

- URL: https://docs.librenms.org/Extensions/Auto-Discovery/
- Uso: alternativa con autodescubrimiento, SNMP, ARP y descubrimiento de vecinos.
- Implicación: refuerza la necesidad de comparar el prototipo con herramientas existentes.

## S15 — Nagios XI

- URL: https://www.nagios.com/products/nagios-xi/
- Uso: alternativa comercial con checks, umbrales, alertas y distintas modalidades de monitorización.
- Implicación: Sentinel compite en un dominio con productos completos.

## S16 — Wazuh: System inventory

- URL: https://documentation.wazuh.com/current/user-manual/capabilities/system-inventory/
- Uso: alternativa adyacente para inventario de hardware/software/puertos/procesos.
- Límite: la comparación debe considerar la modalidad de despliegue y los componentes residentes que requiere.

## Límites de la investigación

No se utilizaron cifras de TAM, crecimiento, precios, ahorros o cuotas de mercado. No se atribuye una ventaja comercial a Sentinel. Los enlaces a documentación `current`, `latest` o ramas `main` pueden cambiar; antes de implementar se deben fijar las versiones concretas de charts, clientes y herramientas.

## S17 — Nmap: TCP Connect Scan

- URL: https://nmap.org/book/scan-methods-connect-scan.html
- Uso: justificar el uso inicial de `-sT`, que establece conexiones mediante la llamada `connect` del sistema operativo y está disponible para usuarios sin privilegios de paquetes crudos.
- Límite: completa la conexión en puertos abiertos y puede generar más tráfico/logs en el objetivo que un SYN scan; por eso se mantiene la allowlist y el límite de tasa.

## S18 — Linux capabilities(7)

- URL: https://man7.org/linux/man-pages/man7/capabilities.7.html
- Uso: diferenciar `CAP_NET_RAW` (sockets RAW/PACKET) de `CAP_NET_ADMIN` (administración/configuración de interfaces y modo promiscuo, entre otras operaciones).
- Límite: la necesidad efectiva depende de la fuente de captura, la interfaz, el runtime y el modo en que se entregue el feed. Solo se habilitarán capabilities demostradas por el POC.


## S19 — Prometheus: scraping y ServiceMonitor

- URL: https://prometheus.io/docs/prometheus/latest/configuration/configuration/
- URL complementaria: https://prometheus-operator.dev/docs/api-reference/api/
- Uso: sustentar el modelo pull: Prometheus consulta por HTTP el endpoint de métricas del target; el ServiceMonitor define el descubrimiento/configuración del endpoint cuando se utiliza Prometheus Operator.
- Implicación: Core expone `/metrics` y Prometheus realiza `GET`; los colectores envían sus observaciones al Core, no a Prometheus. Los selectores del ServiceMonitor y del Prometheus deben coincidir explícitamente.


## S20 — Nmap: XML Output

- URL: https://nmap.org/book/output-formats-xml-output.html
- Uso: XML (`-oX`) es el formato recomendado por Nmap para procesamiento programático; en el MVP se envía a stdout mediante `-oX -` para evitar archivos temporales.
- Límite: el parser debe tolerar atributos/campos ausentes y validar el formato; la salida XML no convierte una inferencia basada en puerto en una identificación confirmada.

## S21 — Prometheus: Alerting rules

- URL: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- Uso: documentar el campo `for`, que exige que una expresión permanezca activa durante un periodo antes de que la alerta pase a firing.
- Límite: el valor de `for` y la expresión deben configurarse y probarse en el entorno; no se asumen umbrales productivos.
