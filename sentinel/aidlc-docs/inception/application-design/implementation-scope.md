# Implementation Scope — Sentinel

**Fase**: INCEPTION — Application Design (preparación)
**Fecha**: 2026-11-07
**Estado**: APPROVED — re-aprobado por defecto (2026-11-07T16:25:32Z)
**Propósito**: separar el **alcance completo del producto** (documentado) del **alcance que se construye para la sustentación**. Este documento no recorta los requisitos: registra qué se implementa, qué se diseña/documenta y qué queda fuera de plazo.

**Fuentes**: `entradas/prd.md`, `aidlc-docs/inception/requirements/requirements.md`, `aidlc-docs/inception/user-stories/stories.md`, `aidlc-docs/inception/plans/execution-plan.md`.

---

## 1. Criterio de clasificación

| Nivel | Significado | Evidencia en la sustentación |
|---|---|---|
| **Implementado** | Se construye, se prueba y se demuestra en vivo | Código + tests + demo |
| **Documentado** | Se diseña y se documenta; no se codifica en el plazo | Diseño + documento; se declara explícitamente |
| **Fuera de alcance** | Trabajo futuro; no se promete en esta entrega | Mención en "trabajo futuro" |

---

## 2. Implementado (demo)

| Unidad / módulo | Alcance implementado | Historias |
|---|---|---|
| Foundation & CI | Layout del repo, imagen OCI común, pipeline base (lint/test/build); PBT designado en áreas construidas (Nmap XML, normalización de flujos, baseline) | EN-01, EN-05, EN-02 (parcial) |
| Core API & persistence | Ingesta, consulta, inventario, SQLite/PVC, export CSV/JSON, `/metrics` | ST-M4-01..07, ST-M6-01..02 |
| Operator GUI (M10) | Inventario, detalle de activo, eventos/alertas, salud, disparo de discovery, reporte MD/PDF; acceso solo por `kubectl port-forward` (sin auth en la demo) | ST-M10-01..07 |
| Configuration & scope | Helm values, `scope.mode: explicit_hosts` para la lista del laboratorio, validación de alcance | ST-M1-01, ST-M1-02, ST-M2-01, ST-M2-02, ST-M2-03, ST-M2-04, ST-M2-06 |
| Discovery | ARP/ICMP/TCP + Nmap `-sV --version-light` sobre hosts explícitos; reconciliación de inventario | ST-M2-01..04, ST-M2-06 |
| Metrics & alerting mínimo | `/metrics`, ServiceMonitor, reglas R-01 y R-04 demostrables; Grafana | ST-M6-01..03, ST-M7-01, ST-M7-04, ST-M7-05 |
| Kubernetes runtime & Helm | Chart desplegable en kind/k3s, Service, PVC, CronJob/Job | ST-M8-01..03 |
| Security mínimo | RBAC, no-root, Pod Security, prueba de no-escritura | ST-M9-01, ST-M9-03, ST-M9-04 |
| Docs & ground truth | Runbook, guion de demo, fixtures, GT-01/02/04/05 | EN-03, EN-06 |

---

## 3. Documentado (no codificado en el plazo)

| Módulo | Qué se documenta | Historias |
|---|---|---|
| Traffic Sensor real (M3) | Diseño de captura SPAN/mirror, agregación y contrato con Core; la demo usa **fallback simulado/fixtures** | ST-M3-01..06 |
| Baseline completo (M5) | Diseño estadístico y supresión; se implementa solo lo necesario para R-01 | ST-M5-01..04 |
| SNMP read-only | Módulo opcional documentado en Helm values, no habilitado | ST-M1-04 |
| NetworkPolicy avanzada | Reglas documentadas; se implementa la política mínima | ST-M9-02 |
| Reporte PDF avanzado | Se implementa el reporte base; secciones adicionales quedan como mejora | ST-M10-06 |
| GitOps / Argo CD | Flujo documentado, no desplegado | PRD §8 Should |

---

## 4. Fuera de alcance (trabajo futuro)

- Multi-sensor / multi-subred (ST-M1-03).
- Integración de logs en Loki.
- Panel de topología.
- Alta disponibilidad del Core; SQLite se mantiene como persistencia de laboratorio.
- Canal externo de notificaciones (correo/SMS); solo webhook opcional.
- Detección de tecnología vecina (LLDP/CDP).
- Cualquier función de IA/LLM/agente (scope lock).
- Autenticación/autorización de operador en la GUI (trabajo futuro; la demo usa solo `port-forward`).

---

## 5. Casos ground truth para la sustentación

| Caso | Cómo se demuestra | Dependencia |
|---|---|---|
| GT-01 Normal operation | Inventario + ciclo de discovery + GUI de salud | Fixtures o red del laboratorio |
| GT-02 New host appears | Añadir host a `explicit_hosts` y disparar discovery desde la GUI | Lista de hosts |
| GT-03 Host absent | Retirar host de la lista y verificar estado `absent` | Fixtures |
| GT-04 High traffic | Ingesta simulada o sensor real; alerta R-01 | Fallback simulado |
| GT-05 Sensor down | Detener heartbeat simulado; alerta R-04 y vista de salud | Fixtures |

**Regla**: si la captura real no está disponible el día de la sustentación, GT-04 y GT-05 se demuestran con el fallback simulado y se declara que la captura real quedó documentada, no demostrada.

---

## 6. Trazabilidad de la decisión

- Decisión del usuario (GUI como módulo del producto): `audit.md` 2026-11-07T16:25:32Z.
- Revisión de alcance EN-02 (PBT implementado parcial en áreas construidas, decisión Q8=A del plan de Functional Design U1): `audit.md` 2026-11-11 (re-aprobada implícitamente con la respuesta Q8=A; NFR-TECH-03 exige PBT para Nmap XML/flow/baseline).
- Requisitos: `requirements.md` §2.9, FR-DISC-06, NFR-TECH-04 / NFR-OPS-04 / NFR-OPS-05.
- Historias: `stories.md` M10 (ST-M10-01..07) y matrices de trazabilidad actualizadas.
- Plan: `execution-plan.md` §5 (Implementation Scope) y unidad 3 del §4.

---

## 7. Approval Gate

**Estado**: APPROVED — re-aprobado por defecto (2026-11-07T16:25:32Z), según instrucción del usuario. Cualquier cambio posterior se registra en `audit.md` y requiere re-aprobación.
