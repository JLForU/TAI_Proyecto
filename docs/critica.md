# Investigación crítica — Sentinel

**Propósito:** intentar refutar la utilidad del proyecto antes de invertir tiempo en su construcción.  
**Fecha:** 2026-11-05

## TL;DR — por qué Sentinel podría fracasar

1. El descubrimiento y monitoreo de red ya están resueltos por productos maduros y gratuitos.
2. Un conjunto de scripts Python, Prometheus y Grafana puede ser suficiente; una plataforma adicional quizá no aporte valor.
3. Kubernetes puede imponer más complejidad que la que elimina para una red pequeña.
4. Sin software residente, el inventario de SO/servicios es parcial y probabilístico.
5. La captura de tráfico requiere acceso real a la red; Kubernetes no proporciona esa visibilidad por defecto.
6. Las alertas por umbrales o cambios ARP pueden ser ruidosas y no demuestran que exista un ataque.
7. El sensor podría requerir privilegios Linux de captura que amplían la superficie de ataque.
8. La propuesta no tiene una ventaja competitiva demostrada ni evidencia de disposición a pagar.
9. El alcance acotado puede no cubrir necesidades de operación reales fuera del laboratorio.

## 1. Comoditización

Zabbix ofrece descubrimiento de red por rangos IP y disponibilidad de servicios/SNMP. LibreNMS ofrece autodescubrimiento, incluyendo ARP y SNMP. Nagios XI ofrece checks y umbrales. Prometheus/Grafana resuelven buena parte de la observabilidad. Sentinel debe explicar por qué su integración es preferible para un usuario concreto.

## 2. ¿Por qué no scripts?

El MVP puede reducirse a cuatro procesos: sondear rangos permitidos, recibir/capturar tráfico, persistir resultados y evaluar reglas. Si el esfuerzo de operar Sentinel es mayor que ejecutar esos procesos con cron y dashboards existentes, el producto no aporta suficiente valor.

**Experimento:** construir un flujo equivalente con scripts independientes y comparar tiempo de instalación, ejecución, mantenimiento y consulta de evidencia.

## 3. El coste oculto de Kubernetes

Kubernetes tiene sentido como requisito de arquitectura y despliegue cloud-native, pero no se ha demostrado que un equipo con 10–50 activos lo prefiera a una VM o a una instalación simple. La arquitectura debe mantener pocos workloads y no fragmentar el producto en microservicios innecesarios.

## 4. Cobertura de descubrimiento limitada

Nmap puede inferir SO y servicios desde respuestas de red; no equivale a un inventario completo del endpoint. La identificación de servicios mediante `-sV --version-light` envía sondas activas a los puertos abiertos y puede no obtener una respuesta concluyente; una coincidencia basada solo en el número de puerto debe marcarse como probable. La identificación de la familia de SO puede fallar o resultar ambigua. No instalar software residente reduce intrusión y carga, pero también reduce información.

## 5. Visibilidad de red

Una aplicación dentro de un Pod no recibe automáticamente paquetes de la LAN física. La solución necesita bridge, interfaz dedicada, TAP/SPAN o un sensor externo que remita metadatos. Si el laboratorio no puede proporcionar esa entrada, la función de tráfico no está construida aunque Grafana y Prometheus estén funcionando.

## 6. Alertas no equivalen a detección de amenazas

Un umbral de bytes/s indica que se superó un valor. Un cambio de asociación IP↔MAC indica que el sensor observó una asociación diferente. Ambas condiciones pueden tener causas legítimas. El producto no debe etiquetarlas como DDoS o ARP spoofing confirmado.

## 7. Riesgo de permisos

La captura puede requerir capabilities Linux o una modalidad de red más amplia. El RBAC de Kubernetes no reemplaza las capabilities del sistema operativo. Un diseño que resuelva el problema mediante `privileged: true`, `hostPID` y montaje de `/` sería inaceptable para este alcance.

## 8. Falsos positivos y ruido

Una línea base de cinco muestras de cinco segundos puede ser útil para una demostración breve, pero no caracteriza la variación diaria de una red. Debe presentarse como baseline de laboratorio, calcularse con un método explícito y evaluarse frente a tráfico normal representativo.

## 9. Ventaja competitiva

La etiqueta “read-only” no constituye una ventaja exclusiva. Los sistemas de monitoreo también ofrecen permisos de lectura, reglas y alertas. La confianza es un requisito de diseño, no una ventaja competitiva probada.

## 10. Riesgo de alcance

El producto puede quedarse corto si el usuario necesita inventario exhaustivo, correlación entre subredes, retención prolongada, notificaciones integradas o análisis de protocolos más amplios. Agregar esas capacidades aumenta el costo y puede desbordar el MVP.

## Veredicto

**Como prototipo técnico:** el recorte es construible y permite demostrar descubrimiento, monitoreo, Kubernetes, Helm, seguridad y observabilidad.  
**Como producto comercial:** no hay diferenciación suficiente ni validación de demanda.  
**Como herramienta de laboratorio:** su utilidad depende de que la topología, la fuente de tráfico y los casos de prueba sean reproducibles.

## Hipótesis que deben probarse

- `[INTERNO]` La integración ahorra trabajo respecto de scripts separados.
- `[VERIFICAR]` El sensor puede obtener el tráfico requerido con permisos aceptables.
- `[VERIFICAR]` La cobertura de descubrimiento es suficiente para la topología prevista.
- `[VERIFICAR]` Los umbrales pueden generar alertas útiles con ruido tolerable.
