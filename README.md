# Sentinel — documentación del proyecto

**Versión documental:** 3.0  
**Fecha de revisión:** 2026-11-05  
**Estado:** alcance funcional consolidado; las decisiones técnicas abiertas se registran en `DECISIONES_PENDIENTES.md`.  
**Nombre:** Sentinel es provisional y no implica disponibilidad de marca o dominio.

## Propósito

Sentinel es una plataforma self-hosted y cloud-native para descubrir y monitorear activos de una red local autorizada. Mantiene inventario y evidencia estructurada, mide tráfico, registra cambios observables y genera alertas mediante reglas deterministas.

Sentinel no administra los endpoints, no cambia sus configuraciones ni aplica controles preventivos/de respuesta sobre ellos; no bloquea tráfico, no ejecuta contención, no escanea vulnerabilidades y no aplica parches. Sí se protege el propio despliegue mediante RBAC, aislamiento y endurecimiento. Los sondeos ARP/ICMP/TCP/Nmap son activos: envían paquetes y pueden generar carga o registros en los objetivos. Por eso requieren rangos, puertos, frecuencia, límites y ventanas autorizados. La captura de tráfico requiere una fuente de visibilidad explícita; no aparece automáticamente por desplegar un Pod.

## Estructura documental

| Ruta | Propósito |
|---|---|
| `docs/pvb.md` | Product Vision Board |
| `docs/overview.md` | Panorama del dominio y límites técnicos |
| `docs/mercado.md` | Alternativas, competencia y posición hipotética |
| `docs/icp.md` | Perfil de cliente ideal como hipótesis |
| `docs/critica.md` | Análisis crítico y pruebas que podrían refutar la propuesta |
| `research/fuentes.md` | Fuentes técnicas y de mercado, con fecha de consulta |
| `specs/prd.md` | Requisitos de producto consolidados |
| `specs/arquitectura.md` | Arquitectura cloud-native, Kubernetes, seguridad y observabilidad |
| `specs/backlog.md` | Backlog técnico con 47 historias verificables |
| `units/unit-of-work.md` | Definición y fronteras de nueve unidades |
| `units/unit-of-work-dependency.md` | Grafo, fases, walking skeleton y camino crítico |
| `units/unit-of-work-story-map.md` | Trazabilidad de historias, criterios y evidencias |
| `units/U04-captura-trafico-code-generation-plan.md` | Plan de construcción detallado de U4 |
| `units/unidades-y-tareas.md` | Consolidación de unidades y 47 tareas con sus predecesoras |
| `scripts/verify_unit_dag.py` | Verifica el grafo de dependencias |
| `scripts/verify_traceability.py` | Verifica IDs, titularidad, dependencias, matriz y tareas por unidad |
| `scripts/verify_document_links.py` | Verifica enlaces relativos y anclajes Markdown |
| `diagrams/*.mmd` | Diagramas Mermaid independientes |
| `DECISIONES_PENDIENTES.md` | Decisiones técnicas abiertas y condiciones de POC |
| `AUDITORIA_FINAL.md` | Registro de revisión cruzada, correcciones y verificaciones reproducibles |
| `MANIFEST.sha256` | Huellas SHA-256 de los archivos incluidos |

## Orden recomendado de lectura

1. `DECISIONES_PENDIENTES.md` para identificar bloqueos técnicos.
2. `docs/pvb.md`, `docs/overview.md`, `docs/mercado.md`, `docs/icp.md` y `docs/critica.md`.
3. `specs/prd.md`, `specs/arquitectura.md` y `specs/backlog.md`.
4. Los artefactos de unidades y el plan de construcción de U4.

## Convenciones

- `[INTERNO]`: decisión, hipótesis o proyección propia del proyecto.
- `[VERIFICAR]`: afirmación que exige validación adicional antes de tratarse como hecho.
- `TBD`: decisión todavía no tomada.
- Un dato de SO se etiqueta como declarado, inferido o desconocido; una inferencia no se presenta como certeza.
- Los eventos describen observaciones; las alertas describen reglas disparadas. Ninguno atribuye por sí solo intención maliciosa.
- Los diagramas representan la arquitectura propuesta, no un despliegue ya ejecutado.
- Los criterios que aparecen en varios artefactos cumplen funciones distintas: el backlog es la fuente de historias; el mapa comprueba cobertura; la consolidación organiza las tareas por unidad.

## Decisión de alcance

**Sentinel es un sistema de monitoreo, no de respuesta.** Kubernetes gestiona las cargas de trabajo de Sentinel; Sentinel observa la red autorizada y no administra los sistemas operativos ni la configuración de los activos observados.

## Verificaciones reproducibles

Desde la raíz del directorio:

```bash
python scripts/verify_unit_dag.py
python scripts/verify_traceability.py
python scripts/verify_document_links.py
sha256sum -c MANIFEST.sha256
```

Estas verificaciones cubren la estructura documental. No sustituyen las pruebas de despliegue, captura de paquetes ni funcionamiento real del clúster.
