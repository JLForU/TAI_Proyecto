# Product Vision Board — Sentinel

**Fecha:** 2026-11-05  
**Estado:** propuesta de producto; segmento e hipótesis comerciales no validados.

## PRODUCTO

**Nombre:** Sentinel (provisional).  
**Descripción en una línea:** plataforma self-hosted para descubrir y monitorear activos de una red local autorizada, mantener inventario y telemetría, registrar logs y generar alertas mediante reglas deterministas, sin administrar los dispositivos.

## 1. PROBLEMA

**Problema que resuelvo:** el operador de una red local necesita conocer qué activos están visibles, qué cambios observables ocurren en sus direcciones, puertos, servicios y tráfico, y disponer de evidencia temporal para revisar esas variaciones sin mantener una colección dispersa de scripts.

**Durabilidad del problema:** sí, la necesidad de inventario y observabilidad de red es recurrente. La existencia de soluciones maduras reduce la oportunidad de diferenciación.

**Durability Score:** 3/5 `[INTERNO]`. El problema es persistente, pero Sentinel aún no demuestra una ventaja difícil de sustituir.

## 2. SEGMENTO TARGET

**Para quién:** organizaciones pequeñas, laboratorios o equipos de TI/redes/ciberseguridad que operan una red local de aproximadamente 10–50 activos `[INTERNO]`, necesitan inventario y alertas básicas, y pueden ejecutar una solución self-hosted en Kubernetes.

**Quién controla el veto de confianza:** responsable de infraestructura, redes o ciberseguridad; puede vetar el despliegue si el sensor solicita permisos excesivos, provoca carga o recoge datos no autorizados.

## 3. VENTAJA COMPETITIVA PRIMARIA

**Ventaja primaria de propuesta:** Trust — observación acotada, evidencia visible y reglas explícitas.

**Qué confianza aporta:** el sistema no modifica endpoints ni ejecuta respuestas automáticas; sus alertas muestran la condición medida y la regla que la disparó. Los sondeos activos sí generan paquetes de consulta, por lo que la operación no se describe como captura completamente pasiva.

**Límite:** esto es un principio de diseño y una hipótesis de valor, no una ventaja exclusiva probada. Herramientas existentes pueden ofrecer controles equivalentes.

## 4. ARENA COMPETITIVA

**Arena:** integración de capacidades de monitoreo existentes.

**Cómo compite:** no intenta reemplazar SIEM, NMS ni plataformas maduras. Como prototipo académico, integra descubrimiento de red, telemetría de tráfico y visualización sobre Kubernetes, con un alcance acotado y reproducible.

**Riesgo principal:** un usuario podría obtener un resultado suficiente con Zabbix, LibreNMS, Nagios, Wazuh o scripts propios.

## 5. PARADIGMA UX

**Interacción:** monitoreo automatizado con supervisión humana. El sistema realiza descubrimiento y calcula condiciones de monitoreo según la programación; Prometheus evalúa las reglas de alerta y el operador consulta inventario, logs, gráficas y notificaciones.

**Límite:** el operador interpreta los eventos y decide qué hacer fuera de Sentinel. El sistema no ejecuta acciones de administración ni controles preventivos/de respuesta sobre los endpoints. Sí mantiene los permisos mínimos y el endurecimiento necesarios para proteger sus propios componentes.

## 6. PRIORIDAD OPERACIONAL

El objetivo es un equilibrio con prioridad en simplicidad y evidencia reproducible `[INTERNO]`.

**Trade-offs aceptados:**
- Cobertura de atributos menor que la de plataformas con componentes residentes en los endpoints.
- SO declarado o inferido únicamente cuando exista evidencia documentada; en ausencia de evidencia suficiente, `desconocido`.
- Reglas de alerta limitadas y transparentes, en vez de clasificación opaca.
- Topología y protocolos soportados limitados para mantener un MVP construible.

## 7. MODELO ECONÓMICO

**Modelo:** no definido. El proyecto es un prototipo académico; no hay evidencia de disposición a pagar, coste de soporte, coste operativo ni margen.

**Escala 10x:** TBD. Antes de formular pricing se deben medir carga de sondeo, cardinalidad de métricas, almacenamiento y número de sensores.

**Costos/ingresos/margen:** TBD; no se inventan cifras.

## 8. MÉTRICAS DE ÉXITO

**Métricas de usuario:**
1. Tiempo desde que inicia un ciclo hasta que el inventario queda actualizado.
2. Porcentaje de activos de la topología de laboratorio identificados correctamente frente al ground truth.

**Métricas del sistema:**
1. Tasa de eventos/alertas verdaderos y falsos frente a un conjunto de pruebas controlado.
2. Latencia entre una condición de red inyectada y su registro/alerta.

**Métrica de ruido:** alertas no accionables por hora y porcentaje de alertas reconocidas como ruido en la revisión humana.

## 9. RIESGOS CRÍTICOS

| Riesgo | Respuesta |
|---|---|
| Comoditización | Comparar directamente con herramientas open source maduras; no declarar diferenciación sin prueba |
| Replicación rápida | Aceptar que los scripts y dashboards son replicables; priorizar calidad de integración y evidencia |
| Falsa sensación de detección | Nombrar reglas por condición observable, no como diagnóstico de amenazas |
| Permisos excesivos | Sensor aislado, mínimos permisos y pruebas negativas |
| Ruido de alertas | Umbrales configurables, ventanas, deduplicación y medición de falsos positivos |
| Visibilidad insuficiente | POC de interfaz de captura antes de prometer monitoreo de la LAN |

## Hipótesis que deben validarse

- `[INTERNO]` La integración de descubrimiento, métricas, logs y alertas reduce el esfuerzo frente a scripts separados.
- `[VERIFICAR]` Existe un segmento que necesita una solución pequeña y self-hosted, pero no quiere desplegar una plataforma madura existente.
- `[VERIFICAR]` El acceso de red requerido puede darse sin privilegios excesivos en el entorno seleccionado.
