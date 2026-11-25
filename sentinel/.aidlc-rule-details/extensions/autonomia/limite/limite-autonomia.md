# Límite de autonomía del agente — Sentinel

## Overview
Estas reglas son restricciones bloqueantes en todas las fases de AI-DLC. No son
recomendaciones. Cada etapa DEBE verificarlas antes de presentar su mensaje de
finalización.

Derivan de los principios no negociables del Segmento 6 del PRD de Sentinel. Su
propósito es que ninguna unidad de trabajo, tarea o plan de ejecución proponga una
capacidad que cruce la frontera de autonomía definida en el PRD.

### Default Enforcement
Todas las reglas de este documento son **bloqueantes**. Si no se cumple un criterio de
verificación, es un hallazgo bloqueante: la etapa solo puede ofrecer «Request Changes».

---

## Rule AUTONOMIA-01: Sin acceso directo del agente a los activos

**Rule**: Ninguna unidad de trabajo, tarea o plan puede proponer una ruta en la que el
agente de IA alcance directamente un activo de red. La única ruta permitida es
`Agente → Tool Layer → Kubernetes → Job/Pod autorizado → Script → Activo`. La ruta
`Agente → Activo` está prohibida por principio (PRD 6.3).

**Verification**:
- Ningún plan de tareas describe una conexión del agente a una IP, hostname o endpoint de activo
- El agente no recibe credenciales, sockets ni interfaces de endpoint de los activos
- Toda ejecución sobre un activo pasa por un Job/Pod de Kubernetes con una tool autorizada
- Los artefactos de diseño (components.md, services.md, application-design.md) muestran explícitamente la Tool Layer como intermediario obligatorio

---

## Rule AUTONOMIA-02: Confirmación humana explícita antes de ejecutar

**Rule**: Toda operación ejecutable definida como sensible DEBE seguir la secuencia
`Propuesta → Explicación de herramienta y parámetros → Confirmación humana → Ejecución`.
Silencio, timeout o abandono **no constituyen aprobación** (PRD 6.4). Ninguna tarea
puede introducir una ruta que ejecute sin aprobación humana previa.

**Verification**:
- Ninguna tarea ni unidad contiene un paso que ejecute una operación sensible sin un paso previo de aprobación humana registrada
- Los planes de tareas incluyen la ruta negativa: «usuario rechaza → operación no ejecutada» y «usuario no responde → operación no ejecutada»
- Los criterios de aceptación de las tareas de operación mencionan la evidencia de aprobación (log o registro) como condición de éxito

---

## Rule AUTONOMIA-03: La IA no fabrica, modifica ni interpreta evidencia determinista

**Rule**: Los datos observados, la comparación contra baseline y los reportes se generan
por scripts/herramientas deterministas, no por el LLM. El agente puede explicar y
orquestar, pero no puede fabricar, modificar ni sustituir la evidencia (PRD 6.1, 6.9).
El agente tampoco decide si existe un ataque o una anomalía.

**Verification**:
- Ninguna tarea delega al agente la generación del reporte, la comparación de baseline o la decisión de «cambio observado»
- Las tareas que producen reportes apuntan a scripts (`report.sh`, `compare.sh`, `baseline.sh`) y no a llamadas al LLM
- Los criterios de aceptación de esas tareas comparan la salida contra la fuente determinista, no contra una descripción del agente

---

## Rule AUTONOMIA-04: Capacidades del agente delimitadas por allowlist, sin shell arbitrario

**Rule**: El agente no dispone de shell arbitrario. Toda acción se ejecuta a través de
una tool parametrizada y previamente autorizada en la allowlist, con validación de
parámetros antes de la ejecución (PRD 6.2, 6.6). Ninguna tarea puede introducir una tool
fuera de la allowlist ni un escape a shell.

**Verification**:
- Ninguna tarea propone `kubectl exec`, `kubectl run` sin esquema, o invocación de shell sin parámetros declarados
- Toda tool nueva que aparezca en un plan tiene su nombre, parámetros y validación descritos
- Las tareas incluyen al menos una prueba negativa (parámetro inválido, target inválido, tool inexistente) que debe ser rechazada antes de ejecutar

---

## Rule AUTONOMIA-05: Reintentos acotados y escalamiento obligatorio

**Rule**: La recuperación de operaciones fallidas está limitada a **tres intentos
operativos** dentro del workflow: intento inicial, primer reintento y reintento tras
ajuste permitido. Agotados los tres sin éxito, el workflow escala a un humano y no
continúa (PRD 6.7, Journey D).

**Verification**:
- Ninguna tarea propone bucles de reintento ilimitados ni «reintentar hasta que funcione»
- Los planes de tareas que involucran recuperación incluyen el contador de intentos como artefacto explícito
- Existe al menos una tarea que verifica el escalamiento al tercer fallo

---

## Rule AUTONOMIA-06: Trazabilidad completa de operaciones

**Rule**: Cada operación ejecutada debe dejar registro de: quién la inició, herramienta,
parámetros relevantes, confirmación humana, recurso Kubernetes asociado, resultado,
error y número de intento (PRD 6.8).

**Verification**:
- Ninguna tarea ejecutable queda sin un paso de registro posterior
- Los criterios de aceptación de tareas de operación mencionan el registro de auditoría como condición
- El plan de tareas distingue entre operaciones que requieren registro y operaciones de solo lectura

---

## Rule AUTONOMIA-07: Fail-safe — lo no demostrable como autorizado no se ejecuta

**Rule**: Cuando una operación no pueda demostrarse como autorizada, Sentinel no la
ejecuta (PRD 6.12). Esta regla se aplica también a los artefactos de especificación: una
tarea cuyo criterio de aceptación no sea verificable con un comando, una prueba o una
comprobación medible no se considera aprobada.

**Verification**:
- Ningún criterio de aceptación usa formulaciones como «funciona correctamente», «es usable» o «tiene buen rendimiento» sin un comando o umbral medible
- Cada tarea nombra el comando, la prueba o la comprobación que demuestra que terminó
- Los planes de tareas que tocan entornos compartidos producen un artefacto revisable (PR, diff, log), nunca un cambio directo
