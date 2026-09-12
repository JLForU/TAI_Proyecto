# <proyecto>

Proyecto de curso para **Tópicos Especiales en Informática**, orientado al desarrollo de
un producto que integre **Kubernetes** y **IA/Agentic Engineering**. La definición
concreta del producto, su problema, alcance y arquitectura se establecerán durante las
iteraciones del proyecto.

---

## Datos del curso

| Campo | Valor |
|---|---|
| Curso | Tópicos Especiales en Informática |
| Semestre | 2026-3 |
| Profesor | Luis Felipe Ariza Vesga |
| Universidad | Pontificia Universidad Javeriana |
| Ciudad | Bogotá, Colombia |
| Repositorio del curso | https://github.com/lfarizav/topicos-especiales |

## Autor: Anne Marques Da Silva

| Campo | Valor |
|---|---|
| Nombre | Anne Carolinne Marques Da Silva |
| Correo | annecmarques@javeriana.edu.co |
| Programa | MINSC |
| Repositorio personal | ... |

## Autor: Jhoseph Lizarazo

| Campo | Valor |
|---|---|
| Nombre | Jhoseph S. Lizarazo Murcia |
| Correo | jhosephs_lizarazom@javeriana.edu.co |
| Programa | MSEGD & MINSC |
| Repositorio personal | https://github.com/JLForU/TAI_Proyecto |

---

## Propósito de este repositorio

Este repositorio contiene los artefactos, investigaciones, especificaciones y material
de apoyo desarrollados durante el proyecto del curso.

El producto todavía se encuentra en etapa de definición. Por esta razón, este README
deliberadamente **no fija el nombre, problema, segmento de usuarios, arquitectura ni
alcance definitivo del producto**.

Esos elementos serán establecidos y documentados progresivamente en los entregables
correspondientes.

---

## Entregables y de dónde salen sus reglas

El curso especifica qué artefactos deben producirse y qué criterios deben seguirse.
Esta tabla relaciona cada entregable del proyecto con el lugar donde se establecen sus
reglas.

| Entregable | Archivo en este repo | Especificado en |
|---|---|---|
| Product Vision Board (PVB) | [`pvb.md`](./pvb.md) | [`modulo2/README.md`](https://github.com/lfarizav/topicos-especiales/blob/main/modulo2/README.md) · [`modulo2/INSTRUCCIONES-ENTREGA.md`](https://github.com/lfarizav/topicos-especiales/blob/main/modulo2/INSTRUCCIONES-ENTREGA.md) |
| Product Requirements Document (PRD) | [`specs/prd.md`](./specs/prd.md) | [`modulo3/README.md`](https://github.com/lfarizav/topicos-especiales/blob/main/modulo3/README.md) · [`modulo3/prompts-para-especificacion.md`](https://github.com/lfarizav/topicos-especiales/blob/main/modulo3/prompts-para-especificacion.md) |
| Investigación de validación | [`docs/overview.md`](./docs/overview.md) | [`modulo2/INSTRUCCIONES-ENTREGA.md`](https://github.com/lfarizav/topicos-especiales/blob/main/modulo2/INSTRUCCIONES-ENTREGA.md) |
| Investigación de mercado / competencia | [`docs/mercado.md`](./docs/mercado.md) | [`modulo2/INSTRUCCIONES-ENTREGA.md`](https://github.com/lfarizav/topicos-especiales/blob/main/modulo2/INSTRUCCIONES-ENTREGA.md) |
| Investigación del segmento / ICP | [`docs/icp.md`](./docs/icp.md) | [`modulo2/INSTRUCCIONES-ENTREGA.md`](https://github.com/lfarizav/topicos-especiales/blob/main/modulo2/INSTRUCCIONES-ENTREGA.md) |
| Investigación de crítica (adversarial) | [`docs/critica.md`](./docs/critica.md) | [`modulo2/INSTRUCCIONES-ENTREGA.md`](https://github.com/lfarizav/topicos-especiales/blob/main/modulo2/INSTRUCCIONES-ENTREGA.md) |
| Análisis de conflictos entre PVB e insumos | [`docs/iteracion1.md`](./docs/iteracion1.md) | [`modulo3/prompts-para-especificacion.md`](https://github.com/lfarizav/topicos-especiales/blob/main/modulo3/prompts-para-especificacion.md) |
| Investigación técnica | [`research/README.md`](./research/README.md) | Según las necesidades del producto y los requisitos del curso |
| Presentaciones | [`presentations/`](./presentations/) | Según las actividades y entregas del curso |

### Reglas de evidencia

Las investigaciones y documentos del proyecto deben distinguir claramente entre:

- **[INTERNO]** — proyecciones, hipótesis, estimaciones o decisiones propias del
  proyecto.
- **[VERIFICAR]** — afirmaciones externas que requieren comprobación mediante una fuente.
- **Fuente + fecha** — toda cifra, afirmación de mercado, costo, adopción o información
  externa relevante debe poder rastrearse hasta su fuente.

El PVB constituye la base conceptual para el PRD. Los cambios importantes en el producto
deben reflejarse primero en la documentación correspondiente antes de incorporarse a la
especificación.

---

## Estructura del repositorio

```text
tai/
├── README.md                 ← Este documento
│
├── pvb.md                    ← Product Vision Board
│
├── docs/                     ← Documentación e insumos del producto
│   ├── overview.md           ← Panorama del dominio
│   ├── mercado.md            ← Mercado y competencia
│   ├── icp.md                ← Segmento objetivo / ICP
│   ├── critica.md            ← Investigación adversarial
│   └── iteracion1.md         ← Análisis de conflictos e iteraciones
│
├── specs/
│   └── prd.md                ← Product Requirements Document
│
├── research/                 ← Investigación técnica y corpus documental
│   └── README.md             ← Índice de investigaciones y fuentes
│
└── presentations/            ← Material de apoyo para presentaciones
````

> **Nota:** La estructura anterior es una estructura inicial. Los directorios y archivos
> podrán modificarse cuando el producto quede definido y aparezcan nuevas necesidades
> documentales o técnicas.

---

## Estado actual del proyecto

**Etapa:** Definición del producto.

**Producto:** **[POR DEFINIR]**

**Problema:** **[POR DEFINIR]**

**Segmento objetivo:** **[POR DEFINIR]**

**Propuesta de valor:** **[POR DEFINIR]**

**Arquitectura:** **[POR DEFINIR]**

**Tecnologías principales:** **[POR DEFINIR]**

**Estado de implementación:** **[POR DEFINIR]**

---

## Criterios técnicos del proyecto

El producto deberá definirse considerando los requisitos fundamentales del módulo
**AI & Agentic Engineering**:

### Kubernetes

Kubernetes debe tener un papel **arquitecturalmente relevante** dentro del producto.
No debe utilizarse únicamente como mecanismo incidental para ejecutar una aplicación que
podría funcionar exactamente igual sin Kubernetes.

**Decisión específica:** **[COMPLETAR CUANDO SE DEFINA EL PRODUCTO]**

### Inteligencia artificial

La IA debe aportar una capacidad funcional defendible al producto.

La eliminación de la IA debe producir una diferencia funcional significativa respecto a
la versión que utiliza IA. La IA no debe limitarse a actuar como una interfaz
conversacional, generador de texto o componente decorativo.

**Decisión específica:** **[COMPLETAR CUANDO SE DEFINA EL PRODUCTO]**

### Agentic Engineering

Cuando el producto utilice un agente, debe quedar documentado:

* qué decisiones puede tomar;
* qué herramientas puede utilizar;
* qué información puede consultar;
* qué acciones puede ejecutar;
* qué límites tiene;
* qué decisiones requieren intervención humana;
* cómo se registra su actividad.

**Definición del agente:** **[COMPLETAR]**

---

## Investigación

La investigación del proyecto se mantendrá separada de la documentación de producto
cuando sea necesario.

Se distinguirá entre:

1. **Investigación de validación:** determina si el problema, segmento y propuesta tienen
   fundamento.
2. **Investigación adversarial:** intenta encontrar razones por las que el producto podría
   fracasar.
3. **Investigación técnica:** estudia tecnologías, arquitecturas, herramientas,
   frameworks y restricciones necesarias para implementar el producto.
4. **Documentación propia:** registra decisiones, hipótesis, experimentos y resultados
   producidos durante el proyecto.

Toda investigación deberá conservar las fuentes utilizadas y, cuando corresponda,
registrar la fecha de consulta.

---

## Principio de trabajo con IA

El desarrollo del producto seguirá el principio:

> **El agente propone, el humano aprueba.**

La IA puede ayudar a investigar, comparar alternativas, identificar conflictos, proponer
arquitecturas y generar artefactos, pero las decisiones definitivas sobre el producto,
su alcance y sus requisitos serán revisadas y aprobadas por el autor.

Las propuestas generadas por IA no se considerarán automáticamente evidencia.

---

## Historial de decisiones

Las decisiones importantes del proyecto deberán registrarse cuando afecten de manera
significativa:

* la visión del producto;
* el problema que se intenta resolver;
* el segmento objetivo;
* la arquitectura;
* el papel de Kubernetes;
* el papel de la IA;
* el alcance del MVP;
* las tecnologías principales;
* los criterios de evaluación.

### Decisiones

| Fecha           | Decisión        | Motivo          | Estado               |
| --------------- | --------------- | --------------- | -------------------- |
| **[COMPLETAR]** | **[COMPLETAR]** | **[COMPLETAR]** | Aprobada / Pendiente |
| **[COMPLETAR]** | **[COMPLETAR]** | **[COMPLETAR]** | Aprobada / Pendiente |

---

## Cronograma

| Entregable / actividad          | Fecha           | Estado      |
| ------------------------------- | --------------- | ----------- |
| Definición inicial del producto | **[COMPLETAR]** | ⬜ Pendiente |
| Product Vision Board            | **[COMPLETAR]** | ⬜ Pendiente |
| Investigación de validación     | **[COMPLETAR]** | ⬜ Pendiente |
| Investigación adversarial       | **[COMPLETAR]** | ⬜ Pendiente |
| Product Requirements Document   | **[COMPLETAR]** | ⬜ Pendiente |
| Diseño técnico                  | **[COMPLETAR]** | ⬜ Pendiente |
| Implementación MVP              | **[COMPLETAR]** | ⬜ Pendiente |
| Evaluación                      | **[COMPLETAR]** | ⬜ Pendiente |
| Presentación final              | **[COMPLETAR]** | ⬜ Pendiente |

---

## Convenciones

### Evidencia

```text
[INTERNO]   → Supuesto, proyección o estimación propia.
[VERIFICAR] → Afirmación externa pendiente de verificación.
```

### Estado de tareas

```text
⬜ Pendiente
🔄 En progreso
✅ Completado
⚠️ Requiere revisión
❌ Descartado
```

---

> **Nota de mantenimiento:** este README debe revisarse y actualizarse cuando cambie la
> estructura del proyecto, se agreguen nuevos entregables, se modifique el estado del
> producto o se adopten nuevas decisiones arquitectónicas.
>
> El README funciona como índice y punto de entrada del repositorio; no debe convertirse
> en una segunda copia del PVB, PRD o de las investigaciones.

