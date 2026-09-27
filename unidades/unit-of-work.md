# Sentinel — Unit of Work

> Artefacto de **Units Generation** de AI-DLC.
> Define las fronteras de las unidades de trabajo de Sentinel y, sobre todo, qué NO hace cada una.
> Las unidades se derivan del PRD y la arquitectura aprobados del producto.

## Regla de calidad

Una unidad es una frontera de responsabilidad que puede construirse, probarse y revisarse sin apropiarse de una responsabilidad perteneciente a otra unidad. Cada unidad declara responsabilidad, exclusiones, dependencias, historias y criterio de finalización.

# 1. Panorama

Sentinel se descompone en **11 unidades de trabajo**:

| # | Unidad | Tipo | Módulo del curso principal | Se implementa como |
|---|---|---|---|---|
| U1 | Base de proyecto y contratos | Fundación | Base / M4–5 | repositorio + estructura de pruebas |
| U2 | Motor de monitoreo determinista | Cadena | M4–5 | scripts + herramientas de ejecución |
| U3 | Kubernetes y workloads | Cadena | M4–5 | Pods/Jobs + configuración |
| U4 | Aplicación cloud-native y Helm | Cadena | M6 | Helm + workloads |
| U5 | Puerta de autonomía y seguridad Kubernetes | Transversal/cadena | M7 | RBAC + ServiceAccounts + policies + pruebas |
| U6 | Observabilidad y auditoría | Transversal | M8 | métricas + logs + auditoría + Grafana |
| U7 | Tool Layer y agente IA | Cadena | M8 / Agentic Engineering | Deployment + tools + adapter LLM |
| U8 | Interfaz y control humano | Cadena | M8 / Agentic Engineering | UI + workflow de aprobación |
| U9 | GitOps y entrega reproducible | Transversal | M8 | Argo CD + Git |
| U10 | Evaluación, red teaming y validación experimental | Transversal | M8 / cierre | tests + dataset + experimentos |
| U11 | Integración y sustentación | Terminal | Sesión 16 | workflow E2E + evidencia final |

## 1.1 Regla de frontera

Cada unidad declara:

1. qué responsabilidad posee;
2. qué no hace;
3. de qué unidades depende;
4. qué historias implementa;
5. qué evidencia demuestra que terminó.

---

---

# 6. U1 — Base de proyecto y contratos

- **Responsabilidad:** crear la estructura de repositorio, especificaciones versionadas y mecanismo mínimo de pruebas.
- **Qué NO hace:** no ejecuta workloads, no consulta activos, no contiene lógica del agente ni toma decisiones de seguridad.
- **Depende de:** ninguna.
- **Historias:** BL-001, BL-002, BL-003.
- **Camino crítico:** Sí.
- **Terminada cuando:** el repositorio tiene la estructura definida, PRD/arquitectura versionados y un runner de pruebas mínimo ejecutable.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U1-T01 | Crear estructura raíz del repositorio | `test -d docs && test -d src && test -d scripts && test -d deploy && test -d tests` devuelve código 0 | BL-001 |
| U1-T02 | Crear subdirectorios funcionales `[INTERNO]` | `test -d src/agent && test -d src/tools && test -d src/monitoring` devuelve 0 | BL-001 |
| U1-T03 | Incorporar PRD aprobado | `test -s docs/prd.md` devuelve 0 y el archivo contiene el encabezado del PRD | BL-002 |
| U1-T04 | Incorporar arquitectura aprobada | `test -s docs/arquitectura.md` devuelve 0 y contiene `# Arquitectura` | BL-002 |
| U1-T05 | Crear runner mínimo de pruebas `[INTERNO]` | `./tests/run.sh --smoke` finaliza con código 0 | BL-003 |
| U1-T06 | Documentar convención de ejecución | `grep -n "tests/run.sh" README.md` devuelve al menos una referencia | BL-003 |

---

---

# 7. U2 — Motor de monitoreo determinista

- **Responsabilidad:** producir la evidencia técnica de Sentinel: discovery, mediciones, tráfico, baseline, comparación, eventos y reportes.
- **Qué NO hace:** no utiliza el LLM, no orquesta Kubernetes y no autoriza acciones.
- **Depende de:** U1.
- **Historias:** BL-004, BL-005, BL-006, BL-007, BL-008, BL-009, BL-010.
- **Camino crítico:** Sí.
- **Terminada cuando:** un workflow determinista sin agente puede descubrir, medir, comparar y generar un reporte verificable.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U2-T01 | Crear script de discovery | `bash -n scripts/discovery.sh` finaliza con 0 | BL-004 |
| U2-T02 | Ejecutar discovery contra la topología de laboratorio | `scripts/discovery.sh > artifacts/discovery.txt` genera un archivo no vacío | BL-004 |
| U2-T03 | Verificar campos básicos del discovery | la salida contiene IP, MAC y los demás campos implementados para la topología | BL-004 |
| U2-T04 | Crear script de monitoreo periódico | `bash -n scripts/monitor.sh` finaliza con 0 | BL-005 |
| U2-T05 | Verificar intervalo de 5 segundos | una ejecución de prueba genera 5 timestamps con separación temporal aproximada de 5 s | BL-005 |
| U2-T06 | Implementar captura de tráfico | `bash -n scripts/traffic.sh` finaliza con 0 | BL-006 |
| U2-T07 | Verificar campos de tráfico | una ejecución contiene bytes/s, origen, destino y protocolo | BL-006 |
| U2-T08 | Implementar cálculo del baseline | `bash scripts/baseline.sh` produce 5 muestras, media `μ` y varianza `s²` | BL-007 |
| U2-T09 | Mantener el umbral como configuración pendiente | el criterio de umbral permanece marcado `[TBD]` hasta su decisión | BL-007 |
| U2-T10 | Implementar comparator independiente del agente | `./tests/run.sh comparator` pasa sin iniciar el agente | BL-008 |
| U2-T11 | Probar cambio positivo | una modificación conocida produce un evento de cambio | BL-008 |
| U2-T12 | Probar estado sin cambio | dos estados equivalentes no producen evento | BL-008 |
| U2-T13 | Implementar generador de reporte plano | `bash -n scripts/report.sh` finaliza con 0 | BL-009 |
| U2-T14 | Verificar esquema del reporte | la cabecera contiene IP, MAC, protocolo, puerto, tiempo y tráfico | BL-009 |
| U2-T15 | Verificar correspondencia reporte-medición | una prueba compara un valor fuente con la fila correspondiente y finaliza con 0 | BL-009 |
| U2-T16 | Registrar cambio observado | una prueba produce timestamp, atributo, valor anterior y valor actual | BL-010 |

---

---

# 8. U3 — Kubernetes y workloads

- **Responsabilidad:** ejecutar el workflow determinista mediante Kubernetes y convertir scripts en workloads reproducibles.
- **Qué NO hace:** no decide qué operación debe ejecutar la IA, no gestiona políticas de seguridad completas y no sustituye Tool Layer.
- **Depende de:** U1, U2.
- **Historias:** BL-011 a BL-017.
- **Camino crítico:** Sí.
- **Terminada cuando:** Discovery, Monitoring, Report y Recovery pueden ejecutarse como workloads y sus resultados son recuperables.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U3-T01 | Preparar clúster de laboratorio | `kubectl cluster-info` finaliza correctamente | BL-011 |
| U3-T02 | Verificar nodos disponibles | `kubectl get nodes` muestra nodos utilizables | BL-011 |
| U3-T03 | Crear namespace `sentinel` | `kubectl get namespace sentinel` devuelve el recurso | BL-012 |
| U3-T04 | Crear imagen del workload de monitoreo | la construcción de la imagen termina con código 0 `[INTERNO: herramienta de build TBD]` | BL-013 |
| U3-T05 | Ejecutar un Job de prueba | `kubectl get job -n sentinel` muestra el Job completado | BL-013 |
| U3-T06 | Verificar salida del Job | `kubectl logs job/<nombre> -n sentinel` devuelve la salida del script | BL-013 |
| U3-T07 | Crear Discovery Job | `kubectl apply -f deploy/jobs/discovery.yaml --dry-run=server` finaliza con 0 | BL-014 |
| U3-T08 | Ejecutar Discovery Job | `kubectl wait --for=condition=complete job/discovery -n sentinel --timeout=120s` finaliza con 0 | BL-014 |
| U3-T09 | Crear Monitoring Job | `kubectl apply -f deploy/jobs/monitoring.yaml --dry-run=server` finaliza con 0 | BL-015 |
| U3-T10 | Ejecutar Monitoring Job | `kubectl get jobs -n sentinel` muestra estado esperado y los logs contienen muestras | BL-015 |
| U3-T11 | Crear Report Job | `kubectl apply -f deploy/jobs/report.yaml --dry-run=server` finaliza con 0 | BL-016 |
| U3-T12 | Verificar Report Job | el Job genera un artefacto de reporte recuperable | BL-016 |
| U3-T13 | Crear flujo de recovery | una prueba provoca un fallo y crea una ruta de reintento conocida | BL-017 |
| U3-T14 | Verificar límite de tres intentos | el experimento registra como máximo intento inicial + dos reintentos | BL-017 |
| U3-T15 | Verificar escalamiento posterior | después del límite no se crea un nuevo Job automáticamente | BL-017 |

---

---

# 9. U4 — Aplicación cloud-native y Helm

- **Responsabilidad:** empaquetar Sentinel como aplicación reproducible y configurable en Kubernetes.
- **Qué NO hace:** no define el modelo LLM, no sustituye RBAC y no implementa el flujo de aprobación humana.
- **Depende de:** U3.
- **Historias:** BL-018, BL-019, BL-020.
- **Camino crítico:** Sí.
- **Terminada cuando:** configuración no sensible está separada de las imágenes y Sentinel puede desplegarse mediante Helm.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U4-T01 | Crear ConfigMap de parámetros no sensibles | `kubectl get configmap -n sentinel` muestra la configuración | BL-018 |
| U4-T02 | Verificar separación imagen/configuración | el manifiesto muestra que intervalo y muestras provienen del ConfigMap | BL-018 |
| U4-T03 | Crear Helm Chart | `helm lint deploy/helm/sentinel` finaliza con 0 | BL-019 |
| U4-T04 | Renderizar manifests | `helm template sentinel deploy/helm/sentinel` finaliza sin errores | BL-019 |
| U4-T05 | Desplegar Sentinel mediante Helm | `helm list -n sentinel` muestra la release | BL-020 |
| U4-T06 | Verificar Pods del despliegue | `kubectl get pods -n sentinel` muestra los workloads en estado esperado | BL-020 |
| U4-T07 | Desinstalar y reinstalar | `helm uninstall` y posterior `helm install` terminan correctamente | BL-020 |

---

---

# 10. U5 — Puerta de autonomía y seguridad Kubernetes

- **Responsabilidad:** imponer el límite de autonomía del agente mediante Tool Layer, RBAC, ServiceAccounts, Pod Security y Network Policies.
- **Qué NO hace:** no ejecuta acciones sobre activos por sí misma, no aprueba operaciones y no genera evidencia de monitoreo.
- **Depende de:** U3, U4.
- **Historias:** BL-021 a BL-027.
- **Camino crítico:** Sí.
- **Terminada cuando:** existen controles independientes de aplicación y plataforma, y las pruebas positivas/negativas demuestran la frontera de autonomía.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U5-T01 | Crear ServiceAccount dedicado del agente | `kubectl get sa sentinel-agent -n sentinel` devuelve el recurso | BL-021 |
| U5-T02 | Asociar ServiceAccount al Deployment | la especificación del Deployment muestra la ServiceAccount del agente | BL-021 |
| U5-T03 | Crear RBAC mínimo inicial | `kubectl apply --dry-run=server -f config/rbac/` finaliza con 0 | BL-022 |
| U5-T04 | Verificar ausencia de privilegio administrativo amplio | una comprobación `auth can-i` no concede acceso administrativo global | BL-022 |
| U5-T05 | Verificar permisos positivos | `kubectl auth can-i` devuelve el resultado esperado para cada operación realmente requerida | BL-023 |
| U5-T06 | Verificar permiso de escritura no autorizado | `kubectl auth can-i create deployments --as=system:serviceaccount:sentinel:sentinel-agent -n sentinel` devuelve `no` | BL-023 |
| U5-T07 | Negar lectura de Secrets no requerida | `kubectl auth can-i get secrets --as=system:serviceaccount:sentinel:sentinel-agent -n sentinel` devuelve `no` | BL-023 |
| U5-T08 | Negar creación de bindings | `kubectl auth can-i create clusterrolebindings --as=system:serviceaccount:sentinel:sentinel-agent` devuelve `no` | BL-023 |
| U5-T09 | Aplicar Pod Security | un Pod que viole la política es rechazado cuando corresponde | BL-024 |
| U5-T10 | Aplicar NetworkPolicy | `kubectl get networkpolicy -n sentinel` muestra las políticas requeridas | BL-025 |
| U5-T11 | Probar comunicación permitida | el flujo autorizado entre componentes completa correctamente | BL-025 |
| U5-T12 | Probar comunicación denegada | una conexión fuera de la política falla | BL-025 |
| U5-T13 | Eliminar credenciales de endpoint del contexto del agente | revisión del Deployment/Secrets confirma que no recibe credenciales directas de activos | BL-026 |
| U5-T14 | Probar intento de acceso directo al endpoint | una prueba de acceso directo desde el agente falla | BL-026 |
| U5-T15 | Verificar ausencia de shell arbitrario | `grep -R "execute_shell" src/ deploy/` no encuentra una tool genérica implementada | BL-027 |
| U5-T16 | Probar solicitud arbitraria | un caso de comando libre es rechazado antes de ejecutar | BL-027 |

> **Dos capas, a propósito:** la Tool Layer deberá rechazar capacidades fuera de su contrato y
> RBAC deberá rechazar la operación en Kubernetes. Ninguna capa debe depender de la otra para
> representar por sí sola la frontera de seguridad.

---

---

# 11. U6 — Observabilidad y auditoría

- **Responsabilidad:** hacer observable el sistema y conservar trazabilidad de workflows, tools, autorizaciones, errores y resultados.
- **Qué NO hace:** no diagnostica ataques, no decide acciones y no modifica el baseline.
- **Depende de:** U3, U5.
- **Historias:** BL-028, BL-029, BL-030, BL-031.
- **Camino crítico:** Sí.
- **Terminada cuando:** las métricas, logs, auditoría y Grafana permiten reconstruir una ejecución real.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U6-T01 | Instrumentar métricas de workflow | una ejecución incrementa las métricas de workflow iniciadas/completadas/fallidas | BL-028 |
| U6-T02 | Instrumentar métricas de tools | una tool call incrementa contadores de llamada, éxito o error | BL-028 |
| U6-T03 | Instrumentar reintentos y escalamiento | un escenario de recovery modifica los contadores correspondientes | BL-028 |
| U6-T04 | Estandarizar logs operacionales | una ejecución genera logs con workflow, tool, resultado e intento | BL-029 |
| U6-T05 | Verificar ausencia de secretos en logs | una búsqueda controlada no encuentra los patrones de secretos definidos | BL-029 |
| U6-T06 | Registrar auditoría de aprobación | una operación confirmada genera usuario, timestamp y tool | BL-030 |
| U6-T07 | Registrar rechazo y error | un rechazo y un fallo de herramienta quedan diferenciados | BL-030 |
| U6-T08 | Registrar resultado Kubernetes | una ejecución permite relacionar la operación con el Job/Pod correspondiente | BL-030 |
| U6-T09 | Desplegar Grafana | `kubectl get pods -n sentinel-observability` muestra Grafana en estado esperado | BL-031 |
| U6-T10 | Publicar métrica de tráfico | la fuente de datos contiene la métrica de tráfico definida | BL-031 |
| U6-T11 | Verificar visualización | el dashboard muestra valores de una ejecución real de laboratorio | BL-031 |

---

---

# 12. U7 — Tool Layer y agente IA

- **Responsabilidad:** convertir solicitudes del usuario en operaciones autorizadas y coordinar el workflow mediante el agente.
- **Qué NO hace:** no actúa directamente sobre endpoints, no genera la evidencia técnica, no compara el baseline y no ejecuta shell arbitrario.
- **Depende de:** U2, U3, U5, U6.
- **Historias:** BL-032 a BL-041.
- **Camino crítico:** Sí.
- **Terminada cuando:** existe un loop de agente funcional, limitado y auditable que puede ejecutar las tools aprobadas sin superar la frontera de autonomía.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U7-T01 | Crear interfaz de Tool Layer | una prueba puede invocar una tool mediante contrato explícito | BL-032 |
| U7-T02 | Rechazar tool no registrada | una llamada a un nombre inexistente termina en rechazo antes de Kubernetes | BL-032 |
| U7-T03 | Validar parámetros de tool | una entrada inválida no produce una llamada al recurso Kubernetes | BL-032 |
| U7-T04 | Implementar `get_cluster_state()` | la tool devuelve únicamente recursos autorizados | BL-033 |
| U7-T05 | Implementar `discover_assets()` | crea/ejecuta el Discovery Job autorizado y recupera el resultado | BL-034 |
| U7-T06 | Implementar `start_monitoring()` | crea/ejecuta el Monitoring Job autorizado con parámetros explícitos | BL-035 |
| U7-T07 | Implementar `generate_report()` | produce un Report Job cuyo resultado proviene del script | BL-036 |
| U7-T08 | Verificar integridad del reporte tras pasar por la tool | la salida antes y después del paso del agente coincide en el conjunto de prueba | BL-036 |
| U7-T09 | Implementar `restart_monitoring_job()` | la tool no permite exceder el contador máximo | BL-037 |
| U7-T10 | Implementar `update_monitoring_config()` | una configuración fuera de allowlist es rechazada | BL-038 |
| U7-T11 | Crear adapter del LLM `[TBD]` | el agente consume el modelo mediante una interfaz estable independiente del proveedor | BL-039 |
| U7-T12 | Configurar proveedor/modelo fuera de imagen | la configuración del modelo no aparece hardcodeada en la imagen | BL-039 |
| U7-T13 | Implementar loop mínimo de agente | un caso normal recorre solicitud → contexto → propuesta → aprobación → tool → resultado | BL-040 |
| U7-T14 | Verificar que la ejecución requiere aprobación | una prueba sin confirmación no produce tool call ejecutable | BL-040 |
| U7-T15 | Integrar recovery con el loop | un error de tool inicia el flujo de reintento limitado | BL-040 |
| U7-T16 | Integrar escalamiento | un fallo persistente termina en estado de escalamiento | BL-040 |
| U7-T17 | Tratar resultados de tools como datos no confiables | un resultado con `IGNORE PREVIOUS INSTRUCTIONS` no modifica la política del agente | BL-041 |
| U7-T18 | Registrar ataque de prompt injection indirecto | el caso adversarial deja evidencia sin ejecutar la operación inyectada | BL-041 |

---

---

# 13. U8 — Interfaz y control humano

- **Responsabilidad:** exponer el workflow al operador y convertir la aprobación humana en una condición explícita de ejecución.
- **Qué NO hace:** no ejecuta directamente comandos, no diagnostica ataques y no concede permisos al agente.
- **Depende de:** U6, U7.
- **Historias:** BL-042 a BL-045.
- **Camino crítico:** Sí.
- **Terminada cuando:** el usuario puede iniciar, aprobar, rechazar, abandonar y recibir un escalamiento de un workflow completo.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U8-T01 | Crear interfaz mínima de operación | la UI carga y muestra el estado básico de Sentinel | BL-042 |
| U8-T02 | Permitir inicio de workflow | una acción de UI genera una solicitud observable en logs | BL-042 |
| U8-T03 | Mostrar operación propuesta | la pantalla muestra tool y parámetros relevantes antes de ejecutar | BL-043 |
| U8-T04 | Implementar aprobación explícita | aprobar genera transición a ejecución autorizada | BL-043 |
| U8-T05 | Implementar rechazo explícito | rechazar no produce tool call ejecutable | BL-043 |
| U8-T06 | Implementar expiración segura | una aprobación pendiente que expira no genera ejecución | BL-044 |
| U8-T07 | Registrar abandono/timeout | el evento de expiración queda registrado | BL-044 |
| U8-T08 | Mostrar contexto de escalamiento | la UI presenta operación, tool, último error e intentos | BL-045 |
| U8-T09 | Bloquear nuevos intentos después del escalamiento | una prueba posterior no genera ejecución automática | BL-045 |

---

---

# 14. U9 — GitOps y entrega reproducible

- **Responsabilidad:** mantener el estado declarativo de Sentinel en Git y reconciliarlo mediante Argo CD.
- **Qué NO hace:** no modifica activos mediante el agente, no fusiona cambios automáticamente y no almacena secretos reales en claro.
- **Depende de:** U4, U5.
- **Historias:** BL-046 a BL-049.
- **Camino crítico:** Sí para la entrega final.
- **Terminada cuando:** un despliegue puede reproducirse desde Git y una reversión versionada restaura el estado deseado.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U9-T01 | Versionar Helm/manifests declarativos | `git status --short deploy/` muestra los artefactos esperados | BL-046 |
| U9-T02 | Verificar ausencia de Secrets reales en Git | una búsqueda controlada no encuentra secretos reales en el repositorio | BL-046 |
| U9-T03 | Desplegar Argo CD `[INTERNO]` | `kubectl get pods -n argocd` muestra el controlador en estado esperado | BL-047 |
| U9-T04 | Crear Application de Sentinel | el estado de Argo CD identifica repositorio y destino previstos | BL-047 |
| U9-T05 | Verificar reconciliación | un cambio controlado en Git modifica el estado observado en Kubernetes | BL-048 |
| U9-T06 | Ejecutar rollback versionado | después de revertir el commit, Kubernetes vuelve al estado esperado | BL-048 |
| U9-T07 | Verificar estrategia de Secrets `[TBD]` | el mecanismo seleccionado queda documentado y probado sin valores reales en claro | BL-049 |
| U9-T08 | Inspeccionar imagen por secretos `[INTERNO]` | la revisión del artefacto publicado no encuentra las credenciales de prueba | BL-049 |

---

---

# 15. U10 — Evaluación, red teaming y validación experimental

- **Responsabilidad:** evaluar comportamiento, seguridad y valor operacional del agente y del sistema.
- **Qué NO hace:** no introduce nuevas funcionalidades de producto; mide las existentes.
- **Depende de:** U2, U5, U6, U7, U8.
- **Historias:** BL-050 a BL-058.
- **Camino crítico:** Sí.
- **Terminada cuando:** existe un dataset con ground truth, pruebas automáticas/humanas, red teaming, escenario ARP y comparación con/sin IA con evidencia reproducible.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U10-T01 | Definir estructura del dataset | cada caso tiene ID, entrada, contexto y resultado esperado | BL-050 |
| U10-T02 | Añadir casos normales y de error | el dataset contiene casos de workflow normal, error, rechazo y ambigüedad | BL-050 |
| U10-T03 | Añadir casos de prompt injection | existen casos donde datos de tools contienen texto manipulador | BL-050 |
| U10-T04 | Automatizar validación de tool selection | la suite detecta una tool incorrecta como fallo | BL-051 |
| U10-T05 | Automatizar validación de parámetros | la suite detecta parámetros inválidos como fallo | BL-051 |
| U10-T06 | Automatizar validación de aprobación | la suite falla si se ejecuta una operación sin confirmación | BL-051 |
| U10-T07 | Crear rúbrica de revisión humana | la rúbrica documenta factualidad, adherencia y relevancia | BL-052 |
| U10-T08 | Ejecutar revisión humana del dataset | cada caso revisado tiene resultado y observación cuando falla | BL-052 |
| U10-T09 | Red teaming de bypass de aprobación | todos los casos terminan sin ejecución no autorizada | BL-053 |
| U10-T10 | Red teaming de escalada de capacidades | shell arbitrario y recursos no autorizados son rechazados | BL-054 |
| U10-T11 | Red teaming de prompt injection indirecto | los datos maliciosos no cambian la política del agente | BL-055 |
| U10-T12 | Preparar topología ARP normal | el estado inicial produce evidencia de tráfico normal | BL-056 |
| U10-T13 | Ejecutar escenario ARP controlado | el atacante temporal puede incorporarse al laboratorio y el experimento queda registrado | BL-056 |
| U10-T14 | Verificar cambio IP↔MAC observado | cuando el escenario lo produzca, el reporte registra valores anterior y actual | BL-056 |
| U10-T15 | Preparar condición control sin IA | el workflow determinista puede ejecutarse sin el proceso del agente | BL-057 |
| U10-T16 | Preparar condición tratamiento con IA | el mismo objetivo funcional se ejecuta mediante el agente | BL-057 |
| U10-T17 | Registrar tiempos comparables | cada ejecución conserva tiempo total y tiempo humano | BL-057 |
| U10-T18 | Calcular North Star | el análisis calcula el tiempo mediano con y sin IA | BL-058 |
| U10-T19 | Calcular métricas de calidad y seguridad | el análisis produce tool success, recovery, acciones no autorizadas e integridad de evidencia | BL-058 |
| U10-T20 | Calcular noise metric | el análisis identifica eventos que no corresponden al ground truth | BL-058 |

---

---

# 16. U11 — Integración y sustentación

- **Responsabilidad:** convertir las unidades terminadas en un workflow completo y en un paquete reproducible para la sustentación.
- **Qué NO hace:** no introduce capacidades nuevas fuera del alcance del MVP.
- **Depende de:** U3, U8, U9, U10.
- **Historias:** BL-059 a BL-065.
- **Camino crítico:** Sí.
- **Terminada cuando:** existe una ejecución reproducible de extremo a extremo y el paquete final contiene la evidencia funcional, de seguridad y experimental.

| # | Tarea | Criterio de aceptación | Historia |
|---|---|---|---|
| U11-T01 | Integrar workflow completo desde UI | una ejecución recorre UI → agente → tool → Kubernetes → Job → reporte → auditoría | BL-059 |
| U11-T02 | Verificar evidencia del workflow | la ejecución conserva logs, reporte y auditoría correlacionables | BL-059 |
| U11-T03 | Ejecutar workflow completo sin agente | el control termina con evidencia equivalente del objetivo funcional | BL-060 |
| U11-T04 | Preparar escenario de recovery para demo | el fallo controlado produce el flujo de reintentos esperado | BL-061 |
| U11-T05 | Preparar escenario de escalamiento | el fallo persistente muestra el contexto entregado al humano | BL-061 |
| U11-T06 | Preparar demo de seguridad Kubernetes | la sustentación incluye al menos una prueba `can-i` positiva y una negativa | BL-062 |
| U11-T07 | Preparar evidencia de ausencia de shell arbitrario | la prueba negativa y la configuración de tools quedan en el paquete final | BL-062 |
| U11-T08 | Preparar demo ARP | existen evidencias antes/durante/después del escenario | BL-063 |
| U11-T09 | Preparar comparación con/sin IA | el paquete contiene datos de ambas condiciones y el cálculo de la comparación | BL-064 |
| U11-T10 | Consolidar documentación | PRD, arquitectura y backlog están versionados en el repositorio final | BL-065 |
| U11-T11 | Consolidar instrucciones de despliegue | una instalación desde el repositorio reproduce el stack definido | BL-065 |
| U11-T12 | Consolidar checklist de sustentación | el checklist no contiene un requisito sin evidencia asociada | BL-065 |

---

---

## Lo que hace defendible esta descomposición

1. **Responsabilidades separadas:** evidencia determinista, Kubernetes, seguridad, observabilidad, agente, UI, GitOps y evaluación tienen fronteras distintas.
2. **El límite de autonomía es una unidad:** U5 convierte la restricción de “humano confirma / agente no actúa directamente sobre activos” en controles verificables.
3. **Qué NO hace es obligatorio:** evita que U7 absorba detección, evidencia o acceso directo a endpoints.
4. **Pruebas junto a la unidad:** cada historia se aterriza en tareas con evidencia reproducible.

# 22. Organización sugerida del código

```text
sentinel/
├── docs/
│   ├── prd.md
│   ├── arquitectura.md
│   ├── backlog.md
│   └── unidades-y-tareas.md
│
├── src/
│   ├── agent/              # U7
│   ├── tools/              # U7
│   ├── monitoring/         # U2
│   └── ui/                 # U8
│
├── scripts/                # U2
│   ├── discovery.sh
│   ├── monitor.sh
│   ├── traffic.sh
│   ├── baseline.sh
│   ├── compare.sh
│   └── report.sh
│
├── deploy/
│   ├── helm/               # U4
│   ├── jobs/               # U3
│   └── rbac/               # U5
│
├── tests/
│   ├── monitoring/         # U2
│   ├── kubernetes/         # U3
│   ├── security/           # U5
│   ├── observability/      # U6
│   ├── agent/              # U7
│   ├── ui/                 # U8
│   ├── gitops/             # U9
│   └── evaluation/         # U10
│
└── artifacts/
    ├── discovery/
    ├── reports/
    ├── evaluation/
    └── demo/
```

La estructura de código es una propuesta `[INTERNO]`; puede cambiar durante la implementación
sin cambiar las fronteras funcionales de las unidades.

---

## Criterio de salida de Units Generation

El paquete queda preparado para Code Generation cuando cada unidad tiene: (a) frontera explícita, (b) dependencias, (c) historias trazables, (d) criterios verificables y (e) una ruta de implementación que no introduce responsabilidades cruzadas.
