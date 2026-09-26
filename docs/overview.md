# Panorama del dominio: monitoreo de activos y agentes de IA sobre Kubernetes

> Documento de contexto para el proyecto Sentinel.  
> Fecha de investigación: 2026-09-21.  
> Las afirmaciones externas se acompañan con fuente y fecha. Las hipótesis propias se marcan como `[INTERNO]`; lo que requiere validación adicional se marca como `[VERIFICAR]`.

## 1. Por qué ahora

El contexto técnico es favorable para una solución que combine Kubernetes, monitoreo y automatización asistida por IA, pero eso no significa que exista automáticamente un espacio de mercado defendible.

La CNCF reportó en enero de 2026 que el 82% de los usuarios de contenedores encuestados ejecutan Kubernetes en producción, frente al 66% en 2023. El mismo estudio reportó que el 66% de las organizaciones que alojan modelos de IA generativa usan Kubernetes para parte o toda su inferencia. Esto muestra que Kubernetes ya es una capa operativa consolidada en muchas organizaciones, aunque no implica que todas ellas necesiten un agente para administrar redes o activos de usuario.

Fuente: CNCF, *The CNCF Annual Cloud Native Survey: The Infrastructure of AI’s Future*, 2026-01-20.  
https://www.cncf.io/reports/the-cncf-annual-cloud-native-survey/

La agenda de CNCF para KubeCon + CloudNativeCon North America 2026 incorporó además un track específico de "AI Inference + Agentic", con temas de agentes, inferencia, observabilidad y operación sobre Kubernetes. Esto confirma que la convergencia entre IA y Kubernetes es un área activa del ecosistema. No demuestra, por sí sola, que un producto de monitoreo de activos tenga demanda comercial.

Fuente: CNCF, 2026-08-10.  
https://www.cncf.io/announcements/2026/08/10/cncf-reveals-kubecon-cloudnativecon-north-america-2026-schedule-adds-new-ai-inference-agentic-track/

## 2. Los proyectos open source y su estado real en la CNCF

Sentinel no pretende sustituir el ecosistema Kubernetes; lo utiliza como capa de orquestación. Conviene distinguir entre proyectos que son parte del ecosistema cloud-native y productos de monitoreo de seguridad que compiten funcionalmente aunque no sean proyectos CNCF.

| Proyecto / tecnología | Ecosistema | Qué aporta al dominio | Relación con Sentinel |
|---|---|---|---|
| Kubernetes | CNCF / núcleo del ecosistema | Orquestación de Pods y workloads | Infraestructura central del producto |
| Helm | CNCF ecosystem / herramienta Kubernetes | Empaquetado y despliegue de recursos Kubernetes mediante Charts | Despliegue reproducible del stack |
| Prometheus | CNCF | Recolección y consulta de métricas | Posible fuente de métricas, no diferencial por sí misma |
| Grafana | Ecosistema cloud-native | Consulta, visualización y alertamiento de métricas/logs/traces | Capa visual |
| OpenTelemetry | CNCF | Telemetría y observabilidad | Puede complementar observabilidad, fuera del MVP |
| Wazuh | Open source, no producto CNCF | SIEM/XDR, inventario, monitoreo y detección | Competidor funcional adyacente |
| Zabbix | Open source | Monitoreo de infraestructura y redes | Competidor funcional adyacente |
| Nagios XI | Comercial | Monitoreo de infraestructura y redes | Competidor funcional adyacente |
| SolarWinds NPM | Comercial | Monitoreo de rendimiento y tráfico de red | Competidor funcional adyacente |

Kubernetes define el Pod como su unidad desplegable mínima y recomienda normalmente gestionar Pods mediante recursos de workload en vez de administrarlos individualmente. Los Jobs, por su parte, permiten ejecutar tareas que terminan y reintentar Pods cuando fallan. Estas primitivas son suficientes para que Sentinel pueda crear, eliminar y controlar workloads de monitoreo sin inventar un orquestador propio.

Fuentes:
- Kubernetes, *Pods*, consultado 2026-09-21.  
  https://kubernetes.io/docs/concepts/workloads/pods/
- Kubernetes, *Jobs*, consultado 2026-09-21.  
  https://kubernetes.io/docs/concepts/workloads/controllers/job/
- Helm, *Charts*, consultado 2026-09-21.  
  https://helm.sh/docs/topics/charts/
- Grafana, documentación oficial, consultada 2026-09-21.  
  https://grafana.com/docs/grafana/latest/

## 3. El dinero: qué se está financiando

No se encontró una fuente pública suficientemente homogénea para afirmar un tamaño de mercado específico para "agentes de IA que monitorizan activos de red". Por ello, el análisis no introduce un TAM/SAM/SOM inventado.

Sí se observan modelos comerciales activos en categorías adyacentes:

| Empresa / producto | Hecho comercial verificable | Lectura para Sentinel |
|---|---|---|
| Wazuh Cloud | Plan Small desde USD 571/mes para hasta 100 agentes; Medium desde USD 923/mes; Large desde USD 1.467/mes | Existe disposición de pago por seguridad/monitorización gestionada, aunque el producto incluye muchas capacidades adicionales |
| SolarWinds NPM | Producto comercial de monitoreo de red; precio mediante cotización y prueba de 30 días | El monitoreo de red empresarial es una categoría comercial consolidada |
| Nagios XI | Producto comercial self-hosted; ofrece prueba de 30 días y modelo basado en hosts/servicios y funciones empresariales | El despliegue dentro de la infraestructura del cliente es un modelo establecido |
| Zabbix | Open source con servicios empresariales y soporte comercial | El modelo open source + servicios es viable como referencia |

Fuentes:
- Wazuh Cloud, pricing, consultado 2026-09-21.  
  https://wazuh.com/cloud/
- SolarWinds NPM, consultado 2026-09-21.  
  https://www.solarwinds.com/network-performance-monitor
- Nagios XI, consultado 2026-09-21.  
  https://www.nagios.com/products/nagios-xi/
- Zabbix, introducción oficial, consultada 2026-09-21.  
  https://www.zabbix.com/documentation/current/es/manual/introduction

## 4. Lo que hacen los hyperscalers

Los hyperscalers y plataformas de observabilidad tienden a competir mediante servicios gestionados, telemetría centralizada, integración con múltiples fuentes y automatización operativa.

Para Sentinel esto tiene una consecuencia importante: **"usar IA para operar infraestructura" no puede tratarse como diferenciador suficiente**. El espacio propio del proyecto debe definirse por la combinación concreta de:

- despliegue self-hosted dentro de la red del cliente;
- foco en un conjunto acotado de activos;
- monitoreo basado en estado y cambios;
- orquestación operacional mediante Kubernetes;
- agente de IA restringido a Kubernetes y herramientas autorizadas;
- prohibición explícita de ejecutar acciones directamente sobre los activos.

Este posicionamiento es una hipótesis de producto, no una ventaja competitiva ya demostrada. `[INTERNO]`

## 5. La tensión central de la categoría

La tensión central no es únicamente "IA versus automatización". Es:

> **¿La inteligencia operacional aporta suficiente valor frente a scripts deterministas y herramientas de monitoreo maduras, especialmente en redes pequeñas de 10–50 activos?**

El monitoreo de red ya es una categoría madura. Zabbix monitoriza parámetros de redes e infraestructura, almacena históricos y permite automatizar respuestas. Nagios XI ejecuta comprobaciones a intervalos y compara resultados contra rangos definidos. SolarWinds NPM monitoriza disponibilidad, tráfico, rendimiento, genera alertas y puede utilizar líneas base históricas. Wazuh ofrece inventario, monitoreo, detección y, en modalidad agentless, puede ejecutar comandos y detectar cambios en su salida.

Fuentes:
- Zabbix, documentación oficial, consultada 2026-09-21.  
  https://www.zabbix.com/documentation/current/es/manual/introduction
- Nagios XI, consultado 2026-09-21.  
  https://www.nagios.com/products/nagios-xi/
- SolarWinds NPM, consultado 2026-09-21.  
  https://www.solarwinds.com/network-performance-monitor
- Wazuh agentless monitoring, consultado 2026-09-21.  
  https://documentation.wazuh.com/current/user-manual/capabilities/agentless-monitoring/how-it-works.html

Por tanto, el agente de Sentinel debe justificarse por la **orquestación de las operaciones**, no por reemplazar la lógica determinista de monitorización.

## 6. Contexto macro: adopción cloud-native y observabilidad

En la encuesta cloud-native publicada por CNCF en enero de 2026:

- 82% de los usuarios de contenedores reportaron Kubernetes en producción.
- 98% de las organizaciones encuestadas reportaron haber adoptado técnicas cloud-native.
- 66% de las organizaciones que alojan modelos de IA generativa usan Kubernetes para alguna parte de su inferencia.

La misma investigación señala que, en 2025, las organizaciones identificaron seguridad como una de las dificultades relevantes de los entornos cloud-native. Otra publicación de CNCF basada en su investigación reportó seguridad (72%) y observabilidad (51%) entre los principales desafíos para cargas de datos intensivas en entornos cloud-native.

Estas cifras describen el ecosistema cloud-native general y **no deben presentarse como evidencia directa de demanda por Sentinel**.

Fuentes:
- CNCF Annual Cloud Native Survey, 2026-01-20.  
  https://www.cncf.io/reports/the-cncf-annual-cloud-native-survey/
- CNCF, *What 500+ Experts Revealed About Kubernetes Adoption and Workloads*, 2025-08-02.  
  https://www.cncf.io/blog/2025/08/02/what-500-experts-revealed-about-kubernetes-adoption-and-workloads/

## 7. Qué NO se pudo verificar

- `[VERIFICAR]` Tamaño mundial del mercado específicamente definido como "agentes de IA para monitoreo de activos de red".
- `[VERIFICAR]` Número de organizaciones que combinarían exactamente Kubernetes + self-hosted + ciberseguridad + 10–50 activos.
- `[VERIFICAR]` Disposición de pago del segmento objetivo de Sentinel.
- `[VERIFICAR]` Ventaja cuantificable de usar un agente de IA frente a una automatización clásica en el caso de redes pequeñas.
- `[VERIFICAR]` Reducción concreta de tiempo operativo atribuible al agente.
- `[VERIFICAR]` Diferenciación sostenible frente a Wazuh, Zabbix, Nagios, SolarWinds y herramientas construidas internamente.

*Material de referencia — Tópicos Especiales en Informática*
