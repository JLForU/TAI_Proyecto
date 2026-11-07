# Auditoría documental final — Sentinel

**Versión revisada:** 3.0  
**Fecha:** 2026-11-05  
**Resultado:** revisión documental y estática completada; las decisiones de implementación pendientes permanecen identificadas.

## 1. Alcance de la revisión

Se contrastaron los documentos de visión e investigación (`docs/`, `research/`), la especificación de producto y la arquitectura (`specs/`), el backlog, las unidades de trabajo, el plan detallado de U4, los seis diagramas Mermaid, el README, las decisiones pendientes y los scripts de validación.

La revisión buscó contradicciones funcionales, responsabilidades duplicadas, historias sin titular, dependencias inválidas, ciclos, enlaces internos rotos, duplicación textual sustantiva, inconsistencias entre diagramas y texto, y afirmaciones técnicas que excedieran la evidencia disponible.

## 2. Correcciones aplicadas

1. **Fronteras funcionales:** U3 descubre y entrega observaciones; U4 captura y agrega metadatos IP/ARP; U5 conserva el inventario histórico y los eventos fuente; U6 calcula condiciones e indicadores idempotentes; U7 configura reglas temporales, tableros y notificaciones; U8 asegura la plataforma; U9 integra y valida.
2. **Identidad e idempotencia:** U5 conserva el evento original y su `event_id`. U6 deriva indicadores sin crear una segunda copia persistente ni contabilizar repetidamente un evento reprocesado.
3. **Métricas y alertas:** los colectores envían observaciones al Core. Prometheus consulta (`GET`) el endpoint `/metrics` mediante el ServiceMonitor; no recibe los lotes de los colectores. Prometheus evalúa las reglas y su duración `for`; Alertmanager agrupa, silencia y enruta; Grafana consulta series para los dashboards.
4. **Inventario frente a métricas:** las direcciones IP, MAC, puertos y servicios detallados permanecen en registros/exportaciones estructuradas. Las etiquetas de las métricas usan dimensiones acotadas para evitar cardinalidad elevada.
5. **Descubrimiento de servicios:** el sondeo `-sV --version-light` queda reconocido como actividad de red activa. Un servicio deducido únicamente del número de puerto se etiqueta como probable; sin evidencia suficiente queda desconocido. El parseo programático consume XML de Nmap (`-oX -`).
6. **Ciclos incompletos:** un ciclo fallido o parcial no permite declarar ausentes los activos que no respondieron. `AssetMissing` requiere el número configurado de ciclos completos y exitosos.
7. **Tráfico:** se distinguen los bytes/s de paquetes IP de los mensajes ARP/s. La longitud usada para el tráfico IP y el cálculo de bytes/s están definidos en un único lugar del PRD; las observaciones detalladas conservan origen y destino.
8. **Permisos de captura:** se precisó que cambiar de namespace no habilita por sí solo `CAP_NET_RAW`. Una excepción solo se contempla si una prueba de concepto demuestra la necesidad, existe una configuración de admisión explícita y verificable, se mantienen restricciones complementarias y se limita por RBAC quién puede crear o modificar esas cargas. `CAP_NET_ADMIN` y `privileged: true` no forman parte del MVP.
9. **Diagramas y referencias:** se alinearon los flujos de consulta de métricas, la dirección de los sondeos, los componentes responsables y los tres grafos de dependencias. Se corrigieron los anclajes de la matriz de historias para que correspondan con los encabezados del backlog.
10. **Camino crítico:** se sustituyó la ruta desactualizada del backlog por la cadena de 11 historias que calcula el verificador. El propio grafo Mermaid del backlog ahora se compara automáticamente con las 14 aristas declaradas.
11. **Duplicación textual:** la definición normativa de U6 queda en `unit-of-work.md`; el documento consolidado remite a esa definición y evita repetir literalmente su bloque completo.
12. **Identificación de SO:** se aclaró que una inferencia exige un método habilitado y evidencia documentada; al no ejecutar `-O` en el perfil inicial, el valor por defecto es declarado o desconocido cuando no exista evidencia suficiente.
13. **Tareas por unidad:** se incorporó a U6 la tabla de tareas que faltaba para SN-026–SN-030. El verificador ahora comprueba que las 47 historias aparezcan una sola vez en las tareas consolidadas, bajo su unidad titular y con las mismas predecesoras directas del backlog.

## 3. Resultados verificables

Las verificaciones se ejecutan desde la raíz del repositorio:

```bash
python scripts/verify_unit_dag.py
python scripts/verify_traceability.py
python scripts/verify_document_links.py
sha256sum -c MANIFEST.sha256
```

| Verificación | Resultado |
|---|---:|
| Historias del backlog | 47 identificadores únicos |
| Unidades | 9 |
| Dependencias entre unidades | 14 |
| Ciclos en el grafo de unidades | 0 |
| Ciclos en el grafo de historias | 0 |
| Historias con titularidad primaria única | 47 de 47 |
| Historias con tarea consolidada y predecesoras coincidentes con backlog | 47 de 47 |
| Historias en cobertura y matriz de trazabilidad | 47 de 47, una vez en cada sección; titularidad y predecesoras coincidentes |
| Dependencias entre historias con correspondencia en el grafo de unidades | Todas verificadas |
| Cadena más larga de historias | 11 historias |
| Enlaces locales y anclajes Markdown | 48 comprobados; 0 rotos |
| URLs de fuentes repetidas | 0 |
| Archivos con contenido idéntico | 0 |
| Párrafos sustantivos largos duplicados entre documentos | 0 |
| Diagramas incluidos | 6; revisión estática de texto y correspondencia con el diseño |

Una ruta de mayor profundidad del backlog es:

`SN-001 → SN-002 → SN-007 → SN-008 → SN-009 → SN-021 → SN-023 → SN-028 → SN-030 → SN-035 → SN-047`

El orden topológico válido de las unidades que produce el verificador es:

`U1 → U2 → U3 → U4 → U5 → U8 → U6 → U7 → U9`

La secuencia es una ordenación válida, no una obligación de serializar unidades que pueden avanzar en paralelo una vez satisfechas sus dependencias.

## 4. Decisiones que siguen abiertas

Las siguientes cuestiones no son contradicciones documentales: se mantienen abiertas porque requieren una prueba de concepto, selección del entorno o configuración concreta.

- Fuente y transporte de visibilidad: red virtual/bridge, tráfico replicado por SPAN/TAP o mecanismo equivalente; compatibilidad con el CNI y el runtime seleccionados.
- Necesidad real de `CAP_NET_RAW` por cada colector, permisos de captura y eventual aislamiento en `sentinel-capture` con política de admisión verificable.
- CIDR, puertos TCP, frecuencia, tasa máxima, timeout y ventana autorizados para los sondeos activos.
- Habilitación o no de detección de SO mediante `-O`; permanece deshabilitada en el perfil inicial.
- Intervalo del descubrimiento periódico.
- Umbrales de tráfico y ARP, dimensión de agregación, valores `for` y comportamiento con línea base incompleta.
- Tamaño del PVC, retención de inventario/eventos/métricas, rotación de logs y política de backup.
- Esquema definitivo de lotes, timeout, reintentos e idempotencia de la ingesta.
- Receptor de notificaciones externo y su configuración.
- Virtualización o emulación de Android, macOS y Windows en la topología de demostración.
- Versiones concretas del chart, imágenes, CNI y selectores/labels de ServiceMonitor.

El detalle operativo y las condiciones de decisión están en `DECISIONES_PENDIENTES.md` y en los apartados de decisiones abiertas del PRD y la arquitectura.

## 5. Fuentes y límites de la auditoría

`research/fuentes.md` contiene 21 fichas con 23 URLs distintas. Se revisaron las referencias oficiales relevantes para Kubernetes Pod Security/RBAC/NetworkPolicy, Nmap, el cliente Python de Kubernetes, Prometheus, Prometheus Operator, Alertmanager, Helm y las herramientas de comparación.

Los seis diagramas Mermaid se inspeccionaron como texto y se compararon con la arquitectura; el grafo de dependencias se valida automáticamente contra el código del verificador. No se afirma una renderización de Mermaid porque el entorno de auditoría no dispone de un renderizador instalado.

Esta auditoría es documental y estática. No se ejecutó un despliegue real del clúster, captura en una interfaz de red física, escaneo sobre activos reales, recepción de notificaciones externas ni prueba integral de extremo a extremo. Las verificaciones reproducibles acreditan consistencia de los artefactos y estructura de trazabilidad, no el funcionamiento de una instalación todavía no desplegada.

## 6. Criterio de cierre

La versión documental 3.0 queda coherente para ser versionada como base del proyecto. Las hipótesis y decisiones no probadas continúan etiquetadas; no deben presentarse como capacidades ya demostradas. Toda modificación futura del backlog, grafo, mapa de historias o enlaces debe acompañarse de la ejecución de los cuatro comandos de verificación indicados en este informe.
