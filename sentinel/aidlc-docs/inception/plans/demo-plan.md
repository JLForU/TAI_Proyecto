# Demo Plan — Sustentación de Sentinel

**Fecha**: 2026-11-07
**Duración objetivo**: 12–15 minutos
**Estado**: APPROVED — re-aprobado por defecto (2026-11-07T16:25:32Z)
**Documento de alcance**: `aidlc-docs/inception/application-design/implementation-scope.md`

**Mensaje central de la sustentación**: Sentinel resuelve un problema real de visibilidad de activos de red usando herramientas de orquestación (Kubernetes + Helm + Prometheus/Grafana) como complemento, con lógica determinista, sin IA y sin modificar los activos.

---

## 1. Prerrequisitos (verificar antes)

- [ ] Clúster kind/k3s operativo.
- [ ] `helm lint` y `helm template` sin errores.
- [ ] Release de Sentinel desplegado en el namespace `sentinel`.
- [ ] `kube-prometheus-stack` desplegado en `monitoring`.
- [ ] GUI accesible por `kubectl port-forward`.
- [ ] Fixtures de demostración cargados (por si la red real falla).
- [ ] Lista `scope.mode: explicit_hosts` con los 5 activos del laboratorio.

Comandos de verificación:

```bash
kubectl get pods -n sentinel
kubectl get pods -n monitoring
kubectl port-forward -n sentinel svc/sentinel-core 8080:8080
helm list -n sentinel
```

---

## 2. Guion de la demo (orden recomendado)

### Bloque 0 — Contexto (1 min)
- Problema: inventario y monitoreo manual de 10–50 activos.
- Propuesta: plataforma self-hosted sobre Kubernetes; orquestación como complemento.
- Aclaración: producto determinista, sin IA; solo observa, no modifica.

### Bloque 1 — Despliegue con Helm (2 min)
- Mostrar `values.yaml` con `scope.mode: explicit_hosts` y la lista de activos.
- `helm install sentinel ./deploy/helm/sentinel -n sentinel`.
- Mostrar Pods, Services, PVC y CronJob.

**Mensaje**: la orquestación es el centro del proyecto, no un detalle de infraestructura.

### Bloque 2 — Descubrimiento e inventario (3 min)
- Abrir la GUI (`/ui/assets`) y mostrar el inventario.
- Disparar discovery para un host desde la GUI.
- Mostrar el evento de nuevo activo y el estado del ciclo.
- Señalar la distinción observado / inferido / declarado / desconocido.

**Mensaje**: inventario reproducible y con certeza explícita.

### Bloque 3 — Detalle y eventos (2 min)
- Abrir el detalle de un activo: observaciones, eventos, tráfico, ARP.
- Mostrar la línea de tiempo de eventos/alertas con filtros.

### Bloque 4 — Observabilidad y alertas (3 min)
- Abrir Grafana y mostrar dashboards de inventario/tráfico/salud.
- Mostrar `/metrics` del Core.
- Provocar GT-04 (tráfico alto) con ingesta simulada o generador.
- Mostrar R-01 en Alertmanager.

**Mensaje**: condiciones deterministas → Prometheus → Alertmanager; Grafana para visualización.

### Bloque 5 — Reporte de red (2 min)
- Generar el reporte MD/PDF desde la GUI para el rango de la demo.
- Mostrar resumen: inventario, cambios, top talkers, alertas y rango de evidencia.
- Descargar CSV/JSON.

**Mensaje**: evidencia ordenada y reproducible para el operador.

### Bloque 6 — Seguridad (1 min)
- Mostrar RBAC de solo lectura y contenedores no-root.
- Mostrar la prueba de no-escritura sobre activos.
- Recordar: GUI no expuesta públicamente.

### Bloque 7 — Cierre (1 min)
- Qué se implementó, qué quedó documentado y trabajo futuro.
- Enfatizar límites: no detección de ataques, no respuesta automática, no payload.

---

## 3. Fallback si falla la red real

| Falla | Fallback |
|---|---|
| No hay visibilidad SPAN/mirror | Cargar fixtures de tráfico y ejecutar GT-04/GT-05 simulados; declararlo |
| Host del laboratorio no responde | Usar lista de fixtures con IPs/MACs de ejemplo |
| Prometheus no scrapea | Mostrar `/metrics` directo y explicar el ServiceMonitor |
| Grafana no carga dashboard | Mostrar el JSON del dashboard y las consultas PromQL |
| PDF no genera | Descargar Markdown y explicar el pipeline de reporte |

**Regla**: nunca improvisar datos en vivo; usar fixtures y declarar que son simulados.

---

## 4. Preguntas probables del jurado

| Pregunta | Respuesta breve |
|---|---|
| ¿Dónde está la IA? | El producto no usa IA; AI-DLC se usó para el proceso de desarrollo. |
| ¿Esto detecta ataques? | No; registra condiciones objetivas. No atribuye intención ni responde. |
| ¿Por qué Kubernetes? | Orquestación, Helm, observabilidad y reproducibilidad; es el centro del proyecto. |
| ¿Qué pasa si el sensor no ve la LAN? | Se documenta la limitación y la demo usa fallback; el diseño SPAN/mirror está especificado. |
| ¿Por qué SQLite? | Prototipo de laboratorio con un solo escritor; no se plantea HA. |
| ¿Cómo garantizan no modificar activos? | RBAC de solo lectura, pruebas negativas y ausencia de escrituras remotas. |

---

## 5. Checklist final (5 minutos antes)

- [ ] Clúster y releases arriba.
- [ ] Port-forward activo.
- [ ] Fixtures cargados.
- [ ] Pestañas abiertas: GUI, Grafana, Alertmanager.
- [ ] Reporte de ejemplo pre-generado (por si falla en vivo).
- [ ] Guion y preguntas revisados.
