# Personas — Sentinel

**Fase**: INCEPTION — User Stories
**Fecha**: 2026-11-07
**Entrada**: `entradas/prd.md` (v3.0) §4, §7; `entradas/pvb.md` §2, §5; `aidlc-docs/inception/requirements/requirements.md`
**Scope Lock**: El producto es determinista. Ninguna persona interactúa con agente, LLM, orquestación IA ni confirmación humana de operaciones.

---

## Convenciones

- **ID de persona**: identificador estable en inglés (`PER-OPR`, `PER-ADM`, `PER-SEC`).
- **Cuerpo**: español, con términos técnicos y nombres de comando en inglés.
- Cada persona traza a las secciones del PRD v3.0 y del PVB indicadas.

---

## PER-OPR — Network Operator

**Descripción**: Analista o administrador de red de un equipo pequeño de TI/redes/ciberseguridad. Opera una red local de 10–50 activos y necesita saber qué dispositivos están presentes, qué cambió y si las condiciones de tráfico o ARP superaron los umbrales definidos.

**Objetivos**
- Ver el inventario actual de activos y los cambios observados (primera aparición, ausencia, cambio de puertos/servicios).
- Consultar telemetría de tráfico y actividad ARP por ventana temporal.
- Recibir y revisar alertas explícitas (`TrafficThresholdExceeded`, `ArpRateThresholdExceeded`, `ArpMappingChanged`, `SensorUnavailable`) sin atribución de intención ni diagnóstico de ataque.
- Exportar evidencia estructurada (JSON Lines / CSV) para revisión fuera de Sentinel.

**Puntos de contacto**
- Grafana: inventario, baseline de tráfico, timeline de alertas, salud del sensor.
- Alertmanager: notificaciones agrupadas.
- Core API: exportación CSV/JSON bajo demanda.

**Necesidades de confianza**
- Ver la regla, el umbral, el valor medido, la hora y el sensor que originaron cada evento/alerta.
- Distinguir observación, inferencia y dato desconocido.
- Confirmar que Sentinel no modificó los endpoints.

**Dolores**
- Recolección dispersa entre scripts y herramientas sin vista temporal unificada.
- Alertas ruidosas o ambiguas que no indican qué se midió.
- Ausencia de evidencia reproducible para justificar una revisión.

**Trazabilidad**: PRD §3.1–§3.5, §5 (UC-01..UC-05), §7.1; PVB §1, §5, §8.

---

## PER-ADM — Platform Administrator

**Descripción**: Responsable de infraestructura/Kubernetes que despliega y opera Sentinel en un clúster self-hosted (kind, k3s o vanilla Kubernetes 1.28+). Valida que la configuración declarativa sea reproducible y que el sensor solo observe el segmento autorizado.

**Objetivos**
- Desplegar Sentinel con un Helm chart y valores declarativos (rangos, puertos, ventanas, umbrales, capabilities).
- Verificar Pods, Jobs, PVC, ServiceMonitor, reglas y servicios.
- Revisar RBAC, ServiceAccounts y capabilities del sensor.
- Recuperar estado tras reinicios del Core desde el PVC SQLite.
- Ejecutar el pipeline de CI (lint, tests, build, escaneo de imagen, helm test, despliegue a kind/k3s).

**Puntos de contacto**
- `helm`, `kubectl`, `values.yaml`.
- Clúster Kubernetes, PVC, ServiceMonitor, NetworkPolicy.
- Pipeline de CI y logs de despliegue.

**Necesidades de confianza**
- Plantillas reproducibles y validadas (`helm lint`, `helm template`).
- Privilegios mínimos y justificados; sensor aislado.
- Procedimientos documentados de despliegue, operación y troubleshooting.

**Dolores**
- Configuraciones manuales no reproducibles.
- Permisos excesivos que bloquean la aprobación de seguridad.
- Falta de visibilidad del estado de las cargas de trabajo.

**Trazabilidad**: PRD §2.3, §7.2, §8, §9 (M1, M7, M8); PVB §2, §9.

---

## PER-SEC — Security Reviewer

**Descripción**: Responsable de infraestructura, redes o ciberseguridad con poder de veto sobre el despliegue. Verifica que Sentinel observe de forma acotada, no escriba en los endpoints y produzca evidencia auditable determinista.

**Objetivos**
- Verificar RBAC de mínimo privilegio y cuentas de servicio separadas.
- Verificar NetworkPolicy default-deny y allowlists explícitas.
- Revisar Pod Security Standards y capabilities del sensor (`CAP_NET_RAW`, `CAP_NET_ADMIN`, `CAP_SYS_ADMIN`).
- Confirmar ausencia de escrituras o cambios remotos sobre los activos (prueba negativa).
- Auditar que eventos y alertas provienen de reglas versionadas y mediciones reproducibles.

**Puntos de contacto**
- Manifiestos RBAC y NetworkPolicy.
- Revisión de capabilities y Pod Security.
- Evidencia de pruebas negativas y de escaneo de vulnerabilidades de imagen.
- Logs estructurados y exportaciones.

**Necesidades de confianza**
- Trazabilidad completa: regla, fuente, hora, umbral, valor y estado del sensor.
- Separación clara entre observación, inferencia, evento y alerta.
- Sin payload completo almacenado en el MVP.

**Dolores**
- Herramientas que solicitan privilegios generales o realizan acciones de respuesta.
- Alertas que afirman ataques confirmados sin evidencia.
- Ausencia de pruebas que demuestren no modificación de endpoints.

**Trazabilidad**: PRD §3.5, §6, §8 (Won't Have), §9 (M9), §11; PVB §2, §3, §9.

---

## Mapa Persona → Grupos de Historias

| Persona | Historias primarias |
|---|---|
| PER-OPR | M1 (consulta de alcance configurado), M2 (inventario y cambios), M3 (tráfico y ARP), M4/M5 (condiciones y baselines), M6/M7 (métricas, dashboards, alertas), M4 Export |
| PER-ADM | M1 (configuración Helm), M8 (runtime Kubernetes), M7 (observabilidad desplegable), Enablers (CI, documentación) |
| PER-SEC | M9 (RBAC, NetworkPolicy, Pod Security, prueba de no escritura), Enablers (escaneo de imagen, PBT) |
