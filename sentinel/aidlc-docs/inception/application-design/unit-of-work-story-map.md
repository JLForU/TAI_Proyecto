# Unit of Work — Story Map — Sentinel

**Fase**: INCEPTION — Units Generation (Parte 2: Generation)
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Entradas**: `stories.md` (58 historias: ST-M1..M10 = 51, EN-01..07 = 7), `implementation-scope.md`, `unit-of-work.md` (Q3=A: cobertura total con marca `documented-only`).

---

## 1. Reglas de titularidad

- Cada historia pertenece a **exactamente una** unidad (sin hogares dobles).
- `implemented` = se construye, se prueba y se demuestra (alcance `implementation-scope.md` §2).
- `documented-only` = se diseña/documenta en la unidad; no se codifica en el plazo (§3, §4, o sin listar en el alcance implementado — nota al margen).
- La titularidad sigue los módulos de la propuesta aprobada (plan Q1=A), con tres asignaciones explícitas fuera del patrón módulo→unidad: EN-02 → U1, EN-04 → U10, EN-07 → U11 (cobertura completa; ninguna historia sin unidad).

---

## 2. Cobertura por unidad

| Unidad | Historias | implemented | documented-only |
|---|---|---|---|
| U1 — Project foundation & CI skeleton | EN-01, EN-02, EN-05 | 2 | 1 |
| U2 — Core API, persistence & export | ST-M4-01..07 | 7 | 0 |
| U3 — Operator GUI & network report | ST-M10-01..07 | 7 | 0 |
| U4 — Configuration, scope & Discovery | ST-M1-01..04, ST-M2-01..06 | 7 | 3 |
| U5 — Traffic Sensor & ARP observation | ST-M3-01..06 | 0 | 6 |
| U6 — Baseline & deterministic conditions | ST-M5-01..04 | 0 | 4 |
| U7 — Metrics exposure | ST-M6-01..03 | 3 | 0 |
| U8 — Observability & alerting | ST-M7-01..06 | 3 | 3 |
| U9 — Kubernetes runtime & Helm | ST-M8-01..04 | 4 | 0 |
| U10 — Security & negative tests | ST-M9-01..04, EN-04 | 3 | 2 |
| U11 — Documentation & GT evidence | EN-03, EN-06, EN-07 | 2 | 1 |
| **Total** | **58** | **38** | **20** |

---

## 3. Mapa completo historia → unidad

### U1 — Project foundation & CI skeleton

| Historia | Título | Estado | Nota |
|---|---|---|---|
| EN-01 | CI pipeline with lint, tests, build and deploy | implemented | Alcance reducido a etapas lint/test/build (`implementation-scope.md` §2 Foundation) |
| EN-02 | Property-based tests for parsing, normalization and baseline | documented-only | No listada en §2; infraestructura de tests base queda prevista en U1 |
| EN-05 | Hardened Alpine base and non-root containers | implemented | Base Alpine, no-root (excepción del Sensor justificada en U10) |

### U2 — Core API, persistence & export

| Historia | Título | Estado | Nota |
|---|---|---|---|
| ST-M4-01 | Ingestion API for sensor observations | implemented | Endpoint de U4/U5 (IP2) |
| ST-M4-02 | SQLite persistence on PVC with restart recovery | implemented | Único escritor: Core |
| ST-M4-03 | Stable event identity and deduplication | implemented | |
| ST-M4-04 | Normalize and correlate observations | implemented | |
| ST-M4-05 | Structured JSON Lines event logs | implemented | |
| ST-M4-06 | On-demand CSV bulk export | implemented | |
| ST-M4-07 | Query API for assets, events and alerts | implemented | Alimenta a U3 |

### U3 — Operator GUI & network report

| Historia | Título | Estado | Nota |
|---|---|---|---|
| ST-M10-01 | Asset inventory view | implemented | |
| ST-M10-02 | Asset detail view | implemented | |
| ST-M10-03 | Events and alerts timeline | implemented | |
| ST-M10-04 | Trigger discovery for one host or the configured list | implemented | Dispara a U4 vía API |
| ST-M10-05 | System health view | implemented | |
| ST-M10-06 | Network report and export | implemented | Reporte base MD/PDF; secciones avanzadas documentadas (`implementation-scope.md` §3) |
| ST-M10-07 | Non-public GUI access (auth out of scope for demo) | implemented | Acceso solo por `kubectl port-forward` |

### U4 — Configuration, scope & Discovery

| Historia | Título | Estado | Nota |
|---|---|---|---|
| ST-M1-01 | Helm-configurable scope and scheduling | implemented | |
| ST-M1-02 | Authorized scope validation before scanning | implemented | |
| ST-M1-03 | Reserved sensor_id for future multi-sensor | documented-only | Fuera de alcance (`implementation-scope.md` §4) |
| ST-M1-04 | Optional read-only SNMP discovery module | documented-only | §3; documentado en Helm values, no habilitado |
| ST-M2-01 | Periodic ARP/ICMP/TCP discovery | implemented | |
| ST-M2-02 | Light service and version probing | implemented | Nmap `-sT -sV --version-light` sobre allowlist |
| ST-M2-03 | Asset first seen event | implemented | |
| ST-M2-04 | Asset missing after N successful cycles | implemented | |
| ST-M2-05 | Port or service change event | documented-only | Sin listar en §2; clasificada documented-only (E-03) |
| ST-M2-06 | Discovery cycle failure handling | implemented | |

### U5 — Traffic Sensor & ARP observation

| Historia | Título | Estado | Nota |
|---|---|---|---|
| ST-M3-01 | Minimal traffic metadata capture on SPAN | documented-only | Captura real documentada; demo usa fallback simulado |
| ST-M3-02 | Configurable aggregation windows | documented-only | Diseño de ventanas documentado; simulador genera ventanas de 5 s |
| ST-M3-03 | Export aggregated flows to Core | documented-only | Contrato HTTP documentado; el simulador lo ejercita |
| ST-M3-04 | ARP observation and IP-MAC tracking | documented-only | |
| ST-M3-05 | ARP rate per interface | documented-only | |
| ST-M3-06 | ARP mapping changed alert | documented-only | Evento E-04 documentado; regla R-03 también documented-only (U8) |

### U6 — Baseline & deterministic conditions

| Historia | Título | Estado | Nota |
|---|---|---|---|
| ST-M5-01 | Baseline from first five samples | documented-only | Diseño estadístico documentado; traza a GT-01 (mínimo implementado ver nota ST-M5-02) |
| ST-M5-02 | Configurable threshold with absolute fallback | documented-only | **Mínimo implementado para R-01/GT-04**: evaluación de umbral con fixtures dentro de U6 (`implementation-scope.md` §3: "se implementa solo lo necesario para R-01") |
| ST-M5-03 | Suppress alerts during baseline establishment | documented-only | |
| ST-M5-04 | Publish deterministic condition indicators | documented-only | Indicador consumido por U7/U8 en la parte mínima de R-01 |

### U7 — Metrics exposure

| Historia | Título | Estado | Nota |
|---|---|---|---|
| ST-M6-01 | Prometheus-compatible /metrics on port 9108 | implemented | Endpoint alojado en Core (C6); titularidad por módulo M6 → U7 |
| ST-M6-02 | Aggregated metrics without high-cardinality labels | implemented | |
| ST-M6-03 | ServiceMonitor for metrics scraping | implemented | |

### U8 — Observability & alerting

| Historia | Título | Estado | Nota |
|---|---|---|---|
| ST-M7-01 | Traffic threshold PrometheusRule | implemented | R-01 demostrable (GT-04) |
| ST-M7-02 | ARP rate PrometheusRule | documented-only | R-02 fuera del alerting mínimo (§2) |
| ST-M7-03 | ArpMappingChanged rule | documented-only | R-03 fuera del alerting mínimo (§2) |
| ST-M7-04 | SensorUnavailable alert | implemented | R-04 demostrable (GT-05) |
| ST-M7-05 | Grafana dashboards and observability stack | implemented | |
| ST-M7-06 | Alertmanager webhook receiver | documented-only | Canal externo §4 (webhook opcional futuro) |

### U9 — Kubernetes runtime & Helm

| Historia | Título | Estado | Nota |
|---|---|---|---|
| ST-M8-01 | Deploy Sentinel via Helm chart | implemented | |
| ST-M8-02 | Declarative workloads, services and PVC | implemented | |
| ST-M8-03 | Deploy and verify on kind/k3s | implemented | |
| ST-M8-04 | Single OCI image with separate commands | implemented | Imagen única construida desde U1 (EN-05); entrypoints `python -m sentinel.{core,discovery,traffic}`; verificada en U9 |

### U10 — Security & negative tests

| Historia | Título | Estado | Nota |
|---|---|---|---|
| ST-M9-01 | Least-privilege RBAC | implemented | |
| ST-M9-02 | Default-deny NetworkPolicy with allow rules | documented-only | §3: política mínima implementada, reglas avanzadas documentadas |
| ST-M9-03 | Pod Security and justified sensor capabilities | implemented | Sin `CAP_NET_ADMIN`, sin `privileged`; cadena de controles según `DECISIONES_PENDIENTES.md` §5 |
| ST-M9-04 | Proof of no writes on endpoints | implemented | |
| EN-04 | Container image vulnerability scan | documented-only | No listada en §2 (pipeline base = lint/test/build) |

### U11 — Documentation & GT evidence

| Historia | Título | Estado | Nota |
|---|---|---|---|
| EN-03 | Repository documentation | implemented | `docs/architecture.md`, `deployment.md`, `operations.md`, `troubleshooting.md` |
| EN-06 | Ground-truth integration suite GT-01..GT-05 | implemented | Fixtures cuando no hay captura real (regla de demo, §5) |
| EN-07 | Lab performance validation (non-binding) | documented-only | Objetivos no vinculantes; no listada en §2 |

---

## 4. Verificación de completitud

| Chequeo | Resultado |
|---|---|
| Historias totales en `stories.md` | 58 (51 ST + 7 EN) |
| Historias con unidad asignada | 58 |
| Historias en más de una unidad | 0 |
| Historias sin unidad | 0 |
| implemented + documented-only | 38 + 20 = 58 |
| Historias de §2 del alcance marcadas `implemented` | sí (37 del listado + ST-M8-04 verificado por §2 Foundation) |
| Historias de §3/§4 marcadas `documented-only` | sí |
| Historias sin listar en el alcance | ST-M2-05, ST-M7-02, ST-M7-03, ST-M7-06, EN-02, EN-04, EN-07 → `documented-only` con nota |

---

## 5. Approval Gate

**Estado**: GENERATED — pendiente de aprobación. Ver `unit-of-work.md` (§5) para el gate conjunto de Units Generation.
