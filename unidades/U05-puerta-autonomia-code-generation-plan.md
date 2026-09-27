# Sentinel — U5 Puerta de autonomía y seguridad Kubernetes — Code Generation Plan

> **AI-DLC · Code Generation, Parte 1**
>
> Unidad seleccionada para la primera demostración de generación de código porque materializa el límite de autonomía del producto en controles comprobables: ServiceAccount, RBAC, NetworkPolicy, Pod Security, allowlist de tools y pruebas negativas.

## 1. Contexto de entrada

U5 implementa la siguiente frontera funcional:

- El agente puede coordinar operaciones autorizadas.
- El agente **no** actúa directamente sobre endpoints.
- El agente no ejecuta shell arbitrario.
- Kubernetes debe aplicar una segunda barrera independiente de la lógica de la aplicación.
- Las operaciones sensibles deben requerir autorización humana en el flujo superior; U5 no aprueba por sí misma.

### Dependencias

```text
U3 Kubernetes y workloads
        ↓
U4 Aplicación cloud-native y Helm
        ↓
U5 Puerta de autonomía y seguridad Kubernetes
        ↓
U6 / U7 consumo seguro de los límites
```

### Historias

- BL-021 — identidad dedicada del agente
- BL-022 — RBAC mínimo
- BL-023 — verificación de permisos positivos y negativos
- BL-024 — Pod Security
- BL-025 — NetworkPolicy
- BL-026 — ausencia de acceso directo a endpoints
- BL-027 — rechazo de shell/capacidades arbitrarias

## 2. Contexto técnico y fronteras

### Entrada

- namespace `sentinel`
- Deployment del agente generado por U3/U4
- contrato de Tool Layer que consumirá U7
- conjunto de operaciones Kubernetes realmente necesarias, cerrado y explícito

### Salida

- ServiceAccount dedicado `sentinel-agent`
- manifiestos RBAC mínimos
- Pod Security aplicado al namespace/pods
- NetworkPolicies para el tráfico permitido
- pruebas positivas/negativas de permisos
- rechazo de ejecución directa sobre endpoints
- rechazo de shell arbitrario
- evidencia reproducible para sustentación

### Qué NO implementar aquí

- El loop de razonamiento del LLM (U7)
- La UI de aprobación humana (U8)
- Discovery/Monitoring/Report como lógica de evidencia (U2)
- Grafana y dashboards (U6)
- GitOps/Argo CD (U9)
- Detección de ataques o anomalías

## 3. Principios materializados

| Principio | Materialización en U5 | Prueba requerida |
|---|---|---|
| Least privilege | permisos explícitos por recurso/verbo | `kubectl auth can-i ...` |
| Defensa en profundidad | Tool Layer rechaza + RBAC rechaza | pruebas negativas en app + clúster |
| No direct endpoint access | no credenciales de endpoint + aislamiento de red | inspección de manifests + prueba de conexión |
| No arbitrary shell | allowlist, sin `exec_shell` genérico | búsqueda + caso negativo |
| Pod hardening | Pod Security | Pod deliberadamente incompatible es rechazado |
| Network isolation | NetworkPolicy | flujo permitido y denegado |
| Evidence-first | toda prueba produce artefacto/log | archivos en `artifacts/demo/` |

## 4. Organización de archivos objetivo

```text
sentinel/
├── deploy/
│   ├── rbac/
│   │   ├── serviceaccount-agent.yaml
│   │   ├── role-agent.yaml
│   │   ├── rolebinding-agent.yaml
│   │   └── ...
│   ├── security/
│   │   ├── pod-security.yaml        # mecanismo exacto [TBD: label/admission manifest]
│   │   └── networkpolicy.yaml
│   └── helm/
│       └── sentinel/
├── src/
│   ├── tools/
│   │   └── allowlist.*               # frontera de herramientas
│   └── agent/
├── tests/
│   ├── security/
│   │   ├── rbac.sh
│   │   ├── networkpolicy.sh
│   │   ├── endpoint-access.sh
│   │   └── arbitrary-shell.sh
│   └── agent/
└── artifacts/
    └── demo/
```

Los nombres exactos de archivos de implementación pueden cambiar; las fronteras funcionales no.

## 5. Interfaces expuestas por U5

### Kubernetes

```text
ServiceAccount: sentinel-agent
Namespace: sentinel
RBAC: solo operaciones explícitamente requeridas
Network: únicamente destinos/puertos autorizados
Pod security: baseline/restricción definida antes de desplegar
```

### Aplicación

U5 expone conceptualmente una política consultable por U7:

```text
isToolAllowed(toolName) -> allow | deny
validateToolParameters(toolName, params) -> valid | deny
isEndpointActionAllowed(action) -> deny
```

La implementación concreta de estas funciones pertenece al Tool Layer de U7; U5 define los artefactos de seguridad Kubernetes y sus pruebas. Cuando el código de U7 esté listo, las pruebas de integración deberán demostrar que ambas capas permanecen independientes.

## 6. Plan de implementación numerado

### Paso 1 — Crear la identidad dedicada del agente

**Tarea:** crear `ServiceAccount/sentinel-agent` en `namespace/sentinel` y asociarlo al Deployment del agente.

**Historia:** BL-021.

**Archivos:**
- `deploy/rbac/serviceaccount-agent.yaml`
- manifest/Helm del Deployment del agente

**Criterio:**

```bash
kubectl get sa sentinel-agent -n sentinel
kubectl get deploy sentinel-agent -n sentinel -o jsonpath='{.spec.template.spec.serviceAccountName}{"\n"}'
```

La segunda salida debe ser exactamente `sentinel-agent`.

### Paso 2 — Definir el RBAC mínimo

**Tarea:** crear únicamente los permisos necesarios para que el agente consulte y dispare las operaciones Kubernetes contempladas por el producto.

**Historia:** BL-022.

**Archivos:**
- `deploy/rbac/role-agent.yaml`
- `deploy/rbac/rolebinding-agent.yaml`

**Procedimiento:**
1. Enumerar operaciones reales requeridas por las tools que existirán en U7.
2. Para cada operación, registrar `apiGroup/resource/verb`.
3. Crear Role/RoleBinding con solo esa lista.
4. No usar wildcard de recursos/verbo como sustituto del diseño.

**Criterio:**

```bash
kubectl auth can-i --list --as=system:serviceaccount:sentinel:sentinel-agent -n sentinel
```

La salida debe contener únicamente las capacidades justificadas por la matriz RBAC del repositorio.

### Paso 3 — Verificar permisos positivos

**Tarea:** probar las operaciones que U7 realmente necesita.

**Historia:** BL-023.

**Criterio:** por cada permiso requerido debe existir una prueba afirmativa:

```bash
kubectl auth can-i <verb> <resource> --as=system:serviceaccount:sentinel:sentinel-agent -n sentinel
```

Cada resultado esperado debe ser `yes`.

### Paso 4 — Negar explícitamente privilegios no requeridos

**Tarea:** comprobar que el agente no puede administrar el clúster ni leer secretos no requeridos.

**Historia:** BL-023.

**Casos mínimos:**

```bash
kubectl auth can-i create deployments \
  --as=system:serviceaccount:sentinel:sentinel-agent -n sentinel

kubectl auth can-i get secrets \
  --as=system:serviceaccount:sentinel:sentinel-agent -n sentinel

kubectl auth can-i create clusterrolebindings \
  --as=system:serviceaccount:sentinel:sentinel-agent
```

**Criterio:** los tres casos deben producir `no`.

### Paso 5 — Aplicar Pod Security

**Tarea:** fijar la política de seguridad de pods elegida para el namespace o workloads.

**Historia:** BL-024.

**Decisión pendiente:** mecanismo exacto (labels de Pod Security Admission u otro mecanismo compatible con el clúster de laboratorio).

**Criterio de implementación:** debe existir un workload deliberadamente incompatible con la política y Kubernetes debe rechazarlo de forma observable.

Ejemplo de evidencia:

```bash
kubectl apply -f tests/security/pod-forbidden.yaml
```

La prueba debe finalizar en rechazo y conservar el mensaje de admisión en `artifacts/demo/pod-security.txt`.

### Paso 6 — Aplicar NetworkPolicy

**Tarea:** definir allow/deny de red dentro de `sentinel` y evitar conectividad no autorizada.

**Historia:** BL-025.

**Archivo:**
- `deploy/security/networkpolicy.yaml`

**Criterios:**

```bash
kubectl get networkpolicy -n sentinel
```

Además, un test de conectividad autorizado debe funcionar y un test hacia un destino no autorizado debe fallar.

### Paso 7 — Eliminar cualquier credencial directa de endpoint

**Tarea:** garantizar que el contexto del agente no recibe secretos que le permitan actuar sobre los activos simulados.

**Historia:** BL-026.

**Comprobaciones:**

```bash
kubectl get deploy sentinel-agent -n sentinel -o yaml > artifacts/demo/agent-deployment.yaml
```

Revisar que no existan variables, mounts o Secrets destinados a acceso directo al endpoint. La configuración de tools debe apuntar únicamente al plano Kubernetes/herramientas autorizadas.

### Paso 8 — Probar intento de acceso directo al endpoint

**Tarea:** ejecutar desde el contexto del agente una operación que represente acceso directo al activo y comprobar que falla por la frontera diseñada.

**Historia:** BL-026.

**Criterio:** el intento termina sin alterar el activo y sin obtener una ruta de ejecución privilegiada. Registrar stdout/stderr y resultado.

### Paso 9 — Prohibir shell arbitrario en la Tool Layer

**Tarea:** asegurar que no exista una herramienta genérica equivalente a `execute_shell(command)`.

**Historia:** BL-027.

**Comprobación estática mínima:**

```bash
grep -R "execute_shell" src/ deploy/ tests/ && exit 1 || exit 0
```

Una implementación más robusta puede buscar patrones equivalentes como `subprocess`, `os.system`, `sh -c` o un `kubectl exec` genérico en rutas expuestas al agente; esos patrones deben revisarse semánticamente para evitar falsos positivos.

### Paso 10 — Prueba negativa de comando libre

**Tarea:** presentar a la interfaz de tools una solicitud de comando arbitrario y comprobar rechazo antes de llegar a Kubernetes.

**Historia:** BL-027.

**Criterio:**

```text
request → Tool Layer → DENY
                     ↘ no Kubernetes call
```

La evidencia debe contener nombre de operación, motivo de rechazo y ausencia de llamada Kubernetes.

### Paso 11 — Integrar pruebas de evidencia y trazabilidad

**Tarea:** guardar resultados de las pruebas U5 bajo `artifacts/demo/` y relacionarlos con BL-021…BL-027.

**Criterio:**

```bash
find artifacts/demo -maxdepth 1 -type f | grep -E 'rbac|network|endpoint|shell|pod-security'
```

Debe existir al menos un artefacto por frontera de seguridad evaluada.

### Paso 12 — Ejecutar regresión de U5

**Tarea:** crear un runner único para las pruebas de la unidad.

**Archivo sugerido:** `tests/security/run_u5.sh`.

**Criterio:**

```bash
./tests/security/run_u5.sh
```

El runner debe fallar ante una regresión de permisos, conectividad, política de pods o rechazo de shell arbitrario.

## 7. Trazabilidad

| Paso | Historia | Archivo(s) principales | Evidencia |
|---:|---|---|---|
| 1 | BL-021 | `deploy/rbac/serviceaccount-agent.yaml`, Deployment | `kubectl get sa`, jsonpath del Deployment |
| 2 | BL-022 | Role/RoleBinding | `kubectl auth can-i --list` |
| 3 | BL-023 | tests RBAC | `auth can-i` positivos |
| 4 | BL-023 | tests RBAC | `auth can-i` negativos |
| 5 | BL-024 | `deploy/security/pod-security.yaml`, test Pod | rechazo de admission |
| 6 | BL-025 | `networkpolicy.yaml`, tests | conectividad allow/deny |
| 7 | BL-026 | Deployment/Secrets | inspección YAML |
| 8 | BL-026 | `endpoint-access.sh` | intento fallido + logs |
| 9 | BL-027 | Tool Layer/tests | búsqueda de shell genérico |
| 10 | BL-027 | Tool Layer/tests | rechazo antes de Kubernetes |
| 11 | BL-021…027 | `artifacts/demo/` | paquete de evidencia |
| 12 | BL-021…027 | `tests/security/run_u5.sh` | regresión automática |

## 8. Definición de terminado de U5

U5 no está terminada por “tener YAML”. Debe cumplirse todo lo siguiente:

```text
[ ] ServiceAccount dedicado existe y está enlazado al agente
[ ] RBAC mínimo está aplicado
[ ] Permisos requeridos producen yes
[ ] create deployments produce no
[ ] get secrets produce no
[ ] create clusterrolebindings produce no
[ ] Pod Security rechaza el caso prohibido
[ ] NetworkPolicy permite el flujo autorizado
[ ] NetworkPolicy bloquea el flujo no autorizado
[ ] No hay credenciales directas a endpoints
[ ] Un intento directo al endpoint falla
[ ] No existe shell arbitrario expuesto al agente
[ ] Un comando libre es rechazado antes de Kubernetes
[ ] Todas las pruebas generan evidencia
```

## 9. No hacer en esta etapa

- No implementar todavía el razonamiento del LLM.
- No diseñar prompts como sustituto del control de seguridad.
- No ampliar el RBAC “para que funcione” si una tool falla; primero identificar la operación mínima realmente necesaria.
- No convertir U5 en un sistema de detección de ataques.
- No agregar nuevas capacidades al MVP solo para llenar el plan.

## 10. Riesgos de implementación de U5

| Riesgo | Señal | Mitigación |
|---|---|---|
| RBAC demasiado amplio | wildcards o permisos administrativos | matriz explícita + pruebas negativas |
| Dependencia de una sola barrera | Tool Layer segura pero RBAC amplio | doble control independiente |
| Falso sentido de aislamiento | NetworkPolicy aplicada pero con excepciones no revisadas | tests allow/deny reproducibles |
| Credenciales invisibles | Secrets montados por herencia/Helm | inspección de Deployment renderizado |
| Shell indirecto | tool que acepta parámetros y termina invocando shell | allowlist estructurada + negative tests |

## 11. Salida hacia U6/U7/U8

Cuando U5 termine, U6 debe poder auditar las operaciones sin modificar la frontera; U7 debe
consumir tools autorizadas sin requerir privilegios adicionales; U8 puede construir el flujo de aprobación sobre una base donde el permiso de infraestructura está probado independientemente.
