# Análisis de mercado — monitoreo de activos y agentes de IA sobre Kubernetes

> Documento de validación de mercado para Sentinel.  
> Fecha de corte: 2026-09-21.  
> Las cifras externas están enlazadas; las hipótesis propias están marcadas `[INTERNO]`.

## 1. El mercado que se cita cuando se quiere convencer

En vez de inventar una cifra única de mercado, conviene utilizar señales de adopción verificables del ecosistema donde Sentinel operaría.

| Cifra | Valor | Horizonte | Fuente |
|---|---:|---|---|
| Organizaciones cloud-native encuestadas que reportaron adopción de técnicas cloud-native | 98% | Encuesta 2025, publicada 2026 | CNCF |
| Usuarios de contenedores que ejecutan Kubernetes en producción | 82% | Encuesta 2025, publicada 2026 | CNCF |
| Organizaciones que alojan IA generativa y usan Kubernetes para alguna parte de inferencia | 66% | Encuesta 2025, publicada 2026 | CNCF |
| Seguridad entre desafíos de cargas de datos cloud-native | 72% | Investigación publicada 2025 | CNCF |
| Observabilidad entre desafíos de cargas de datos cloud-native | 51% | Investigación publicada 2025 | CNCF |

Fuentes:
- https://www.cncf.io/reports/the-cncf-annual-cloud-native-survey/
- https://www.cncf.io/blog/2025/08/02/what-500-experts-revealed-about-kubernetes-adoption-and-workloads/

**Interpretación:** estas cifras justifican que Kubernetes, seguridad y observabilidad son dominios relevantes. No demuestran que exista un mercado independiente para Sentinel.

## 2. La cifra que hay que poner en la misma diapositiva

La cifra de adopción debe acompañarse con una realidad competitiva incómoda: **el monitoreo y la gestión de activos ya tienen productos maduros, open source y comerciales**.

- Wazuh reporta más de 15 millones de endpoints protegidos, más de 100.000 usuarios empresariales y más de 30 millones de descargas anuales en su propia información corporativa.
- Wazuh Cloud publica un precio inicial de USD 571/mes para hasta 100 agentes en su plan Small.
- Nagios XI y SolarWinds NPM ya ofrecen monitoreo self-hosted, dashboards, alertas y comprobaciones periódicas.
- Zabbix ofrece una plataforma de monitoreo open source que puede escalar desde redes pequeñas hasta miles de hosts.

Estas cifras y capacidades muestran que Sentinel no puede basar su propuesta en "monitorizar redes" de forma genérica.

Fuentes:
- Wazuh, About us, consultado 2026-09-21.  
  https://wazuh.com/about-us/
- Wazuh Cloud, consultado 2026-09-21.  
  https://wazuh.com/cloud/
- Nagios XI, consultado 2026-09-21.  
  https://www.nagios.com/products/nagios-xi/
- SolarWinds NPM, consultado 2026-09-21.  
  https://www.solarwinds.com/network-performance-monitor
- Zabbix, consultado 2026-09-21.  
  https://www.zabbix.com/documentation/current/es/manual/introduction

## 3. Estructura competitiva

### Capa gratuita / open source

| Producto | Posición funcional | Señal comercial verificable |
|---|---|---|
| Wazuh | Seguridad de endpoints, SIEM/XDR, inventario y monitoreo | Plataforma open source; además ofrece Wazuh Cloud de pago |
| Zabbix | Monitoreo de infraestructura y redes | Open source; soporte y servicios empresariales |

Wazuh puede hacer monitoreo agentless y detectar cambios en archivos, directorios, configuraciones o salidas de comandos. Esto se aproxima directamente al patrón "estado inicial + comprobación periódica + detección de cambio".

Fuente Wazuh:
https://documentation.wazuh.com/current/user-manual/capabilities/agentless-monitoring/how-it-works.html

### Capa hyperscalers / plataformas gestionadas

| Tipo | Posición |
|---|---|
| Plataformas cloud y observabilidad gestionada | Ofrecen monitorización, métricas, logs, automatización e integración a mayor escala |

No se toma una plataforma hyperscaler concreta como competidor directo porque el MVP de Sentinel está explícitamente planteado como **self-hosted en la red local del cliente**.

### Capa comercial

| Empresa / producto | Posición | Señal comercial verificable |
|---|---|---|
| Nagios XI | Monitoreo de infraestructura y red self-hosted | Prueba de 30 días y venta empresarial |
| SolarWinds NPM | Network Performance Monitoring | Prueba de 30 días y precio por cotización |
| LogicMonitor | Network traffic flow monitoring | Producto comercial con monitoreo NetFlow/IPFIX/sFlow y análisis de flujos |

Fuentes:
- https://www.nagios.com/products/nagios-xi/
- https://www.solarwinds.com/network-performance-monitor
- https://www.logicmonitor.com/support/network-traffic-flow-monitoring-new-ui

## 4. Dónde queda el espacio

El espacio hipotético de Sentinel es deliberadamente estrecho:

> **Organizaciones con una red local de aproximadamente 10–50 activos, con un equipo de ciberseguridad que desea desplegar el sistema dentro de su propia infraestructura para monitorizar cambios en un conjunto definido de atributos y usar un agente de IA como orquestador de las operaciones de Kubernetes.** `[INTERNO]`

El producto no intenta competir en amplitud con un SIEM/XDR completo ni con una suite empresarial de network performance monitoring.

El MVP se centra en seis familias de información:

1. IP
2. MAC
3. Sistema operativo
4. Puertos
5. Servicios
6. Tráfico

En tráfico, la definición adoptada es:

- volumen en bytes por segundo;
- IP origen y destino;
- protocolo.

El nuevo activo detectado automáticamente **no forma parte del MVP**. Se considera una evolución futura.

## 5. El dolor operativo, con datos que resistieron la auditoría

La evidencia disponible respalda que seguridad y observabilidad son retos relevantes en entornos cloud-native, pero no mide específicamente el dolor del ICP de Sentinel.

El dolor que Sentinel formula es más estrecho:

- pérdida de visibilidad sobre el estado actual de activos;
- dificultad para saber cuándo una característica monitoreada cambió;
- esfuerzo operacional para ejecutar de forma consistente las tareas de descubrimiento y monitoreo;
- incorporación automática de nuevos activos como problema futuro, no resuelto en el MVP.

La automatización mediante scripts es determinista; la IA se ubica por encima de ella como orquestador.

Esto es coherente con el hecho de que Kubernetes expone una API y gestiona recursos como Pods y Jobs, mientras que Helm empaqueta y despliega recursos de Kubernetes mediante Charts.

Fuentes:
- Kubernetes API access, consultado 2026-09-21.  
  https://kubernetes.io/docs/tasks/extend-kubernetes/http-proxy-access-api/
- Kubernetes Jobs, consultado 2026-09-21.  
  https://kubernetes.io/docs/concepts/workloads/controllers/job/
- Helm Charts, consultado 2026-09-21.  
  https://helm.sh/docs/topics/charts/

## 6. Riesgo geográfico y de segmento

El diseño self-hosted reduce la dependencia del país como variable principal. La hipótesis es que una organización puede instalar el repositorio en su propia red, independientemente de su ubicación geográfica.

Por eso, el beachhead no se fija todavía en Colombia, México, Brasil u otro país. `[INTERNO]`

El principal riesgo de segmentación es técnico:

- una organización puede tener solo 10–50 activos pero no tener capacidad para administrar Kubernetes;
- puede preferir una solución gestionada;
- puede requerir intervención directa sobre endpoints, algo que Sentinel no ofrece;
- puede considerar suficientes sus herramientas actuales.

Por tanto, la capacidad técnica del cliente para desplegar y operar una instalación self-hosted debe convertirse en una señal de calificación del ICP.

## 7. Qué no se pudo verificar

- `[VERIFICAR]` Tamaño monetario del segmento específico de Sentinel.
- `[VERIFICAR]` Porcentaje de organizaciones con 10–50 activos que tienen un equipo de ciberseguridad formal.
- `[VERIFICAR]` WTP (willingness to pay) por el componente de orquestación mediante IA.
- `[VERIFICAR]` Tiempo operativo ahorrado frente a scripts + cron + una plataforma de monitoreo existente.
- `[VERIFICAR]` Tasa de adopción de Kubernetes en organizaciones pequeñas con redes de 10–50 activos.
- `[VERIFICAR]` Ventaja comercial sostenible del control humano por etapas frente a otras herramientas que también aplican permisos y automatización restringida.

*Material de referencia — Tópicos Especiales en Informática*
