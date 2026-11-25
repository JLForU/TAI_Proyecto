# Application Design Plan — Sentinel

**Fase**: INCEPTION — Application Design (Parte 1: Planning)
**Fecha**: 2026-11-07
**Estado**: APPROVED — artefactos aprobados por el usuario (2026-11-07T17:15:00Z)
**Entradas**: `requirements.md` (M1–M10), `stories.md` (ST-M1..M10 + EN-01..07), `execution-plan.md`, `aidlc-docs/inception/application-design/implementation-scope.md`, `contexto/arquitectura.md`

---

## 1. Alcance del diseño

- **Estilo propuesto**: monolito modular en el Core + colectores (Discovery, Sensor) como workloads separados que llaman al Core por HTTP. Coherente con SQLite de un solo escritor y con el alcance de sustentación.
- **Componentes a diseñar**: Core (ingesta, inventario, condiciones, métricas, reporte, GUI embebida), Discovery Worker, Traffic Sensor, GUI M10, Report Generator, capa de configuración/alcance, adaptadores de persistencia.
- **Fuera de diseño detallado**: lógica estadística fina del baseline, captura real de paquetes, RBAC avanzado y dashboards. Se detallan en Functional Design / NFR Design / Infrastructure Design.
- **Profundidad**: estándar, con métodos de alto nivel. Las reglas de negocio finas quedan para Functional Design (CONSTRUCTION).

---

## 2. Checklist del plan

- [x] Analizar contexto (requirements, stories, execution plan, arquitectura)
- [x] Identificar capacidades y áreas funcionales
- [x] Crear plan con preguntas de diseño
- [x] Recoger respuestas a los `[Answer]:`
- [x] Analizar respuestas y resolver ambigüedades
- [x] Solicitar aprobación explícita del plan
- [x] Generar `components.md`
- [x] Generar `component-methods.md`
- [x] Generar `services.md`
- [x] Generar `component-dependency.md`
- [x] Generar `application-design.md` (consolidado)
- [x] Validar completitud y consistencia (incluye Mermaid/ASCII)
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas. Si ninguna opción aplica, elige la última (`Other`) y describe tu preferencia.

## Question 1 — Límites de componentes

¿Cómo organizamos los componentes del sistema?

A) Core como monolito modular (API, inventario, condiciones, métricas, GUI y reporte en un solo proceso) + Discovery y Sensor como workloads separados (recomendado para el plazo)

B) Core dividido en microservicios separados (inventario, condiciones, métricas, GUI)

C) Un único proceso que incluye también Discovery y Sensor

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Disparo del descubrimiento desde la GUI

El Core tiene RBAC de solo lectura (`get/list/watch`). ¿Cómo se ejecuta un discovery manual sin romper ese límite?

A) El Core ejecuta el discovery en proceso (tarea en segundo plano) y la GUI lo dispara por la API; el CronJob ejecuta el mismo comando (recomendado, sin permisos extra)

B) El Core crea un Job de Kubernetes (requiere añadir `create jobs` al RBAC, fuera del perfil de solo lectura)

C) Solo el CronJob programa discovery; la GUI únicamente muestra estado (sin disparo manual)

D) Other (please describe after [Answer]: tag below)

[Answer]: A — ejecución acotada por `discovery.timeout_seconds`; estados `running/completed/timeout/failed`; un solo ciclo a la vez.

## Question 3 — Dónde se sirve la GUI

A) Embebida en el proceso del Core (Jinja + HTMX en el mismo contenedor) (recomendado)

B) Contenedor separado dentro del mismo Pod del Core

C) Deployment y Service separados para la GUI

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Estilo de API

A) REST/JSON versionado en `/api/v1` con OpenAPI generado (recomendado)

B) GraphQL

C) gRPC

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Autenticación del operador en la GUI

A) Token de operador en Secret + cookie de sesión; las acciones de escritura exigen sesión (recomendado para la demo)

B) HTTP Basic auth con contraseña hasheada en Secret

C) OAuth2 proxy / IdP externo

D) Other (please describe after [Answer]: tag below)

[Answer]: D — sin autenticación; solo demo por `kubectl port-forward`. Ajustar FR-GUI-07 / ST-M10-07: autenticación fuera de alcance de la demo.

## Question 6 — Generación del reporte

A) Síncrona en el Core al recibir la petición; Markdown y conversión a PDF en el servidor (recomendado)

B) Tarea en segundo plano en el Core + enlace de descarga cuando esté listo

C) Worker/Job separado para reportes

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Comunicación entre componentes

A) HTTP síncrono hacia el Core + Core como único escritor de SQLite; GUI y colectores consumen la API del Core (recomendado)

B) Cola de mensajes / bus de eventos entre colectores y Core

C) Other (please describe after [Answer]: tag below)

[Answer]: A — reintentos simples hasta que el Core responda; sin broker.

## Question 8 — Nivel de detalle de los métodos

A) Firmas de alto nivel y contratos de entrada/salida; reglas de negocio finas en Functional Design (recomendado)

B) Detalle completo de métodos y reglas de negocio en esta etapa

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## 3.1 Answer validation

| # | Respuesta | Consistencia |
|---|---|---|
| 1 | A | OK: monolito modular + colectores del mismo proyecto |
| 2 | A | OK: discovery en proceso, timeout configurable, sin permisos extra |
| 3 | A | OK: GUI embebida en el Core |
| 4 | A | OK: REST/JSON `/api/v1` |
| 5 | D | Conflicto resuelto: sin auth, solo `port-forward`; FR-GUI-07 / ST-M10-07 ajustados a "no exposición pública" y auth marcada fuera de alcance de la demo |
| 6 | A | OK: reporte síncrono bajo demanda |
| 7 | A | OK: HTTP directo + reintentos, sin broker |
| 8 | A | OK: firmas de alto nivel; reglas finas en Functional Design |

**Sin ambigüedades pendientes.**

---

## 4. Artefactos obligatorios a generar (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `components.md` | Componentes, propósito, responsabilidades e interfaces |
| `component-methods.md` | Firmas de métodos, propósito y tipos de entrada/salida (sin reglas finas) |
| `services.md` | Servicios, responsabilidades, interacción y orquestación |
| `component-dependency.md` | Matriz de dependencias, patrones de comunicación y flujo de datos |
| `application-design.md` | Consolidado de los cuatro documentos anteriores |

---

## 5. Gate de aprobación

1. [x] Completar todos los `[Answer]:`.
2. [x] Validar respuestas y ambigüedades.
3. [x] Aprobación explícita del plan: `Sí, apruebo` (2026-11-07T17:04:07Z).
4. [ ] Generar los artefactos de diseño.

**Estado**: APPROVED — generación autorizada. La aprobación de los artefactos se pedirá por separado al finalizar.
