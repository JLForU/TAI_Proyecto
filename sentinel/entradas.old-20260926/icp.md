# Ideal Customer Profile — Sentinel

> El ICP se deriva del PVB, la definición funcional actual y la investigación de dominio. Es una hipótesis falsable, no una descripción de un cliente ya validado.
>
> Fecha: 2026-09-21.

## ICP — segmento beachhead

### Empresas / organizaciones

Organizaciones con una red local o privada administrable, que tengan aproximadamente **10–50 activos** dentro del alcance inicial y un equipo o responsable formal de ciberseguridad.

El cliente debe poder instalar software dentro de su propia infraestructura y aceptar un modelo **self-hosted**. `[INTERNO]`

### Geografía inicial

**Sin restricción geográfica inicial.** `[INTERNO]`

El repositorio debe poder desplegarse en la red del cliente, por lo que la variable crítica no es el país sino la capacidad técnica y las restricciones de operación local.

### Sectores

No se fija todavía un sector vertical único. `[INTERNO]`

Como hipótesis inicial, el producto puede probarse en organizaciones que:

- administren una red privada con un número limitado de activos;
- tengan necesidad de visibilidad operativa;
- cuenten con al menos un responsable de seguridad o infraestructura;
- puedan ejecutar una instalación Kubernetes local.

La verticalización debe decidirse después de entrevistas o pilotos; no existe evidencia suficiente todavía para afirmar que un sector concreto presenta mayor disposición de pago.

### Las tres señales de calificación

**Señal 1 — Alcance técnico**
- Entre 10 y 50 activos aproximadamente.
- Los activos están dentro de una red administrable por el cliente.

**Señal 2 — Necesidad operacional**
- El equipo quiere conocer cambios en IP, MAC, SO, puertos, servicios y tráfico.
- Existe una necesidad real de ejecutar periódicamente tareas de descubrimiento y monitoreo.

**Señal 3 — Condición de despliegue**
- El cliente acepta una solución self-hosted.
- Tiene capacidad para ejecutar y mantener un entorno Kubernetes o cuenta con personal técnico que pueda hacerlo.

### Fuera del ICP (explícitamente)

- Organizaciones que exigen una solución SaaS y no aceptan self-hosted.
- Redes con un alcance muy superior a 50 activos para el MVP.
- Organizaciones que buscan detección avanzada de amenazas, EDR, SIEM completo o XDR como objetivo principal.
- Clientes que requieren que el agente modifique directamente los endpoints.
- Entornos donde no sea posible ejecutar scripts autorizados o acceder a los recursos locales necesarios.
- Organizaciones sin capacidad para mantener la infraestructura de despliegue. `[INTERNO]`

## Buyer personas

### Persona 1 — Responsable / líder de ciberseguridad (decisor y veto)

**Objetivo:** mantener visibilidad sobre los activos y reducir tareas operativas repetitivas.

**Necesidades:**
- evidencia de cambios;
- control de quién ejecuta operaciones;
- trazabilidad de acciones;
- despliegue dentro de la infraestructura propia.

**Veto de confianza:** alto.

El responsable de seguridad debe poder decidir qué herramientas y acciones puede ejecutar el agente. `[INTERNO]`

### Persona 2 — Analista o ingeniero de ciberseguridad (usuario principal)

**Objetivo:** ejecutar de manera consistente descubrimiento, monitoreo y tareas operativas sobre el entorno.

**Necesidades:**
- simplificar tareas repetitivas;
- consultar el estado de Kubernetes;
- lanzar herramientas y scripts con parámetros correctos;
- recuperar operaciones fallidas;
- revisar evidencia de ejecución.

**Problema principal:**
- detectar cambios en activos sin tener que repetir manualmente toda la secuencia operacional.

### Persona 3 — Administrador de infraestructura / redes (usuario colaborador)

**Objetivo:** asegurar que Kubernetes, red, scripts y componentes de monitorización funcionen de manera estable.

**Necesidades:**
- configuración reproducible;
- despliegue self-hosted;
- control de recursos Kubernetes;
- capacidad de diagnosticar fallos de Pods y Jobs.

**Rol:** colaborador técnico; no necesariamente comprador.

## Pains

### Operativos

- No siempre existe una forma centralizada y repetible de observar los cambios de los activos.
- Ejecutar periódicamente múltiples scripts y comprobaciones puede requerir intervención manual.
- Mantener la consistencia de parámetros entre tareas puede generar errores humanos.
- Recuperar una operación fallida exige revisar logs y repetir comandos.
- Las herramientas existentes pueden tener mucha más amplitud de la necesaria para un entorno pequeño.

### Estratégicos

- Las organizaciones pueden querer una solución self-hosted para mantener los datos dentro de su infraestructura.
- El equipo puede querer introducir IA en operaciones sin otorgarle capacidad de intervención directa sobre endpoints.
- El cliente puede necesitar trazabilidad para demostrar qué hizo la herramienta y con qué parámetros. `[INTERNO]`

## Deseos

- Tener una vista operativa de los activos y su comportamiento.
- Registrar cambios importantes en el estado monitoreado.
- Ejecutar tareas repetitivas mediante un flujo controlado.
- Poder detener o aprobar cada etapa.
- Evitar que el agente pueda modificar directamente los activos.
- Desplegar el sistema en la infraestructura local.
- Poder ampliar el sistema en el futuro para reconocer nuevos activos y asignarles monitoreo automáticamente. `[INTERNO]`

## Triggers de compra

- Aumento de incidentes relacionados con cambios no documentados en activos.
- Necesidad de una instalación local por restricciones de datos o política.
- Equipo pequeño de ciberseguridad con tareas manuales repetitivas.
- Requerimiento de estandarizar scripts y procedimientos de monitoreo.
- Interés de la organización en experimentar con agentes de IA bajo permisos muy restringidos. `[INTERNO]`

## Objeciones probables

| Objeción | Respuesta que debe demostrar el producto |
|---|---|
| "Ya tengo Zabbix/Wazuh/Nagios." | Sentinel no debe prometer reemplazarlos; debe demostrar una diferencia operacional concreta en la orquestación. |
| "Esto lo puedo hacer con scripts y cron." | Debe medirse el tiempo y la tasa de error con y sin agente. |
| "No quiero que una IA toque mi infraestructura." | El agente no puede ejecutar acciones directamente sobre los activos; solo usa Kubernetes y herramientas autorizadas. |
| "No quiero enviar datos de mi red a un proveedor externo." | El despliegue es self-hosted y debe definirse una estrategia de modelo local o de manejo explícito de datos. `[VERIFICAR]` |
| "Kubernetes es demasiado complejo para 10–50 activos." | El producto debe reducir la complejidad de despliegue mediante Helm y documentación reproducible. |
| "Necesito detección de ataques, no solo cambios." | Eso está fuera del alcance del MVP. Sentinel es un sistema de monitoreo; la detección avanzada requeriría otro alcance. |
| "¿Puede detectar dispositivos nuevos automáticamente?" | No en el MVP. Es una funcionalidad futura del roadmap. |

*Material de referencia — Tópicos Especiales en Informática*
