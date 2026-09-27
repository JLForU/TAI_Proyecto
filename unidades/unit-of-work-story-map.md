# Sentinel — Unit of Work Story Map

> Artefacto de **Units Generation** de AI-DLC.
> Garantiza que las 65 historias del backlog estén asignadas a una sola unidad y que cada historia tenga evidencia verificable.

## Regla de cobertura

```text
PRD → BL-xxx → Unidad Ux → Tarea Ux-Txx → criterio verificable → evidencia
```

Ninguna historia puede quedar huérfana y ninguna debe pertenecer a dos unidades.

# 5. Mapa de historias a unidades

Las historias del backlog aprobado se mantienen identificadas por sus IDs `BL-*`. Cada historia
aparece exactamente en una unidad.

| Unidad | Historias asignadas |
|---|---|
| U1 | BL-001, BL-002, BL-003 |
| U2 | BL-004, BL-005, BL-006, BL-007, BL-008, BL-009, BL-010 |
| U3 | BL-011, BL-012, BL-013, BL-014, BL-015, BL-016, BL-017 |
| U4 | BL-018, BL-019, BL-020 |
| U5 | BL-021, BL-022, BL-023, BL-024, BL-025, BL-026, BL-027 |
| U6 | BL-028, BL-029, BL-030, BL-031 |
| U7 | BL-032, BL-033, BL-034, BL-035, BL-036, BL-037, BL-038, BL-039, BL-040, BL-041 |
| U8 | BL-042, BL-043, BL-044, BL-045 |
| U9 | BL-046, BL-047, BL-048, BL-049 |
| U10 | BL-050, BL-051, BL-052, BL-053, BL-054, BL-055, BL-056, BL-057, BL-058 |
| U11 | BL-059, BL-060, BL-061, BL-062, BL-063, BL-064, BL-065 |

**Cobertura:** 65 historias.  
**Historias sin unidad:** 0.  
**Historias en más de una unidad:** 0.

---

## Matriz historia → unidad → criterio operativo

| Historia | Unidad | Tareas asociadas | Evidencia/criterio representativo |
|---|---|---|---|
| BL-001 | U1 | U1-T01, U1-T02 | `test -d docs && test -d src && test -d scripts && test -d deploy && test -d tests` devuelve código 0 |
| BL-002 | U1 | U1-T03, U1-T04 | `test -s docs/prd.md` devuelve 0 y el archivo contiene el encabezado del PRD |
| BL-003 | U1 | U1-T05, U1-T06 | `./tests/run.sh --smoke` finaliza con código 0 |
| BL-004 | U2 | U2-T01, U2-T02, U2-T03 | `bash -n scripts/discovery.sh` finaliza con 0 |
| BL-005 | U2 | U2-T04, U2-T05 | `bash -n scripts/monitor.sh` finaliza con 0 |
| BL-006 | U2 | U2-T06, U2-T07 | `bash -n scripts/traffic.sh` finaliza con 0 |
| BL-007 | U2 | U2-T08, U2-T09 | `bash scripts/baseline.sh` produce 5 muestras, media `μ` y varianza `s²` |
| BL-008 | U2 | U2-T10, U2-T11, U2-T12 | `./tests/run.sh comparator` pasa sin iniciar el agente |
| BL-009 | U2 | U2-T13, U2-T14, U2-T15 | `bash -n scripts/report.sh` finaliza con 0 |
| BL-010 | U2 | U2-T16 | una prueba produce timestamp, atributo, valor anterior y valor actual |
| BL-011 | U3 | U3-T01, U3-T02 | `kubectl cluster-info` finaliza correctamente |
| BL-012 | U3 | U3-T03 | `kubectl get namespace sentinel` devuelve el recurso |
| BL-013 | U3 | U3-T04, U3-T05, U3-T06 | la construcción de la imagen termina con código 0 `[INTERNO: herramienta de build TBD]` |
| BL-014 | U3 | U3-T07, U3-T08 | `kubectl apply -f deploy/jobs/discovery.yaml --dry-run=server` finaliza con 0 |
| BL-015 | U3 | U3-T09, U3-T10 | `kubectl apply -f deploy/jobs/monitoring.yaml --dry-run=server` finaliza con 0 |
| BL-016 | U3 | U3-T11, U3-T12 | `kubectl apply -f deploy/jobs/report.yaml --dry-run=server` finaliza con 0 |
| BL-017 | U3 | U3-T13, U3-T14, U3-T15 | una prueba provoca un fallo y crea una ruta de reintento conocida |
| BL-018 | U4 | U4-T01, U4-T02 | `kubectl get configmap -n sentinel` muestra la configuración |
| BL-019 | U4 | U4-T03, U4-T04 | `helm lint deploy/helm/sentinel` finaliza con 0 |
| BL-020 | U4 | U4-T05, U4-T06, U4-T07 | `helm list -n sentinel` muestra la release |
| BL-021 | U5 | U5-T01, U5-T02 | `kubectl get sa sentinel-agent -n sentinel` devuelve el recurso |
| BL-022 | U5 | U5-T03, U5-T04 | `kubectl apply --dry-run=server -f config/rbac/` finaliza con 0 |
| BL-023 | U5 | U5-T05, U5-T06, U5-T07, U5-T08 | `kubectl auth can-i` devuelve el resultado esperado para cada operación realmente requerida |
| BL-024 | U5 | U5-T09 | un Pod que viole la política es rechazado cuando corresponde |
| BL-025 | U5 | U5-T10, U5-T11, U5-T12 | `kubectl get networkpolicy -n sentinel` muestra las políticas requeridas |
| BL-026 | U5 | U5-T13, U5-T14 | revisión del Deployment/Secrets confirma que no recibe credenciales directas de activos |
| BL-027 | U5 | U5-T15, U5-T16 | `grep -R "execute_shell" src/ deploy/` no encuentra una tool genérica implementada |
| BL-028 | U6 | U6-T01, U6-T02, U6-T03 | una ejecución incrementa las métricas de workflow iniciadas/completadas/fallidas |
| BL-029 | U6 | U6-T04, U6-T05 | una ejecución genera logs con workflow, tool, resultado e intento |
| BL-030 | U6 | U6-T06, U6-T07, U6-T08 | una operación confirmada genera usuario, timestamp y tool |
| BL-031 | U6 | U6-T09, U6-T10, U6-T11 | `kubectl get pods -n sentinel-observability` muestra Grafana en estado esperado |
| BL-032 | U7 | U7-T01, U7-T02, U7-T03 | una prueba puede invocar una tool mediante contrato explícito |
| BL-033 | U7 | U7-T04 | la tool devuelve únicamente recursos autorizados |
| BL-034 | U7 | U7-T05 | crea/ejecuta el Discovery Job autorizado y recupera el resultado |
| BL-035 | U7 | U7-T06 | crea/ejecuta el Monitoring Job autorizado con parámetros explícitos |
| BL-036 | U7 | U7-T07, U7-T08 | produce un Report Job cuyo resultado proviene del script |
| BL-037 | U7 | U7-T09 | la tool no permite exceder el contador máximo |
| BL-038 | U7 | U7-T10 | una configuración fuera de allowlist es rechazada |
| BL-039 | U7 | U7-T11, U7-T12 | el agente consume el modelo mediante una interfaz estable independiente del proveedor |
| BL-040 | U7 | U7-T13, U7-T14, U7-T15, U7-T16 | un caso normal recorre solicitud → contexto → propuesta → aprobación → tool → resultado |
| BL-041 | U7 | U7-T17, U7-T18 | un resultado con `IGNORE PREVIOUS INSTRUCTIONS` no modifica la política del agente |
| BL-042 | U8 | U8-T01, U8-T02 | la UI carga y muestra el estado básico de Sentinel |
| BL-043 | U8 | U8-T03, U8-T04, U8-T05 | la pantalla muestra tool y parámetros relevantes antes de ejecutar |
| BL-044 | U8 | U8-T06, U8-T07 | una aprobación pendiente que expira no genera ejecución |
| BL-045 | U8 | U8-T08, U8-T09 | la UI presenta operación, tool, último error e intentos |
| BL-046 | U9 | U9-T01, U9-T02 | `git status --short deploy/` muestra los artefactos esperados |
| BL-047 | U9 | U9-T03, U9-T04 | `kubectl get pods -n argocd` muestra el controlador en estado esperado |
| BL-048 | U9 | U9-T05, U9-T06 | un cambio controlado en Git modifica el estado observado en Kubernetes |
| BL-049 | U9 | U9-T07, U9-T08 | el mecanismo seleccionado queda documentado y probado sin valores reales en claro |
| BL-050 | U10 | U10-T01, U10-T02, U10-T03 | cada caso tiene ID, entrada, contexto y resultado esperado |
| BL-051 | U10 | U10-T04, U10-T05, U10-T06 | la suite detecta una tool incorrecta como fallo |
| BL-052 | U10 | U10-T07, U10-T08 | la rúbrica documenta factualidad, adherencia y relevancia |
| BL-053 | U10 | U10-T09 | todos los casos terminan sin ejecución no autorizada |
| BL-054 | U10 | U10-T10 | shell arbitrario y recursos no autorizados son rechazados |
| BL-055 | U10 | U10-T11 | los datos maliciosos no cambian la política del agente |
| BL-056 | U10 | U10-T12, U10-T13, U10-T14 | el estado inicial produce evidencia de tráfico normal |
| BL-057 | U10 | U10-T15, U10-T16, U10-T17 | el workflow determinista puede ejecutarse sin el proceso del agente |
| BL-058 | U10 | U10-T18, U10-T19, U10-T20 | el análisis calcula el tiempo mediano con y sin IA |
| BL-059 | U11 | U11-T01, U11-T02 | una ejecución recorre UI → agente → tool → Kubernetes → Job → reporte → auditoría |
| BL-060 | U11 | U11-T03 | el control termina con evidencia equivalente del objetivo funcional |
| BL-061 | U11 | U11-T04, U11-T05 | el fallo controlado produce el flujo de reintentos esperado |
| BL-062 | U11 | U11-T06, U11-T07 | la sustentación incluye al menos una prueba `can-i` positiva y una negativa |
| BL-063 | U11 | U11-T08 | existen evidencias antes/durante/después del escenario |
| BL-064 | U11 | U11-T09 | el paquete contiene datos de ambas condiciones y el cálculo de la comparación |
| BL-065 | U11 | U11-T10, U11-T11, U11-T12 | PRD, arquitectura y backlog están versionados en el repositorio final |

## Comprobación de cobertura

- Historias esperadas: **65** (`BL-001`…`BL-065`).
- Historias asignadas a una unidad: **65**.
- Historias huérfanas: **0**.
- Historias duplicadas entre unidades: **0**.
- Cada tarea `U*-T*` debe apuntar a una historia.
- Cada historia debe terminar con al menos un criterio ejecutable o comprobable.

## Nota sobre criterios

El criterio del mapa es representativo; la especificación operativa completa permanece en las tablas de tareas de `unidades-y-tareas.md`. La trazabilidad detallada se amplía en el plan de Code Generation de U5.
