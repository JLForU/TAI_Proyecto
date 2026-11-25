# Unit of Work — Sentinel

**Fase**: INCEPTION — Units Generation (Parte 2: Generation)
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Entradas**: `requirements.md` (M1–M10), `stories.md` (ST-M1..M10 + EN-01..07), `application-design.md` (+ componentes), `execution-plan.md`, `implementation-scope.md`, `plans/unit-of-work-plan.md`
**Decisiones aprobadas (Q1–Q8)**: A en todas — 11 unidades; Discovery y Sensor separados; todas las historias en el mapa (`documented-only` donde aplique); monorepo `src/sentinel/`; dependency-first con GUI ∥ Discovery; desarrollador único; Build & Test único al final; documentación/evidencia GT como unidad final.

---

## 1. Panorama

Definición: **unidad de construcción** — agrupación lógica de historias con su propia cadena de artefactos de CONSTRUCTION (functional design → NFR → infra design → código/tests). No implica despliegue independiente; Core es monolito modular y Discovery/Sensor son workloads separados del mismo proyecto/imagen.

| Orden | Unidad | Módulos | Historias | Depende de |
|---|---|---|---|---|
| U1 | Project foundation & CI skeleton | EN-01, EN-02*, EN-05 | 3 | — |
| U2 | Core API, persistence & export | M4 | 7 | U1 |
| U3 | Operator GUI & network report | M10 | 7 | U2 |
| U4 | Configuration, scope & Discovery | M1, M2 | 10 | U2 |
| U5 | Traffic Sensor & ARP observation | M3 | 6 | U1, U2 |
| U6 | Baseline & deterministic conditions | M5 | 4 | U2, U5 |
| U7 | Metrics exposure | M6 | 3 | U2, U6 |
| U8 | Observability & alerting | M7 | 6 | U6, U7 |
| U9 | Kubernetes runtime & Helm | M8 | 4 | U1–U8 |
| U10 | Security & negative tests | M9, EN-04* | 5 | U1–U9 |
| U11 | Documentation & GT evidence | EN-03, EN-06, EN-07* | 3 | U1–U10 |

\* EN-02, EN-04 y EN-07 no figuran en `implementation-scope.md` §2; se asignan aquí para cobertura total (Q3=A) con estado `documented-only`. Total: 58 historias (51 ST + 7 EN). Detalle en `unit-of-work-story-map.md`.

**Alcance** (según `implementation-scope.md`): las unidades se construyen todas para trazabilidad; el corte implementado/documentado se marca historia por historia. Unidades predominantemente documentadas (U5, U6) igualmente ejecutan su cadena de CONSTRUCTION con el alcance reducido indicado abajo.

---

## 2. Definición de las unidades

### U1 — Project foundation & CI skeleton

- **Responsabilidad**: layout del repositorio, imagen OCI común con comandos separados por workload, pipeline CI base (lint/test/build), base Alpine no-root, modelos/config/logging compartidos y contratos (incluye suite de pruebas base para property-based tests).
- **Entradas**: decisiones de `application-design.md`, convenciones de `code-generation.md`.
- **Salidas**: estructura `src/sentinel/` + `tests/`, imagen única `sentinel:*` (entrypoints por módulo), pipeline CI, logger JSON, modelos tipados y contrato de métricas.
- **Qué NO hace**: no sondea redes, no captura paquetes, no persiste datos operativos, no despliega en el clúster.
- **Historias**: EN-01, EN-05 (implementadas); EN-02 (documented-only).
- **Criterio de frontera**: los modelos, validadores y parsers se prueban sin sockets, clúster ni base de datos.
- **Depende de**: ninguna.

### U2 — Core API, persistence & export

- **Responsabilidad**: API REST/JSON interna (`/api/v1`), ingesta y normalización de observaciones, inventario y eventos, SQLite sobre PVC con recuperación, identidad estable de eventos y deduplicación, logs JSON Lines, export CSV/JSON y endpoint `/metrics` en 9108 (junto con U7).
- **Entradas**: contratos de U1; observaciones enviadas por U4 y U5.
- **Salidas**: servicio Core desplegable (Deployment, puerto 8080/9108), repositorio SQLite, endpoints de consulta para U3, `/metrics` para U7.
- **Qué NO hace**: no sondea, no captura, no evalúa condiciones de negocio (U6), no expone GUI (U3), no escribe en activos monitorizados.
- **Historias**: ST-M4-01..07 (implementadas).
- **Criterio de frontera**: la API se prueba con fixtures HTTP; Core es el único escritor de la BD; los colectores no tocan SQLite.
- **Depende de**: U1.

### U3 — Operator GUI & network report

- **Responsabilidad**: vistas Jinja + HTMX para el operador (inventario, detalle de activo, timeline eventos/alertas, salud del sistema, disparo de discovery) y generación de reporte de red Markdown/PDF bajo demanda.
- **Entradas**: API de consulta de U2; estado de salud (lectura de K8s en U9/U10).
- **Salidas**: rutas `/ui/*` embebidas en Core, plantillas, ReportService (C7), reporte MD/PDF base.
- **Qué NO hace**: no accede a la BD directamente; sin autenticación en la demo (acceso solo por `kubectl port-forward`, ST-M10-07); no modifica activos.
- **Historias**: ST-M10-01..07 (implementadas; ST-M10-06 con secciones avanzadas documentadas).
- **Criterio de frontera**: la GUI se prueba contra la API de U2 con datos de fixtures; no importa módulos de descubrimiento/captura.
- **Depende de**: U2.

### U4 — Configuration, scope & Discovery

- **Responsabilidad**: valores Helm de alcance, validación de hosts/puertos autorizados (`explicit_hosts` para la demo), descubrimiento ARP/ICMP/TCP, sondeo ligero Nmap `-sT -sV --version-light` sobre la allowlist, manejo de fallos de ciclo y reconciliación de inventario (first seen / missing).
- **Entradas**: configuración validada (C12), contratos de U1, API de ingesta de U2.
- **Salidas**: worker de descubrimiento (CronJob/Job), lote de observaciones de inventario enviado por HTTP al Core, eventos E-01..E-03.
- **Qué NO hace**: no lee la BD, no evalúa condiciones, no escanea fuera de la allowlist, no ejecuta `-sU/-sC/--script/-A` ni `-O` en el MVP.
- **Historias**: ST-M1-01, ST-M1-02, ST-M2-01..04, ST-M2-06 (implementadas); ST-M1-03, ST-M1-04, ST-M2-05 (documented-only).
- **Criterio de frontera**: el worker produce observaciones de un ciclo probadas con fixtures Nmap/ARP; la reconciliación histórica pertenece a U2 (InventoryService).
- **Depende de**: U2 (y contratos de U1).

### U5 — Traffic Sensor & ARP observation

- **Responsabilidad**: captura de metadatos IP/ARP (diseño SPAN/mirror documentado), agregación en ventanas de 5 s, tasa de mensajes ARP, tracking IP↔MAC, envío de agregados al Core. **Alcance construido**: fuente de paquetes abstracta + **fallback simulado/fixtures** para GT-04/GT-05; la captura real queda documentada.
- **Entradas**: fuente de paquetes (real o simulada), contratos de U1, API de ingesta de U2.
- **Salidas**: agregados de tráfico y observaciones ARP enviados por HTTP al Core; heartbeats de disponibilidad para U6/U8.
- **Qué NO hace**: no persiste en SQLite, no expone `/metrics` propio, no evalúa umbrales, no almacena payload, no modifica paquetes.
- **Historias**: ST-M3-01..06 (documented-only; el simulador/fixtures es código de soporte de la unidad).
- **Criterio de frontera**: las pruebas usan PCAP/fixtures; ningún test requiere visibilidad real de la LAN.
- **Depende de**: U1, U2.

### U6 — Baseline & deterministic conditions

- **Responsabilidad**: línea base estadística (primeras 5 muestras), umbral configurable con fallback absoluto, supresión durante establecimiento e indicadores de condición deterministas (tráfico alto, disponibilidad de sensor). **Alcance construido**: solo lo mínimo para R-01/GT-04 (evaluación de umbral con fixtures); el diseño estadístico completo se documenta.
- **Entradas**: series de U5/observaciones en U2, contratos de U1.
- **Salidas**: indicadores de condición publicados (C5 ConditionService) y estado de alerta consumido por U7/U8.
- **Qué NO hace**: no decide acciones automáticas, no llama a canales externos de alerta, no define labels de alta cardinalidad.
- **Historias**: ST-M5-01..04 (documented-only con mínimo implementado para R-01).
- **Criterio de frontera**: los cálculos se prueban con fixtures parametrizados (bajo/igual/encima del umbral; sin línea base); sin dependencia de red.
- **Depende de**: U2, U5.

### U7 — Metrics exposure

- **Responsabilidad**: proyectar métricas agregadas de Core en `/metrics` (puerto 9108) sin labels de alta cardinalidad, registrar ServiceMonitor y exponer indicadores de condición de U6.
- **Entradas**: datos de U2 (Core, C6 MetricsExporter), indicadores de U6.
- **Salidas**: endpoint `/metrics`, ServiceMonitor, métricas `sentinel_*` agregadas.
- **Qué NO hace**: no evalúa reglas de alerta (U8), no guarda series en Core, no usa IPs/pares como labels.
- **Historias**: ST-M6-01..03 (implementadas).
- **Criterio de frontera**: el endpoint responde con formato Prometheus válido; tests de cardinalidad con fixtures.
- **Depende de**: U2, U6.

### U8 — Observability & alerting

- **Responsabilidad**: reglas PrometheusRule (R-01 tráfico, R-04 sensor caído implementadas; R-02/R-03 ARP documentadas), dashboards Grafana, stack de monitoreo y receiver webhook de Alertmanager (documentado).
- **Entradas**: métricas de U7, indicadores de U6, kube-prometheus-stack.
- **Salidas**: PrometheusRule validadas, dashboards, alertas visibles en Alertmanager/Grafana.
- **Qué NO hace**: no envía correo/SMS (fuera de alcance), no silencia ni enruta acciones sobre los activos.
- **Historias**: ST-M7-01, ST-M7-04, ST-M7-05 (implementadas); ST-M7-02, ST-M7-03, ST-M7-06 (documented-only).
- **Criterio de frontera**: `promtool check rules` pasa; los dashboards se validan con datos de fixtures; nada depende de la red real.
- **Depende de**: U6, U7.

### U9 — Kubernetes runtime & Helm

- **Responsabilidad**: chart de Helm desplegable en kind/k3s con Workloads (Deployment/Core, CronJob/Job/Discovery, Deployment/Sensor), Service, PVC, health checks, ServiceMonitor/Grafana values y verificación del despliegue; incluye la imagen OCI única con comandos separados (ST-M8-04).
- **Entradas**: artefactos de U1–U8.
- **Salidas**: `charts/sentinel/` completo, `helm install` verificado en kind/k3s, workloads corriendo con probes.
- **Qué NO hace**: no implementa políticas de seguridad (U10), no ejecuta la suite GT (U11), no gestiona GitOps.
- **Historias**: ST-M8-01..04 (implementadas).
- **Criterio de frontera**: `helm lint` + despliegue en kind/k3s + `kubectl rollout status` de todos los workloads.
- **Depende de**: U1–U8.

### U10 — Security & negative tests

- **Responsabilidad**: RBAC mínimo (ServiceAccounts separadas, lectura limitada), Pod Security y justificación de capabilities del sensor, prueba de no-escritura en endpoints, NetworkPolicy default-deny documentada (política mínima implementada), escaneo de imagen documentado.
- **Entradas**: manifiestos/charts de U9, superficie de U2–U5.
- **Salidas**: manifiestos RBAC/PodSecurity/NetworkPolicy aplicados, tests negativos (no escritura, no privilegios), informe de escaneo (documentado).
- **Qué NO hace**: no concede `privileged: true` ni `CAP_NET_ADMIN`; no modifica la seguridad de los activos.
- **Historias**: ST-M9-01, ST-M9-03, ST-M9-04 (implementadas); ST-M9-02 (avanzada, documentada), EN-04 (documented-only).
- **Criterio de frontera**: `kubectl auth can-i` limitado, prueba de no-escritura automatizada, PSA de `sentinel-capture` verificado si aplica.
- **Depende de**: U1–U9.

### U11 — Documentation & GT evidence

- **Responsabilidad**: documentación del repositorio (arquitectura, despliegue, operación, troubleshooting), guion y runbook de demo, fixtures de la demo, suite de integración GT-01..GT-05 y evidencia de la sustentación; validación de rendimiento en laboratorio (documentada).
- **Entradas**: código y despliegue de U1–U10.
- **Salidas**: `docs/*.md`, `tests/integration/test_gt_01_05.py`, fixtures, evidencia GT-01..GT-05, informe de desempeño (documentado).
- **Qué NO hace**: no añade funcionalidad nueva; no modifica comportamiento de unidades anteriores (solo corrige docs).
- **Historias**: EN-03, EN-06 (implementadas); EN-07 (documented-only).
- **Criterio de frontera**: los comandos documentados se ejecutan literalmente; la suite GT pasa con fixtures cuando la captura real no está disponible.
- **Depende de**: U1–U10.

---

## 3. Estrategia de organización del código (greenfield — Q4=A)

Monorepo único, un solo paquete Python `sentinel` con submódulos por unidad; artefactos de despliegue y docs en directorios propios. Patrón según `construction/code-generation.md` (monolith multi-unit: `src/{unit}/` → aquí `src/sentinel/{modulo}/`).

```text
<workspace-root>/                     # raíz del repo (sentinel/)
├── src/sentinel/
│   ├── foundation/                   # U1: models, config, logging, contracts
│   ├── core/                         # U2: api/, ingestion/, inventory/, export/, db/
│   ├── gui/                          # U3: views (Jinja/HTMX), report/
│   ├── discovery/                    # U4: scope, arp, probes, nmap
│   ├── traffic/                      # U5: packet source, parser, windows, simulator/
│   ├── baseline/                     # U6: statistics, thresholds, conditions
│   ├── metrics/                      # U7: exporter
│   └── observability/                # U8: (reglas/dashboards viven en deploy/)
├── charts/sentinel/                  # U9: Helm chart
├── deploy/
│   ├── monitoring/                   # U8: PrometheusRules, dashboards
│   └── security/                     # U10: RBAC, PodSecurity, NetworkPolicy
├── tests/
│   ├── unit/{foundation,core,gui,discovery,traffic,baseline,metrics}/
│   ├── property/                     # EN-02 (documented-only)
│   ├── integration/                  # U11: GT-01..05
│   └── perf/                         # EN-07 (documented-only)
├── docs/                             # U11: architecture, deployment, operations, troubleshooting
├── scripts/                          # utilidades de validación
├── .github/workflows/                # U1: CI (lint, test, build)
├── pyproject.toml
└── Dockerfile                        # U1: imagen OCI única
```

**Reglas**:
- **Imagen única, comandos separados** (ST-M8-04): entrypoints `python -m sentinel.core`, `python -m sentinel.discovery`, `python -m sentinel.traffic` desde la misma imagen.
- **Imports por módulo**: `from sentinel.core...`, `from sentinel.foundation...`; los colectores (U4/U5) solo importan `foundation` y hablan con Core por HTTP — nunca importan `core` interno ni tocan `db`.
- **Límite de dependencias**: `gui → core API (HTTP/funciones)`, `baseline → foundation`, `metrics → core + baseline`; sin ciclos.
- **Tests espejo**: `tests/unit/<modulo>/` replica `src/sentinel/<modulo>/`.
- **Nada de código en `aidlc-docs/`**; documentación de producto en `docs/`, documentación del flujo en `aidlc-docs/`.

---

## 4. Criterios de validación de esta descomposición

- [x] 58/58 historias asignadas a exactamente una unidad (ver `unit-of-work-story-map.md`).
- [x] Grafo de dependencias acíclico (ver `unit-of-work-dependency.md`).
- [x] Unidades alineadas con `implementation-scope.md` (corte implementado/documentado por historia).
- [x] Orden dependency-first con paralelismo aprobado U3 ∥ U4 tras U2.
- [x] Build & Test único al final (Q7=A); U11 cierra la documentación/evidencia (Q8=A).
- [ ] Aprobación explícita del usuario.

---

## 5. Approval Gate

**Estado**: GENERATED — pendiente de aprobación. Responder `aprobado` para cerrar Units Generation y pasar a CONSTRUCTION; `cambios` para solicitar modificaciones.
