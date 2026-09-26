# Investigación de crítica — Sentinel

> **Este documento no intenta defender Sentinel.** Su propósito es encontrar las razones por las que podría fracasar, quedar comoditizado o no justificar el uso de IA.
>
> Fecha de investigación: 2026-09-21.  
> Toda evidencia externa está enlazada; las hipótesis propias se marcan `[INTERNO]`.

## TL;DR — por qué Sentinel podría fracasar

1. **La monitorización que Sentinel ofrece ya es una categoría madura.** Zabbix, Nagios, SolarWinds y Wazuh ya monitorizan infraestructura, redes, servicios, cambios y/o tráfico.
2. **El componente IA puede ser innecesario para el MVP.** El descubrimiento y monitoreo pueden ejecutarse con scripts deterministas; si el agente solo selecciona herramientas y parámetros, el valor adicional debe demostrarse con mediciones.
3. **El "control humano" no es suficiente como diferenciador.** Es una propiedad de gobernanza y seguridad, pero no constituye por sí sola un moat.
4. **El MVP no resuelve todavía uno de los dos problemas declarados.** La incorporación automática de nuevos activos queda fuera del MVP; por tanto, la opción 4 del problema es una oportunidad futura, no una capacidad actualmente demostrada.
5. **Self-hosted tampoco es un diferenciador único.** Nagios XI y otros productos comerciales ya soportan despliegues dentro de infraestructura controlada por el cliente.
6. **El riesgo más serio es de utilidad, no de tecnología.** Una organización con 10–50 activos puede resolver gran parte del problema con herramientas existentes y scripts propios.
7. **El agente tiene un límite operativo importante y deliberado:** no puede actuar directamente sobre los activos. Esto reduce el riesgo, pero también limita el valor de automatización que puede capturarse.

## 1. Comoditización: el problema ya tiene muchas soluciones

La observación periódica de dispositivos, la comparación contra valores esperados, los umbrales y los dashboards no son innovaciones nuevas.

Zabbix se presenta como plataforma de monitoreo empresarial de código abierto para redes e infraestructura, con almacenamiento histórico, visualización y automatización de respuestas.

Fuente:
https://www.zabbix.com/documentation/current/es/manual/introduction

Nagios XI ejecuta plugins sobre hosts y servicios a intervalos definidos, compara resultados con rangos de advertencia/críticos, registra resultados y notifica.

Fuente:
https://www.nagios.com/products/nagios-xi/

SolarWinds NPM monitoriza disponibilidad, tráfico, rendimiento, métricas de red, descubrimiento de dispositivos y líneas base históricas.

Fuente:
https://www.solarwinds.com/network-performance-monitor

Wazuh, mediante monitoreo agentless, puede conectarse por SSH, supervisar archivos/configuraciones y ejecutar comandos periódicamente; cuando cambia la salida monitorizada, puede generar una alerta.

Fuente:
https://documentation.wazuh.com/current/user-manual/capabilities/agentless-monitoring/how-it-works.html

**Implicación crítica:** Sentinel no puede vender "monitorización continua de activos" como novedad. Su posible diferenciación debe estar en la forma concreta de orquestar operaciones y desplegar los componentes.

## 2. El riesgo base de la categoría: IA sobre automatización determinista

El proyecto declara que la IA es principalmente un orquestador operacional.

Eso crea una prueba de valor muy concreta:

> ¿El agente ahorra suficiente trabajo operativo como para justificar su complejidad y coste frente a una secuencia equivalente de scripts?

En el MVP:

- consultar Kubernetes: sí;
- ejecutar descubrimiento: sí;
- ejecutar monitoreo: sí;
- crear/eliminar Pods: sí;
- modificar configuración: sí;
- ejecutar acción después de aprobación: sí;
- reintentar operaciones fallidas: sí;
- comparar baseline directamente como capacidad del agente: no;
- consultar Grafana directamente: no;
- detectar nuevos activos: no;
- proponer acciones: no.

La arquitectura resultante hace que la **lógica de monitoreo siga siendo determinista y externa al modelo**. `[INTERNO]`

Eso es bueno para reproducibilidad, pero deja abierta la pregunta más difícil: **¿qué parte de ese trabajo sería imposible o materialmente peor sin IA?** `[VERIFICAR]`

## 3. La limitación de diseño no es un diferenciador por sí misma

Sentinel establece una frontera de seguridad clara:

> El agente nunca puede ejecutar acciones directamente sobre los activos; solo puede interactuar con Kubernetes y herramientas autorizadas.

Esta decisión reduce la superficie de impacto de un error del modelo y facilita aplicar RBAC, allowlists y aislamiento en el plano de orquestación.

Pero la restricción no es, por sí sola, una innovación. La necesidad de limitar permisos y mantener controles de acceso ya es una práctica central en Kubernetes y en herramientas de seguridad.

**Lo que podría diferenciar a Sentinel** es la combinación de:

- agente restringido;
- herramientas predefinidas;
- secuenciación operacional;
- reintentos acotados;
- despliegue self-hosted;
- trazabilidad de lo que el agente ejecutó.

Incluso esta combinación debe medirse; no debe asumirse como moat.

## 4. El moat, examinado en frío

El PVB identifica confianza/control humano como ventaja competitiva primaria.

La crítica es que **control no es un activo acumulativo automáticamente**.

Un competidor podría implementar:

- RBAC;
- allowlists de herramientas;
- un agente con tool-calling;
- registros de ejecución;
- aprobaciones humanas;
- ejecución sobre la API de Kubernetes.

La implementación técnica es replicable.

El posible activo acumulativo de Sentinel sería más estrecho:

- historial de ejecuciones y fallos;
- datos de qué herramientas, parámetros y reintentos funcionan;
- recetas operativas validadas;
- evidencia de reducción de trabajo humano.

Pero eso todavía no constituye un moat demostrado. `[VERIFICAR]`

## 5. El fracaso más probable no es técnico: es la irrelevancia

El escenario peligroso no necesita una catástrofe.

Puede suceder algo más simple:

1. El equipo instala Sentinel.
2. Los scripts funcionan.
3. Kubernetes crea los Pods correctamente.
4. El agente también funciona.
5. Pero el equipo concluye que podía ejecutar los mismos scripts con cron, una herramienta de monitoreo existente y unos pocos comandos de `kubectl`.

En ese escenario, el sistema técnicamente funciona, pero el producto no tiene suficiente valor adicional.

**Métrica que debe existir:** tiempo total de una tarea operacional con Sentinel frente al mismo flujo sin agente.

## 6. El producto puede ser parte del problema que dice resolver

Las herramientas maduras ya reducen parte del trabajo mediante dashboards, alertas, detección de cambios, discovery y automatización.

Por ejemplo, SolarWinds NPM afirma realizar descubrimiento automático de dispositivos y monitoreo continuo de métricas; Wazuh agentless permite comandos periódicos y detectar cambios.

Fuentes:
- https://www.solarwinds.com/network-performance-monitor
- https://documentation.wazuh.com/current/user-manual/capabilities/agentless-monitoring/how-it-works.html

Por eso Sentinel debe demostrar que **no añade otra capa de operación que el administrador tenga que mantener**.

La complejidad adicional incluye:

- Kubernetes;
- Helm;
- scripts;
- agente;
- permisos;
- configuración;
- logs del propio agente.

La carga operativa de Sentinel debe medirse como parte de la evaluación.

## 7. Riesgo de seguridad que el propio diseño no elimina

El modelo no tiene acceso directo a los activos, pero sí recibe datos operativos y tiene acceso al plano Kubernetes.

Eso crea otros vectores:

- uso incorrecto de la API de Kubernetes;
- permisos excesivos del ServiceAccount;
- modificación indebida de configuraciones;
- uso de una herramienta autorizada con parámetros incorrectos;
- manipulación de datos consumidos por el agente;
- fuga de información del entorno en consultas a un proveedor externo de IA.

La arquitectura propuesta reduce el impacto porque el agente no actúa directamente sobre los endpoints, pero **no elimina el riesgo de una acción incorrecta dentro de Kubernetes**.

Mitigaciones a evaluar:

- RBAC de mínimo privilegio;
- ServiceAccount dedicado;
- herramientas allowlisted;
- parámetros validados;
- aislamiento por namespace;
- secretos fuera del prompt;
- registro de cada llamada a herramienta;
- modelo self-hosted o política explícita de no enviar información sensible a proveedores externos.

## 8. Qué cambiaría del PVB

1. No presentar "monitoreo" como diferenciador central.
2. Presentar el agente como **orquestador de herramientas**, no como detector inteligente de amenazas.
3. Hacer explícito que la comparación de baseline pertenece al mecanismo determinista de monitoreo y no al LLM.
4. Marcar la detección automática de nuevos activos como **roadmap**, no como capacidad actual.
5. Medir el tiempo de ejecución de tareas con agente frente a tareas sin agente.
6. Medir la tasa de fallos recuperables y el costo de los reintentos.
7. Mantener la restricción de no intervenir directamente sobre activos como requisito de seguridad del MVP.
8. No afirmar un moat antes de acumular evidencia operacional.

## 9. Veredicto

El proyecto tiene coherencia técnica como **plataforma self-hosted de monitoreo + orquestación operacional sobre Kubernetes**, pero su principal hipótesis de valor todavía no está demostrada:

> **La incertidumbre crítica no es si puede construirse, sino si la capa de agente de IA aporta una mejora operacional suficientemente medible frente a scripts y plataformas de monitoreo maduras.** `[INTERNO]`

La demostración debe concentrarse en esa pregunta.

## 10. Afirmaciones que deben evitarse o permanecer como hipótesis

- "Sentinel detecta ataques." → **No**. El MVP detecta cambios en las variables monitorizadas.
- "Sentinel detecta anomalías mediante IA." → **No**.
- "Sentinel incorpora automáticamente nuevos activos." → **No en el MVP**; funcionalidad futura.
- "La IA compara el baseline." → **No**; la comparación debe pertenecer al mecanismo determinista de monitoreo.
- "Control humano = moat." → **No demostrado**.
- "10–50 activos es un mercado validado." → **No demostrado**.
- "La IA reduce costos operativos." → **No demostrado** hasta medir un flujo equivalente con y sin agente.

*Material de referencia — Tópicos Especiales en Informática*
