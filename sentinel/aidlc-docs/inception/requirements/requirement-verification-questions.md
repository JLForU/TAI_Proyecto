# Requirements Verification Questions — Sentinel

**Project**: Sentinel — Self-hosted network asset monitoring platform on Kubernetes
**Source Documents**: `entradas/prd.md` (v3.0), `entradas/pvb.md`
**Date**: 2026-11-07

---

## Intent Analysis Summary

- **User Request**: Build Sentinel per PRD v3.0 and PVB specifications
- **Request Type**: New Project (Greenfield)
- **Scope Estimate**: System-wide (multiple components: discovery, traffic sensor, core, observability stack)
- **Complexity Estimate**: Complex (Kubernetes-native, multiple workloads, security constraints, observability integration)

---

## Clarifying Questions

### Question 1: Discovery Scope and Methods
The PRD specifies ARP/ICMP/TCP discovery with Nmap `-sV --version-light` for service detection. No `-O` OS detection, no NSE scripts, no UDP, no aggressive mode.

**A)** Use exactly the methods specified in PRD (ARP/ICMP/TCP + Nmap `-sV --version-light` only)

**B)** Add passive OS fingerprinting from traffic captures (no active `-O` probes)

**C)** Add SNMP read-only discovery as Should Have (PRD §8 Should Have)

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A

---

### Question 2: Discovery Frequency and Scheduling
PRD §3.3 states "intervalo inicial `TBD`" for periodic discovery.

**A)** Default to every 15 minutes (configurable via Helm values)

**B)** Default to every 5 minutes with exponential backoff on failures

**C)** Event-driven only (triggered manually or via webhook, no CronJob)

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — 15 min por defecto, configurable vía Helm values

---

### Question 3: Traffic Capture Source
PRD §3.2 and §9 M3 require "fuente de visibilidad validada" for traffic metadata capture.

**A)** Linux `AF_PACKET` / `TPACKET_V3` on a mirror/SPAN port (requires `CAP_NET_RAW`, `CAP_NET_ADMIN`)

**B)** eBPF/XDP attached to host interface (requires modern kernel, `CAP_BPF`, `CAP_PERFMON`)

**C)** NetFlow/IPFIX ingest from a network device (no packet capture on sensor)

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — AF_PACKET/TPACKET_V3 sobre bridge/SPAN. Requiere hostNetwork en el Pod del sensor

---

### Question 4: Traffic Aggregation Window
PRD §3.3 hypothesizes 5-second aggregation windows.

**A)** Fixed 5-second windows (as PRD hypothesis)

**B)** Configurable: 1s, 5s, 10s, 30s, 60s via Helm values

**C)** Adaptive: start at 5s, adjust based on flow cardinality

**X)** Other (please describe after [Answer]: tag below)

[Answer]: B — configurable 1s/5s/10s/30s/60s, default 5s

---

### Question 5: Baseline Calculation and Alert Thresholds
PRD §3.3: baseline = 5 samples at 5s intervals (25s init window), mean μ and sample variance s². Thresholds `TBD` — options: absolute, `μ + k·s`, or combination.

**A)** Implement baseline engine in Core (U6) with configurable `k` for `μ + k·s`; absolute threshold as fallback

**B)** Only absolute thresholds (simpler, no baseline wait period)

**C)** Baseline + absolute; alert only after baseline established (no alerts during first 25s)

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — baseline engine con k configurable y umbral absoluto como fallback; no alertar durante los primeros 25s

---

### Question 6: ARP Monitoring Scope
PRD §3.2 models ARP separately (layer 2). E-04 `ArpMappingChanged` generates alert. R-02 `ArpRateThresholdExceeded` and R-03 `ArpMappingChanged` are alert rules.

**A)** Full ARP capture: all ARP op codes, track IP↔MAC mappings, rate per interface

**B)** ARP reply only (op=2): track mappings, detect changes, rate limiting

**C)** ARP request + reply: full visibility but higher volume

**X)** Other (please describe after [Answer]: tag below)

[Answer]: C — ARP request + reply (opcodes 1 y 2)

---

### Question 7: Persistence Layer
PRD §9 M4: "SQLite/PVC + eventos y exportaciones CSV/JSON". U5 assigns stable identity to persisted events.

**A)** SQLite on PVC (single-node, simple, matches PRD)

**B)** PostgreSQL on PVC (better concurrency, future-proof for multi-sensor)

**C)** Embedded key-value (e.g., BoltDB/badger) — lighter than SQLite

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — SQLite en PVC

---

### Question 8: Core API and Ingestion
PRD §9 M4: "API de ingesta/consulta, normalización, comparación, historial y persistencia". M6: Service ClusterIP `sentinel-core`, puerto `metrics:9108`, ServiceMonitor.

**A)** gRPC + HTTP/JSON for ingestion; HTTP/JSON for query/export; `/metrics` for Prometheus

**B)** HTTP/JSON only for all APIs (simpler, no protobuf)

**C)** NATS/Kafka for ingestion (decouple sensor from core); HTTP for query

**X)** Other (please describe after [Answer]: tag below)

[Answer]: B — HTTP/JSON only, /metrics para Prometheus

---

### Question 9: Multi-Sensor / Multi-Subnet Support (Could Have)
PRD §8 Could Have: "Más de un sensor o subred".

**A)** MVP supports single sensor/subnet only; multi-sensor deferred

**B)** Design for multi-sensor from start: sensor_id in all observations, Core handles multiple

**C)** Single sensor MVP but with sensor_id field reserved for future

**X)** Other (please describe after [Answer]: tag below)

[Answer]: C — single sensor MVP con sensor_id reservado

---

### Question 10: SNMP Read-Only (Should Have)
PRD §8 Should Have: "SNMP de solo lectura para uno o más dispositivos de red".

**A)** Include in MVP: SNMP v2c/v3 read-only, configurable OIDs, parallel with Nmap discovery

**B)** Defer to post-MVP: focus on ARP/ICMP/TCP/Nmap first

**C)** SNMP as separate discovery module, optional via Helm values

**X)** Other (please describe after [Answer]: tag below)

[Answer]: C — SNMP como módulo opcional vía Helm, no obligatorio en MVP

---

### Question 11: Observability Stack Deployment
PRD §9 M7: "Prometheus + Grafana + Alertmanager mediante Helm". PRD §13: CKAD/Helm chart for Sentinel.

**A)** Sentinel Helm chart includes subcharts for Prometheus/Grafana/Alertmanager (all-in-one)

**B)** Sentinel Helm chart only; observability stack deployed separately (kube-prometheus-stack)

**C)** Sentinel Helm chart with optional dependency on kube-prometheus-stack

**X)** Other (please describe after [Answer]: tag below)

[Answer]: B — Sentinel chart separado, kube-prometheus-stack aparte

---

### Question 12: Alertmanager Notification Channels
PRD §8 Should Have: "Alertmanager con un canal de notificación externo".

**A)** Email + Webhook (generic) as default; Slack/PagerDuty as optional config

**B)** Webhook only (operator implements receiver)

**C)** No default channel; documentation only

**X)** Other (please describe after [Answer]: tag below)

[Answer]: B — webhook only; documentar webhook.site para demos

---

### Question 13: Network Policies and Pod Security
PRD §8 Should Have: "NetworkPolicies para aislar la comunicación interna de Sentinel". PRD §9 M9: RBAC, Pod Security, capabilities.

**A)** Default-deny NetworkPolicy; allow only Core↔Sensor, Core↔Prometheus, Grafana↔Prometheus

**B)** Namespace-level isolation only; no pod-to-pod policies (CNI may not support)

**C)** NetworkPolicy as optional/should-have; document required rules

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — default-deny NetworkPolicy; documentar requisito de CNI compatible (Calico/Cilium/k3s)

---

### Question 14: Sensor Capabilities and Privileges
PRD §9 M3/M9: "capabilities específicas", "sensor aislado, capabilities mínimas". Traffic capture requires elevated privileges.

**A)** `CAP_NET_RAW`, `CAP_NET_ADMIN`, `CAP_SYS_ADMIN` (for AF_PACKET/TPACKET_V3)

**B)** `CAP_BPF`, `CAP_PERFMON`, `CAP_NET_RAW` (for eBPF/XDP)

**C)** Rootless with `NET_RAW` via `CAP_NET_RAW` only (limited capture)

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — CAP_NET_RAW + CAP_NET_ADMIN + CAP_SYS_ADMIN; evaluar si CAP_SYS_ADMIN se puede dropear

---

### Question 15: Export and Evidence Format
PRD §3.5: "logs estructurados conservan fecha/hora, activo o par origen/destino, método, protocolo, condición, regla, umbral, valor medido y resultado". U5: "exportación estructurada... CSV/JSON".

**A)** JSON Lines for logs/events; CSV for bulk export; both via Core API

**B)** Parquet for analytics; JSON for real-time; CSV on demand

**C)** JSON only; CSV generated client-side from JSON

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — JSON Lines para eventos, CSV para bulk export

---

### Question 16: Test Scenarios and Ground Truth
PRD §11: "Ground truth de laboratorio" with cases: normal, nuevo host, host ausente, cambio puerto/servicio, cambio IP/MAC, tráfico bajo/alto, aumento ARP, ruido legítimo, sensor caído, error de permisos.

**A)** Implement all 11 ground truth cases as integration tests in CI

**B)** Core 5 cases for MVP: normal, nuevo host, host ausente, tráfico alto, sensor caído

**C)** Property-based tests for parsing/normalization; scenario tests for key flows only

**X)** Other (please describe after [Answer]: tag below)

[Answer]: B — 5 casos core; los 11 son stretch

---

## Extension Opt-In Questions (Mandatory)

### Question 17: Security Extensions
Should security extension rules be enforced for this project?

**A)** Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)

**B)** No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — enforce all SECURITY rules (proyecto enfocado en seguridad)

---

### Question 18: Resiliency Extensions
Should the resiliency baseline be applied to this project?

**What this extension is.** Enabling it applies a set of **directional, design-time best practices** for building resilient systems, derived from the **AWS Well-Architected Framework (Reliability Pillar)** and resilience-review guidance. It steers requirements, design, and code toward fault tolerance, high availability, observability, and recoverability — covering 15 practice areas across business goals, change management, observability, high availability, disaster recovery, and continuous improvement.

**What this extension is NOT.** Enabling it does **not** make your workload production-ready, nor does it certify or guarantee any availability, RTO, or RPO target. It is a **starting point** that scaffolds good resiliency decisions early — it is not a substitute for a formal **AWS Well-Architected Review** of the built system.

Treat the output as a well-grounded **first draft of your resiliency posture** to build on and validate — not a finished, production-certified result.

**A)** Yes — apply the resiliency baseline as directional best practices and design-time guidance (recommended for business-critical workloads, as an informed starting point that you can validate and harden before go-live)

**B)** No — skip the resiliency baseline (suitable for PoCs, prototypes, and experimental projects where rapid iteration matters more than reliability)

**X)** Other (please describe after [Answer]: tag below)

[Answer]: B — skip (prototipo académico, no producción)

---

### Question 19: Property-Based Testing Extensions
Should property-based testing (PBT) rules be enforced for this project?

**A)** Yes — enforce all PBT rules as blocking constraints (recommended for projects with business logic, data transformations, serialization, or stateful components)

**B)** Partial — enforce PBT rules only for pure functions and serialization round-trips (suitable for projects with limited algorithmic complexity)

**C)** No — skip all PBT rules (suitable for simple CRUD applications, UI-only projects, or thin integration layers with no significant business logic)

**X)** Other (please describe after [Answer]: tag below)

[Answer]: B — partial PBT (parsing XML Nmap, normalización, baseline)

---

## Additional Clarifications (Optional)

### Question 20: Kubernetes Distribution and Version Target
**A)** Vanilla Kubernetes 1.28+ (EKS/GKE/AKS/k3s/kind compatible)

**B)** Specific distribution: k3s (lightweight, good for labs)

**C)** OpenShift (additional security constraints)

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — vanilla Kubernetes 1.28+, testeado en kind/k3s

---

### Question 21: Container Image Base and Build
**A)** Distroless/static base (gcr.io/distroless/static) — minimal attack surface

**B)** Alpine-based — small, familiar, apk for debugging

**C)** Ubuntu/Debian slim — broader compatibility, larger

**X)** Other (please describe after [Answer]: tag below)

[Answer]: B — Alpine base (minimal attack surface)

---

### Question 22: Programming Language for Core Components
PRD §13: "Linux y contenedores: scripts de descubrimiento y sensor empaquetados en imagen mínima", "consulta de estado de cargas desde Python".

**A)** Python for all (discovery scripts, sensor, Core API) — single language, rich ecosystem

**B)** Go for Core/sensor (performance, concurrency); Python for discovery scripts

**C)** Rust for sensor (memory safety, performance); Python/Go for rest

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — Python para todo (FastAPI + scapy)

---

### Question 23: CI/CD Pipeline Scope
PRD §13: "CI/CD/GitOps: pipeline de pruebas, build, análisis de imagen y despliegue; Argo CD sujeto al tiempo disponible".

**A)** GitHub Actions / GitLab CI: lint, test, build, image scan, helm test, deploy to kind/k3s

**B)** Minimal CI: build + unit test only; deploy manual

**C)** Full GitOps: Argo CD + image updater + automated promotion

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — full CI; B si el tiempo aprieta

---

### Question 24: Documentation and Runbooks
**A)** Markdown docs in repo: architecture, deployment, operations, troubleshooting runbooks

**B)** MkDocs/GitBook site generated from docs; runbooks as separate markdown

**C)** Minimal: README + Helm values reference + PRD/PVB links

**X)** Other (please describe after [Answer]: tag below)

[Answer]: A — markdown en repo

---

## Instructions for Response

Please fill in your answers directly in this document after each `[Answer]:` tag. 

- For multiple choice: enter the letter (A, B, C, or X)
- For "X) Other": provide your description after the `[Answer]:` tag
- You may answer multiple questions at once
- Once all questions are answered, I will analyze for ambiguities and may ask follow-up questions
- When all ambiguities are resolved, I will generate the final `requirements.md` document

---

**Note**: Questions 1-16 are derived from PRD/PVB analysis. Questions 17-19 are mandatory extension opt-in prompts. Questions 20-24 are additional clarifications for technical decisions.