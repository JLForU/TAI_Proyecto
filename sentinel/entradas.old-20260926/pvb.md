Product Vision Board
====================

PRODUCTO
--------

### Nombre del producto

**[INTERNO] Nombre provisional: Sentinel**

### Descripción en una línea

**Plataforma de monitoreo continuo de activos de red, orquestada mediante Kubernetes y asistida por un agente de IA que identifica cambios en los activos y propone acciones operativas bajo control humano.**

* * *

1. PROBLEMA

-----------

### Problema que resuelvo

Los equipos de infraestructura y ciberseguridad necesitan mantener visibilidad sobre los activos que componen una red y reconocer oportunamente modificaciones en su estado. Sin embargo, la supervisión de múltiples activos puede requerir la ejecución coordinada de diferentes herramientas, consultas y procesos de recolección.

El producto establece un **estado base (baseline)** de cada activo y monitorea periódicamente seis atributos:

* IP

* MAC

* Sistema operativo

* Puertos

* Servicios

* Tráfico

Cada cinco segundos, el sistema compara el estado observado con el baseline y registra las diferencias encontradas.

El producto **no pretende determinar automáticamente si un cambio constituye un ataque**. Su función en el MVP es identificar y registrar cambios observables para que puedan ser revisados posteriormente.

Este enfoque es coherente con el concepto de _Information Security Continuous Monitoring_ de NIST, cuyo objetivo incluye proporcionar visibilidad continua sobre los activos y sobre el estado de los controles de seguridad.

### ¿El problema persistirá?

☑ Sí

### Durability Score

**4/5 [INTERNO]**

La necesidad de conocer el estado de los activos y detectar cambios en una infraestructura es transversal a redes y sistemas que evolucionan continuamente. Sin embargo, la funcionalidad básica de inventario y monitoreo puede convertirse en una capacidad estándar de plataformas de observabilidad y seguridad existentes.

La permanencia de la propuesta dependerá, por tanto, de la combinación de:

* orquestación mediante Kubernetes;

* agente de IA;

* control humano sobre las acciones;

* trazabilidad de las operaciones;

* integración con herramientas existentes.

* * *

2. SEGMENTO TARGET

------------------

### ¿Para quién?

**Segmento primario:**

* Equipos de ciberseguridad.

* Administradores de infraestructura y redes.

* Organizaciones que necesiten monitorear activos internos.

**Segmentos secundarios:**

* Laboratorios académicos de ciberseguridad.

* Laboratorios de infraestructura y redes.

* Instituciones educativas que necesiten demostrar monitoreo y orquestación de activos.

### MVP / escenario de demostración

El prototipo utilizará una red simulada compuesta por cinco activos:

| Activo simulado | Cantidad |
| --------------- | -------- |
| Android         | 2        |
| Linux           | 1        |
| Windows         | 1        |
| macOS           | 1        |
| **Total**       | **5**    |

**[INTERNO]** La implementación concreta de la simulación de estos sistemas se definirá en la etapa técnica del proyecto; el PVB no presupone que todos ellos sean implementados como contenedores Linux convencionales.

### ¿Quién controla el veto de confianza?

El **administrador de infraestructura o responsable de ciberseguridad**.

Esta persona debe poder determinar qué acciones puede ejecutar el agente sobre la infraestructura y cuáles requieren autorización explícita.

* * *

3. VENTAJA COMPETITIVA PRIMARIA

-------------------------------

### ☑ Trust

### Control humano sobre las acciones del agente

La diferenciación propuesta no consiste en afirmar que la IA interpreta mejor los eventos que un especialista.

La propuesta consiste en que el agente pueda **automatizar y coordinar operaciones sin eliminar el control humano sobre las acciones que modifican o amplían el monitoreo**.

El agente puede:

* seleccionar una herramienta disponible;

* determinar parámetros de ejecución;

* ejecutar scripts autorizados;

* consultar información del sistema;

* interpretar resultados operativos;

* detectar errores de ejecución;

* reintentar operaciones;

* proponer la siguiente acción.

Pero las acciones relevantes sobre la infraestructura permanecen bajo autorización humana.

### Ejemplo de evolución futura

Si el sistema identifica un nuevo activo:
    Nuevo activo detectado
            ↓
    Agente identifica sus características
            ↓
    Agente propone acciones
            ↓
    Usuario revisa y autoriza
            ↓
    Kubernetes crea/configura el recurso
            ↓
    Se inicia el monitoreo

Por ejemplo, el agente podría proponer la creación de un nuevo Pod encargado de monitorizar el activo.

**[FUTURO]** El producto podría incorporar dinámicamente nuevos activos mediante Pods de monitoreo gestionados por Kubernetes, siempre después de la autorización correspondiente.

La ventaja de Trust se materializa entonces en la combinación de **automatización + autorización + trazabilidad**, en lugar de autonomía irrestricta.

* * *

4. ARENA COMPETITIVA

--------------------

### ☑ Enhancer

El producto se plantea como un **complemento de tecnologías existentes**, no como un reemplazo de Kubernetes, Grafana ni de las herramientas especializadas de monitoreo.

La arquitectura combina diferentes capacidades:
                  AGENTE IA
                      │
            ┌─────────┴─────────┐
            │                   │
            ▼                   ▼
     Herramientas/scripts   Kubernetes API
            │                   │
            └─────────┬─────────┘
                      ▼
                MONITOREO
                      │
                      ▼
                   DATOS
                      │
                      ▼
                  GRAFANA

Kubernetes proporciona la infraestructura para ejecutar y gestionar workloads mediante Pods y recursos de workload. Los Pods constituyen la unidad desplegable fundamental de Kubernetes y los Jobs permiten ejecutar tareas, gestionar reintentos y ejecutar Pods en paralelo cuando corresponde.

Grafana proporciona la capa de visualización mediante dashboards y paneles que consultan y transforman datos procedentes de fuentes de información.

Por tanto:

* **Kubernetes** → orquestación.

* **Herramientas/scripts** → adquisición y procesamiento determinista.

* **Agente IA** → coordinación inteligente.

* **Grafana** → visualización.

* **Usuario** → autorización y control.

### ¿Cómo sobrevive frente a un gigante, hyperscaler u open source CNCF?

**[INTERNO]**

La propuesta no busca competir mediante la sustitución de plataformas de observabilidad consolidadas.

Su posición consiste en actuar como una capa de coordinación que:

1. integra herramientas existentes;

2. automatiza tareas operativas;

3. utiliza Kubernetes como infraestructura de ejecución;

4. introduce un agente capaz de seleccionar herramientas y parámetros;

5. conserva intervención humana sobre acciones relevantes.

Esto permite que el producto pueda evolucionar junto con el ecosistema en lugar de depender de la creación de un stack completo de observabilidad propio.

* * *

5. UX PARADIGM

--------------

### ☑ Agent

El producto utiliza un **agente de IA** porque el componente inteligente no se limita a responder preguntas.

El agente recibe una instrucción operacional, consulta el contexto disponible, selecciona las herramientas apropiadas, determina parámetros, ejecuta la operación, verifica el resultado y gestiona errores.

### Flujo de interacción

    Usuario
       │
       ▼
    Ordena ejecutar una etapa
       │
       ▼
    Agente analiza contexto
       │
       ▼
    Selecciona herramienta + parámetros
       │
       ▼
    Ejecuta operación
       │
       ▼
    Verifica resultado
       │
       ├── Correcto ──► "CHECK"
       │
       └── Error
              │
              ▼
          Reintento
              │
              ▼
       Ajuste de configuración
              │
              ▼
          Nuevo intento
              │
              ▼
          Resultado
              │
              ▼
            Usuario

**[INTERNO] Política operacional propuesta:**

1. Primer intento con la configuración normal.

2. Segundo intento manteniendo la configuración normal.

3. Tercer intento realizando un ajuste de configuración.

4. Si continúa fallando, se informa al usuario y se detiene la etapa.

El agente **no ejecuta todo el flujo de manera autónoma**. El usuario mantiene el control sobre el avance entre etapas.

* * *

6. AI DECISION TRIANGLE

-----------------------

### ☑ Capability

La prioridad del proyecto es **Capability**.

El objetivo no es utilizar IA simplemente para generar texto, sino obtener capacidades de coordinación contextual que serían más difíciles de implementar mediante una secuencia completamente rígida de scripts.

### ¿Qué capacidad aporta la IA?

El agente debe poder:

* identificar qué herramienta disponible corresponde a una tarea;

* seleccionar parámetros apropiados;

* interpretar resultados de las herramientas;

* identificar errores;

* decidir cuándo realizar un reintento permitido;

* ajustar una configuración en el último intento;

* consultar el estado de Kubernetes;

* coordinar herramientas diferentes;

* determinar qué información necesita para continuar;

* presentar el resultado de cada etapa al usuario.

### Trade-off

**[INTERNO]**

Se acepta:

* mayor latencia;

* mayor complejidad;

* costo computacional adicional;

* dependencia de un modelo de IA;

a cambio de una mayor capacidad de coordinación y adaptación del flujo operacional.

Las tareas deterministas de adquisición y comparación de datos permanecen fuera del modelo de IA cuando no sea necesario utilizar inteligencia generativa.

Esto permite separar:

**IA → decisión y coordinación**

de

**scripts → ejecución determinista y recolección**

* * *

7. MODELO ECONÓMICO

-------------------

### ☑ Hybrid Tiered

**[INTERNO] Modelo conceptual**

| Nivel               | Características                                                     |
| ------------------- | ------------------------------------------------------------------- |
| **Academic / Free** | Número limitado de activos, monitoreo básico y uso educativo        |
| **Professional**    | Mayor cantidad de activos, automatización y capacidades del agente  |
| **Enterprise**      | Mayor escala, integración, control de permisos, auditoría y soporte |

La elección de un modelo escalonado es consistente con la existencia de diferentes modelos comerciales en plataformas de observabilidad actuales. Por ejemplo, New Relic combina usuarios, ingestión de datos y capacidades adicionales según edición, mientras Grafana Cloud factura diferentes componentes según unidades de consumo como usuarios activos, series métricas, GB de logs u horas de host.

### ¿Cómo escala 10×?

**[INTERNO]**

La unidad principal de crecimiento propuesta será el número de **activos monitorizados**.
    MVP
    5 activos

          ↓ 10×

    50 activos

          ↓

    500 activos

          ↓

    5.000 activos

El incremento de activos requeriría aumentar la capacidad de ejecución y coordinación de Pods, recolección de datos y almacenamiento/visualización.

La arquitectura basada en Kubernetes permite gestionar workloads mediante recursos que mantienen el estado deseado y administran grupos de Pods.

### Costo por usuario / mes

**[VERIFICAR]**

El costo real dependerá de:

* modelo de IA utilizado;

* infraestructura Kubernetes;

* almacenamiento;

* volumen de telemetría;

* frecuencia de monitoreo;

* número de activos;

* retención de información;

* servicios externos utilizados.

### Revenue por usuario / mes

**[INTERNO]**

Se establecerá posteriormente a partir del costo real de infraestructura y del segmento comercial objetivo.

### Gross margin

**[INTERNO]**

La meta comercial deberá calcularse posteriormente con datos reales de infraestructura y consumo del modelo de IA.

No se fija todavía un porcentaje para evitar presentar como dato de mercado una proyección que aún no ha sido validada.

* * *

8. MÉTRICAS DE ÉXITO

--------------------

### User Metrics

#### 1. Cobertura de monitoreo

**Porcentaje de activos esperados que tienen sus seis atributos monitorizados.**
    Cobertura =
    activos monitorizados / activos identificados × 100

**Objetivo MVP:**

**[INTERNO] ≥ 90 %**

para los cinco activos simulados.

* * *

#### 2. Detección de cambios

**Porcentaje de cambios deliberadamente introducidos que son registrados correctamente por el sistema.**
    Tasa de detección =
    cambios registrados / cambios introducidos × 100

**Objetivo MVP:**

**[INTERNO] ≥ 95 %**

para los cambios definidos en las pruebas.

Esta métrica mide la capacidad del sistema para reconocer diferencias respecto al baseline; **no mide la capacidad de determinar si el cambio constituye un ataque**.

* * *

### AI Metrics

#### 1. Éxito de ejecución de tareas

**Porcentaje de etapas en las que el agente selecciona correctamente las herramientas y parámetros necesarios y obtiene un resultado válido.**
    Éxito =
    etapas completadas correctamente /
    etapas ejecutadas × 100

**Objetivo MVP:**

**[INTERNO] ≥ 90 %**

* * *

#### 2. Recuperación ante errores

**Porcentaje de fallos recuperables en los que el agente consigue completar la operación utilizando la política de reintentos definida.**
    Recuperación =
    fallos recuperados mediante reintento /
    fallos recuperables × 100

**Objetivo MVP:**

**[INTERNO] ≥ 80 %**

El agente dispondrá de un máximo de tres intentos:

1. ejecución normal;

2. reintento;

3. ajuste de configuración + reintento.

* * *

9. RIESGOS CRÍTICOS

-------------------

### ¿Qué ocurre si el problema desaparece en 12 meses porque se vuelve commodity?

Las capacidades básicas de inventario, monitoreo y visualización ya forman parte de un mercado maduro de observabilidad.

**Riesgo: Alto [INTERNO]**

La respuesta propuesta es diferenciar el producto mediante:

* coordinación basada en agentes;

* Kubernetes como infraestructura de ejecución;

* integración de herramientas existentes;

* control humano;

* trazabilidad de las acciones;

* capacidad futura de incorporar nuevos activos mediante Pods.

La propuesta no depende exclusivamente de inventariar o visualizar activos.

* * *

### ¿Puede un competidor replicarlo utilizando las mismas APIs en menos de seis semanas?

**Sí, potencialmente. [INTERNO]**

El uso de Kubernetes, Grafana, APIs y herramientas de monitoreo abiertas reduce las barreras técnicas para construir una solución funcional similar.

La defensa propuesta no será la exclusividad de una tecnología concreta, sino la combinación de:

* flujo operacional;

* integración de herramientas;

* configuración;

* políticas de autorización;

* experiencia de uso;

* lógica de coordinación del agente;

* trazabilidad.

**[VERIFICAR]** La velocidad real de replicación deberá validarse mediante investigación competitiva posterior.

* * *

### Si el producto tiene éxito a escala, ¿cuál sería el primer punto de ruptura de confianza?

**El primer punto de ruptura sería una acción incorrecta del agente sobre la infraestructura.**

Ejemplos:

* seleccionar una herramienta incorrecta;

* utilizar parámetros incorrectos;

* crear un recurso Kubernetes no autorizado;

* interpretar incorrectamente un resultado;

* modificar una configuración que no debía modificarse;

* continuar una operación después de un resultado ambiguo.

Por esta razón, el diseño incorpora:

* intervención humana;

* ejecución por etapas;

* herramientas explícitamente disponibles;

* parámetros controlados;

* política limitada de reintentos;

* reporte del resultado de cada etapa;

* separación entre adquisición determinista y decisión asistida por IA.

La confianza no depende únicamente de que el agente "acierte", sino de que **el usuario conserve capacidad de supervisión y autorización sobre las acciones relevantes**.

* * *

CHECKLIST
---------

* Producto seleccionado.

* Problema definido.

* Segmento target definido.

* Veto de confianza definido.

* Ventaja primaria seleccionada: **Trust**.

* Arena competitiva seleccionada: **Enhancer**.

* Paradigma UX seleccionado: **Agent**.

* Prioridad del AI Decision Triangle seleccionada: **Capability**.

* Modelo económico seleccionado: **Hybrid Tiered**.

* Métricas de usuario definidas.

* Métricas de IA definidas.

* Riesgos críticos identificados.

* MVP delimitado a cinco activos simulados.

* Seis atributos de monitoreo definidos.

* Baseline y comparación cada cinco segundos definidos.

* Detección de cambios diferenciada de detección de ataques.

* Control humano sobre acciones del agente definido.

* Visión futura de incorporación de nuevos activos mediante Kubernetes definida.

* Investigación externa utilizada para validar conceptos fundamentales.

* Investigación competitiva profunda.

* Validación de precios y costos reales.

* Validación experimental de las métricas propuestas.

* PRD.

* Diseño técnico definitivo.

* Investigación adversarial del uso de IA.
