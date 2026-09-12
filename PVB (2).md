## PRODUCTO

**Nombre del producto:** NetSentinel

**Descripción en una línea:** Plataforma de monitoreo continuo de activos de una red empresarial o de laboratorio que utiliza Kubernetes para desplegar agentes de observación y una IA para analizar cambios, correlacionar información y generar reportes de seguridad basados en evidencia.

---

## 1. PROBLEMA

Una red empresarial está compuesta por múltiples dispositivos y sistemas que cambian con el tiempo: aparecen nuevos dispositivos, cambian direcciones IP, se modifican puertos disponibles, desaparecen servicios, cambian configuraciones de red o dejan de estar disponibles los mecanismos de monitoreo.

El problema no es únicamente **obtener un inventario de dispositivos**. El problema es mantener una visión continua de su estado y determinar **qué cambios son relevantes y requieren atención**.

En un escenario tradicional, la información de los dispositivos puede estar distribuida entre diferentes herramientas y registros. Un administrador debe comparar información de diferentes momentos para determinar si ocurrió un cambio y posteriormente decidir si dicho cambio representa un riesgo.

NetSentinel propone centralizar este proceso:

* Identificar los activos observables de la red.
* Recopilar información de cada activo.
* Mantener el estado conocido de los activos.
* Detectar cambios respecto al estado anterior.
* Determinar qué información adicional debe recopilarse.
* Analizar los cambios y su contexto.
* Generar un reporte fechado y basado en evidencia.

La IA no reemplaza la adquisición de información. La capa de monitoreo recopila datos y detecta cambios de manera determinística; el agente utiliza posteriormente esa información para **decidir qué investigar, qué evidencia adicional consultar, cómo correlacionar los datos y qué nivel de relevancia asignar al evento**. **[INTERNO]**

Esto permite separar el problema de **observar la red** del problema de **interpretar sus cambios**.

**¿Este problema sobrevive a las próximas 2-3 generaciones de modelos foundation?**

**[X] Sí, porque es un problema de WORKFLOW/INTEGRACIÓN, no de OUTPUT.**

Un modelo más potente podrá interpretar mejor los eventos, pero seguirá siendo necesario recopilar información de los activos, detectar cambios, consultar fuentes de evidencia, mantener historial y controlar las acciones que puede realizar un agente sobre una infraestructura.

**Durability Score (1-5): 5/5**

---

## 2. SEGMENTO TARGET

**¿Para quién es este producto?**

**Beachhead:** laboratorios académicos y pequeños equipos de administración de redes que necesitan mantener un inventario dinámico de activos y recibir análisis contextualizado de cambios en su entorno de red. **[INTERNO]**

El primer prototipo estará orientado a un **entorno de red simulado**, donde los dispositivos físicos se representan mediante Pods y servicios controlados dentro de Kubernetes.

Esto permite demostrar el comportamiento completo del sistema sin depender inicialmente de una infraestructura empresarial real.

Un escenario posterior podría extenderse a pequeñas organizaciones que no dispongan de capacidades avanzadas de monitoreo o un SOC dedicado. **[VERIFICAR]**

**NO es para:** grandes organizaciones que ya dispongan de plataformas maduras de SIEM, EDR/NDR, gestión de activos y SOC, al menos como mercado inicial. **[VERIFICAR]**

**¿Quién controla el veto de confianza?**

El **administrador de red / responsable de infraestructura o seguridad**, porque es quien debe decidir si permite que una herramienta recopile información de los activos y determine qué eventos requieren atención.

Su principal preocupación será:

> "¿Qué información está recopilando el sistema, qué puede hacer el agente con ella y qué ocurre si la IA se equivoca?"

Por ello, los permisos de los componentes de monitoreo y del agente deben estar explícitamente delimitados.

---

## 3. VENTAJA COMPETITIVA PRIMARIA

**[X] Trust**

La principal ventaja competitiva propuesta es la **confianza en el análisis**, no simplemente la capacidad de descubrir dispositivos.

El sistema puede construir confianza mediante tres elementos:

1. **Evidencia asociada a cada conclusión.** Cada reporte debe indicar qué activo presentó el cambio, qué información fue observada, cuándo fue observada y qué evidencia utilizó el agente para llegar a su conclusión. **[INTERNO]**

2. **Separación entre observación y decisión.** La adquisición de información y la detección básica de cambios se realizan mediante mecanismos determinísticos. La IA analiza posteriormente esos cambios. Esto reduce la posibilidad de que una alucinación del modelo se convierta directamente en un hecho registrado por el sistema. **[INTERNO]**

3. **Historial temporal de los activos.** El sistema puede comparar el estado actual con estados anteriores para proporcionar contexto al agente. Por ejemplo, un puerto que apareció recientemente puede ser interpretado de manera diferente a un puerto que ha estado presente durante meses. **[INTERNO]**

La confianza se construye, por tanto, mediante la relación:

**evento  evidencia → análisis → decisión → reporte**

El objetivo no es que el usuario simplemente "confíe en la IA", sino que pueda **verificar por qué la IA produjo determinada conclusión**.

El moat inicial no sería el modelo de IA —que puede ser reemplazado sino la integración del proceso de observación, historial, evidencia, análisis y trazabilidad. **[INTERNO]**

---

## 4. ARENA COMPETITIVA

**[X] Enhancer (AI-Enhanced)** — La monitorización e inventario de redes son problemas existentes. NetSentinel utiliza IA para fortalecer el proceso de análisis y priorización de los cambios detectados.

**Cómo sobrevive o complementa a los gigantes y al open source:**

* **Herramientas de descubrimiento y monitoreo de red** ya pueden identificar dispositivos, servicios y cambios. NetSentinel no intenta reinventar estas capacidades, sino utilizarlas como fuentes de información. **[VERIFICAR]**

* **SIEM, EDR/NDR y plataformas de seguridad** proporcionan capacidades mucho más amplias de detección y correlación. NetSentinel no pretende sustituir inicialmente estas plataformas, sino funcionar como una capa experimental de análisis contextual sobre los datos disponibles. **[VERIFICAR]**

* **Kubernetes** proporciona la infraestructura para ejecutar los componentes de monitoreo, los activos simulados, los servicios de almacenamiento y el agente.

* La diferenciación propuesta está en el **bucle agentic**: cuando el sistema detecta un cambio, la IA no se limita a resumirlo. Puede decidir qué evidencia adicional consultar, qué información histórica recuperar, qué activos relacionados investigar y qué nivel de relevancia asignar al evento. **[INTERNO]**

El sistema, por tanto, no compite simplemente como "otro scanner". Su propuesta es:

**monitorear → detectar cambio → investigar  correlacionar → priorizar → reportar**

**Riesgo honesto de esta arena:** muchas plataformas de seguridad están incorporando capacidades de IA y podrían ofrecer funcionalidades similares. Si el producto se limita a "usar un LLM para generar reportes de seguridad", su diferenciación sería muy débil.

La propuesta debe demostrar que el agente **toma decisiones operativas dentro del workflow de investigación**, y no solamente genera texto.

---

## 5. UX PARADIGM

**[X] Agent — La IA ejecuta tareas autónomamente dentro de límites.**

El usuario no necesita analizar manualmente cada cambio detectado.

El flujo conceptual es:

**activos → monitoreo → detección de cambio  agente → investigación  correlación → reporte**

El agente puede:

1. Recibir un evento de cambio.
2. Determinar qué activo debe investigarse.
3. Consultar información adicional mediante herramientas permitidas.
4. Recuperar información histórica del activo.
5. Consultar información relacionada con otros activos.
6. Correlacionar los datos obtenidos.
7. Determinar la relevancia del cambio.
8. Identificar cuando la evidencia es insuficiente.
9. Generar un reporte fechado con las evidencias utilizadas.

Por ejemplo, si aparece un nuevo puerto en un activo, el agente podría determinar que necesita consultar el estado anterior del activo y obtener información adicional antes de generar una conclusión. **[INTERNO]**

La interacción humana se mantiene deliberadamente limitada: el usuario puede **solicitar o visualizar el reporte**, mientras que el sistema realiza automáticamente la investigación dentro de los límites establecidos.

**No se selecciona Autonomous** porque el agente no debe modificar arbitrariamente los activos de la red ni ejecutar acciones defensivas no autorizadas.

El agente investiga y reporta; no administra la infraestructura.

Esto también establece una frontera de seguridad clara:

> **La IA puede observar e investigar, pero no puede modificar los activos monitoreados.** **[INTERNO]**

---

## 6. AI DECISION TRIANGLE

**[X] Capability**

**Trade-offs que acepto:**

* **Sacrifico velocidad:** la generación del reporte no necesita ser instantánea. Es preferible que el agente tenga tiempo suficiente para consultar diferentes fuentes de evidencia y producir un análisis contextualizado. **[INTERNO]**

* **Sacrifico costo:** una investigación puede requerir varias llamadas al modelo y varias consultas a herramientas antes de generar el reporte final. **[INTERNO]**

* **Sacrifico cobertura inicial:** el sistema comenzará con un conjunto limitado de tipos de cambios que pueda analizar correctamente, en lugar de intentar interpretar cualquier evento de red.

La prioridad es que la IA sea capaz de **investigar y contextualizar correctamente un cambio**, incluso si para ello necesita realizar varias consultas.

La capacidad es especialmente importante porque el valor del sistema no está en decir simplemente:

> "El puerto 22 está abierto."

Sino en determinar, utilizando evidencia disponible:

> "El puerto 22 apareció en este activo después de la última observación; anteriormente no estaba presente y este cambio requiere revisión."

La conclusión final debe permanecer vinculada a la evidencia disponible.

---

## 7. MODELO ECONÓMICO

**Modelo de pricing:**

**[X] Hybrid Tiered** — diferentes niveles según cantidad de activos monitoreados, volumen de eventos analizados y capacidad de almacenamiento histórico. **[INTERNO]**

Una posible estructura conceptual sería:

* **Lab:** pocos activos y almacenamiento histórico limitado.
* **Team:** mayor cantidad de activos y análisis continuo.
* **Business:** mayor volumen de eventos, historial ampliado y capacidades administrativas.
* **Enterprise:** despliegue self-hosted y controles avanzados. **[INTERNO]**

Los valores monetarios no se establecen todavía porque no existe evidencia suficiente para justificar un precio comercial.

**¿El pricing escala si tienes 10x usuarios?**

**[X] Necesita ajuste**

El principal factor de costo no sería necesariamente el número de usuarios, sino:

* número de activos;
* frecuencia de observación;
* cantidad de cambios;
* número de investigaciones realizadas por el agente;
* almacenamiento histórico;
* consumo de inferencia.

Un entorno con 100 activos que cambia constantemente puede generar considerablemente más trabajo que otro con 1.000 activos prácticamente estáticos. **[INTERNO]**

**Costo estimado por usuario/mes:** `[VERIFICAR]`

**Revenue por usuario/mes:** `[VERIFICAR]`

**Gross margin proyectado:** `[VERIFICAR]`

Para el prototipo académico, estas cifras no serán utilizadas como hechos comerciales.

---

## 8. MÉTRICAS DE ÉXITO

**Métricas de usuario:**

1. **Tiempo desde la detección del cambio hasta la generación del análisis:** mide cuánto tarda el sistema en pasar de un cambio observado a un reporte contextualizado. **[INTERNO]**

2. **Porcentaje de cambios correctamente priorizados:** proporción de eventos considerados relevantes por el sistema que coinciden con la evaluación de referencia definida para el experimento. **[INTERNO]**

**Métricas específicas de IA:**

1. **Precisión de clasificación/priorización:** porcentaje de eventos en los que el agente asigna correctamente la relevancia del cambio frente a una evaluación de referencia. **[INTERNO]**

2. **Tasa de decisiones sustentadas en evidencia:** porcentaje de conclusiones del agente que pueden vincularse directamente con información recuperada mediante las herramientas autorizadas. **[INTERNO]**

**Métrica adicional de seguridad:** **tasa de investigaciones sin evidencia suficiente**

El agente debe poder responder **"evidencia insuficiente"** en lugar de inventar una conclusión.

Esta métrica permite evaluar una propiedad especialmente importante del producto: si el sistema sabe reconocer los límites de la información disponible. **[INTERNO]**

---

## 9. RIESGOS CRÍTICOS

**1. ¿Qué pasa si el problema desaparece en 12 meses por comoditización?**

**Riesgo alto.**

Las herramientas de monitoreo, inventario y seguridad de redes están evolucionando hacia plataformas cada vez más integradas y muchas ya incorporan capacidades de IA. **[VERIFICAR: estado actual de plataformas de seguridad y network monitoring]**

Si estas plataformas incorporan agentes capaces de detectar cambios, consultar información histórica, investigar automáticamente y generar reportes con evidencia, gran parte del producto podría convertirse en una funcionalidad estándar.

**Mitigación:** no competir exclusivamente mediante un modelo de IA. El producto debe centrarse en la integración del workflow:

**telemetría  cambio → investigación agentic → evidencia  historial → decisión**

Además, el sistema debe ser independiente del modelo específico para poder sustituir el modelo de IA sin rediseñar toda la arquitectura. **[INTERNO]**

---

**2. ¿Puede un competidor replicar tu producto con la misma API en menos de 6 semanas?**

**Sí, el prototipo básico probablemente puede replicarse.**

Un equipo competente podría construir rápidamente:

* un servicio de descubrimiento;
* almacenamiento de inventario;
* detección de cambios;
* una API;
* un LLM;
* generación de reportes;
* varios Pods sobre Kubernetes.

Por tanto, Kubernetes + API + LLM **no constituyen una barrera competitiva suficiente**.

La diferenciación debe estar en el comportamiento del agente: qué decide investigar, cómo selecciona herramientas, cómo utiliza el historial, cómo maneja evidencia insuficiente y qué tan correctamente prioriza los cambios. **[INTERNO]**

La evaluación experimental debe demostrar que la capa agentic proporciona un beneficio observable frente a un sistema determinístico que simplemente detecta cambios y genera reportes estáticos.

---

**3. Si tienes éxito a escala, ¿cuál es la primera forma en que se rompe la confianza?**

Tres vectores principales:

1. **El agente genera una conclusión incorrecta sobre un evento real.**

   Un cambio legítimo podría clasificarse como amenaza o, peor aún, un cambio potencialmente peligroso podría considerarse irrelevante.

   *Mitigación:* cada conclusión debe incluir evidencia, nivel de confianza y posibilidad explícita de declarar evidencia insuficiente. **[INTERNO]**

2. **El agente es manipulado mediante información obtenida de la red.**

   Los datos observados —nombres de host, banners de servicios, respuestas DNS, información de aplicaciones, etc.— son datos externos no confiables. Si el agente interpreta directamente determinados contenidos como instrucciones, existe riesgo de manipulación del proceso de decisión.

   *Mitigación:* tratar toda información obtenida de los activos como **datos no confiables**, separar datos de instrucciones y restringir estrictamente las herramientas disponibles para el agente. **[INTERNO]**

3. **El sistema obtiene o almacena más información de la necesaria.**

   Un sistema de monitoreo puede terminar almacenando información sensible sobre dispositivos, servicios, usuarios o infraestructura.

   *Mitigación:* principio de mínimo privilegio, recopilación limitada al propósito del producto, control de acceso al historial, segmentación de componentes y políticas explícitas de retención. **[INTERNO]**

**Verdad incómoda:** el producto no gana por descubrir que existe un dispositivo o que tiene determinado puerto abierto. Existen herramientas especializadas para eso. Su valor depende de demostrar que **la IA puede convertir cambios de infraestructura en investigaciones contextualizadas y trazables**, sin inventar evidencia ni necesitar privilegios peligrosos.

Y existe una segunda verdad incómoda: **si todos los "activos empresariales" del prototipo son únicamente Pods dentro del mismo clúster Kubernetes, el proyecto demuestra arquitectura distribuida y agentic AI, pero no demuestra por sí solo monitoreo de una red empresarial real.** Por eso, el prototipo debe presentar explícitamente esos Pods como **activos de una red empresarial simulada** y evaluar posteriormente qué componentes serían necesarios para llevar el mismo workflow a una red real. **[INTERNO]**
