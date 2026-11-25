# Requirements Specification — Sentinel

**Project**: Sentinel — Self-hosted deterministic network asset monitoring platform on Kubernetes
**Source Documents**: `entradas/prd.md` (v3.0), `entradas/pvb.md`
**Date**: 2026-11-07
**Phase**: INCEPTION — Requirements Analysis (Completed)
**Status**: APPROVED by user on 2026-11-07

---

## 1. Project Overview

Sentinel is a **deterministic** self-hosted platform for monitoring network assets on Kubernetes. It performs periodic network discovery (ARP/ICMP/TCP + Nmap service detection), captures traffic metadata from a SPAN/mirror port, computes baselines, detects anomalies, and exports structured evidence. The product contains **no AI/LLM/orchestration/agent components** — all logic is deterministic rule-based.

It also includes a lightweight operator web GUI (module M10) over the Core API for inventory, events, alerts and report generation. The GUI is a presentation layer only: it does not write to SQLite directly and does not perform remote actions on monitored assets.

**Scope Lock**: AI agent explicitly excluded from MVP and all future versions (see audit.md 2026-11-07T00:30:00Z). GUI module M10 added on 2026-11-07 to support the defense/demo (see audit.md 2026-11-07T16:25:32Z).

---

## 2. Functional Requirements

### 2.1 Network Discovery

| ID | Requirement | Source |
|----|-------------|--------|
| FR-DISC-01 | Perform ARP, ICMP echo, and TCP connect (-sT) discovery scans on configured subnet(s) | PRD §3.1, Q1=A |
| FR-DISC-02 | Run Nmap with `-sV --version-light` for service/version detection; no `-O`, no NSE, no UDP, no aggressive mode | PRD §3.1, Q1=A |
| FR-DISC-03 | Execute discovery on configurable interval (default 15 min), configurable via Helm values | PRD §3.3, Q2=A |
| FR-DISC-04 | Support single sensor/subnet in MVP; `sensor_id` field reserved in all observations for future multi-sensor | PRD §8 Could Have, Q9=C |
| FR-DISC-05 | SNMP read-only discovery as optional module, enabled via Helm values (v2c/v3, configurable OIDs) | PRD §8 Should Have, Q10=C |
| FR-DISC-06 | Support two scope modes via Helm values: `scope.mode: cidr` (authorized subnet ranges) and `scope.mode: explicit_hosts` (explicit IP/host list for lab assets) | Defense/lab decision 2026-11-07 |

### 2.2 Traffic Metadata Capture

| ID | Requirement | Source |
|----|-------------|--------|
| FR-TRAF-01 | Capture traffic metadata via Linux `AF_PACKET` / `TPACKET_V3` on a mirror/SPAN port | PRD §3.2, Q3=A |
| FR-TRAF-02 | Sensor Pod runs with `hostNetwork: true` and capabilities `CAP_NET_RAW`, `CAP_NET_ADMIN`, `CAP_SYS_ADMIN` (evaluate if `CAP_SYS_ADMIN` can be dropped) | PRD §9 M3/M9, Q14=A |
| FR-TRAF-03 | Parse and extract only: timestamp, protocol, src IP, dst IP, packet length (bytes). MAC and port are NOT extracted for IP traffic in MVP. ARP fields (psrc, pdst, hwsrc, hwdst) are captured separately per FR-ARP-01. | PRD §3.2 |
| FR-TRAF-04 | Aggregate flows into configurable time windows: 1s, 5s (default), 10s, 30s, 60s via Helm values | PRD §3.3, Q4=B |
| FR-TRAF-05 | Export aggregated flow records to Core via HTTP/JSON ingestion API | PRD §9 M4, Q8=B |

### 2.3 ARP Monitoring (Layer 2)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-ARP-01 | Capture both ARP request (opcode 1) and reply (opcode 2) | PRD §3.2, Q6=C |
| FR-ARP-02 | Track IP↔MAC mappings per interface; detect mapping changes | PRD §3.2, E-04 |
| FR-ARP-03 | Compute ARP rate per interface; trigger alert rule `ArpRateThresholdExceeded` (R-02) | PRD §3.2, R-02 |
| FR-ARP-04 | Trigger alert rule `ArpMappingChanged` (R-03) on IP↔MAC binding change | PRD §3.2, R-03, E-04 |

### 2.4 Baseline Engine & Alerting

| ID | Requirement | Source |
|----|-------------|--------|
| FR-BASE-01 | Compute baseline from first 5 samples at configured aggregation interval (default 5s → 25s init window) | PRD §3.3, Q5=A |
| FR-BASE-02 | Calculate mean (μ) and sample variance (s²) per flow metric (bytes, packets, flows) | PRD §3.3 |
| FR-BASE-03 | Support configurable threshold: `μ + k·s` with Helm-configurable `k`; absolute threshold as fallback | PRD §3.3, Q5=A |
| FR-BASE-04 | Suppress alerts during baseline establishment window (first 25s default) | Q5=A |
| FR-BASE-05 | Alert rules: `TrafficThresholdExceeded` (R-01), `ArpRateThresholdExceeded` (R-02), `ArpMappingChanged` (R-03), `SensorUnavailable` (R-04) | PRD §3.2 |

### 2.5 Core API & Persistence

| ID | Requirement | Source |
|----|-------------|--------|
| FR-CORE-01 | Expose HTTP/JSON API for: ingestion (sensor → core), query (evidence, assets, alerts), export (CSV/JSON) | PRD §9 M4, Q8=B |
| FR-CORE-02 | Expose `/metrics` endpoint on port 9108 for Prometheus scraping (ServiceMonitor) | PRD §9 M6, Q8=B |
| FR-CORE-03 | Persist events, assets, alerts, and baselines in SQLite on PVC | PRD §9 M4, Q7=A |
| FR-CORE-04 | Assign stable UUID to each persisted event (U5) | PRD §9 U5 |
| FR-CORE-05 | Normalize and correlate discovery + traffic + ARP observations | PRD §9 M4 |

### 2.6 Export & Evidence

| ID | Requirement | Source |
|----|-------------|--------|
| FR-EXP-01 | Emit structured JSON Lines for real-time event logs | PRD §3.5, Q15=A |
| FR-EXP-02 | Support bulk CSV export via Core API (all fields: timestamp, asset/pair, method, protocol, condition, rule, threshold, measured value, result) | PRD §3.5, U5, Q15=A |
| FR-EXP-03 | Export available on-demand via HTTP API; no scheduled push | Q15=A |

### 2.7 Observability & Alerting

| ID | Requirement | Source |
|----|-------------|--------|
| FR-OBS-01 | Deploy Sentinel Helm chart; observability stack (Prometheus, Grafana, Alertmanager) via separate `kube-prometheus-stack` | PRD §9 M7, Q11=B |
| FR-OBS-02 | Core exposes metrics for: discovery runs, flow counts, alert counts, baseline status, sensor health | PRD §9 M6 |
| FR-OBS-03 | Alertmanager configured with webhook receiver only (document webhook.site for demos) | PRD §8 Should Have, Q12=B |
| FR-OBS-04 | Grafana dashboards: asset inventory, traffic baselines, alert timeline, sensor health | PRD §9 M7 |

### 2.8 Security & Network Policies

| ID | Requirement | Source |
|----|-------------|--------|
| FR-SEC-01 | Default-deny NetworkPolicy; allow only Core↔Sensor, Core↔Prometheus, Grafana↔Prometheus | PRD §8 Should Have, Q13=A |
| FR-SEC-02 | Document requirement for CNI supporting NetworkPolicy (Calico, Cilium, k3s default) | Q13=A |
| FR-SEC-03 | RBAC: least-privilege ServiceAccounts for Core, Sensor, Grafana | PRD §9 M9 |
| FR-SEC-04 | [Inferido] Pod Security Standards: restricted profile where possible; sensor Pod documented exception for capabilities. | PRD §9 M9 |

### 2.9 Operator GUI & Network Report (M10)

The GUI is a fast, low-complexity operator interface built on server-rendered pages (FastAPI + Jinja + HTMX + Tailwind/DaisyUI) served by Sentinel Core. It is stateless and consumes only the Core HTTP API; it never opens SQLite directly.

| ID | Requirement | Source |
|----|-------------|--------|
| FR-GUI-01 | Provide a read-only asset inventory view: IP, MAC, hostname, OS (observed/inferred/declared/unknown), last seen, status (present/absent) and source | Defense 2026-11-07 |
| FR-GUI-02 | Provide an asset detail view with observation history, events, traffic summary and ARP mappings for the selected asset | Defense 2026-11-07 |
| FR-GUI-03 | Provide an events and alerts timeline with filters by asset, severity, rule and time range; show whether each alert is firing or resolved | Defense 2026-11-07 |
| FR-GUI-04 | Allow triggering a discovery cycle for one configured host or the whole explicit host list; show cycle status and result | Defense 2026-11-07 |
| FR-GUI-05 | Show system health: Core status, last successful discovery cycle, collector/sensor heartbeat and degraded-data warnings | Defense 2026-11-07 |
| FR-GUI-06 | Generate and download a network report (Markdown and PDF) with inventory summary, changes, top talkers (when traffic data exists), alerts and evidence range; also export CSV/JSON | Defense 2026-11-07 |
| FR-GUI-07 | GUI must not be publicly exposed: lab access only via `kubectl port-forward`; no `LoadBalancer`/`NodePort`. Operator authentication is out of scope for the MVP demo (documented as future work). | Defense 2026-11-07, Q5=D |
| FR-GUI-08 | GUI must clearly distinguish observed, inferred, declared and unknown values; it must not present unknown data as confirmed | PRD §6.5 |

---

## 3. Non-Functional Requirements

| ID | Requirement | Source |
|----|-------------|--------|
| NFR-PERF-01 | [Objetivo inicial] Discovery scan <60s for /24. Not binding; validated in lab. | PRD §3.1 |
| NFR-PERF-02 | [Objetivo inicial] Sensor ≥10k flows/s on 2 cores. Not binding. | PRD §3.2 |
| NFR-PERF-03 | [Objetivo inicial] Core API p95 <500ms. Not binding. | — |
| NFR-AVAIL-01 | Single-sensor MVP; no HA requirements (sensor down → gap in visibility, alert on sensor down) | Q16=B |
| NFR-AVAIL-02 | Core restarts recover state from SQLite PVC | FR-CORE-03 |
| NFR-SEC-01 | All SECURITY extension rules enforced as blocking constraints | Q17=A |
| NFR-SEC-02 | Container images: Alpine base, non-root user (except sensor capabilities) | Q21=B |
| NFR-SEC-03 | Image vulnerability scan in CI pipeline | Q23=A |
| NFR-OPS-01 | Helm chart configurable via values.yaml for all tunable parameters (intervals, windows, thresholds, capabilities) | Q2, Q4, Q5, Q14 |
| NFR-OPS-02 | Full CI pipeline: lint, unit test, integration test (5 ground-truth cases), build, image scan, helm test, deploy to kind/k3s | Q16=B, Q23=A |
| NFR-OPS-03 | Documentation: Markdown in repo (architecture, deployment, operations, troubleshooting runbooks) | Q24=A |
| NFR-TECH-01 | Target: vanilla Kubernetes 1.28+ (tested on kind, k3s) | Q20=A |
| NFR-TECH-02 | Implementation language: Python 3.11+ (FastAPI, scapy, nmap parser) | Q22=A |
| NFR-TECH-03 | Property-based testing enforced for: Nmap XML parsing, flow normalization, baseline calculations | Q19=B |
| NFR-TECH-04 | GUI stack: FastAPI + Jinja2 + HTMX + Tailwind/DaisyUI, server-rendered, no SPA build step. Responsive and readable on a laptop for the defense demo. | Defense 2026-11-07 |
| NFR-OPS-04 | GUI is served by the Core workload (static assets and templates baked into the image) and exposed through the Core Service; no separate frontend deployment in MVP. | Defense 2026-11-07 |
| NFR-OPS-05 | Report generation must be deterministic and reproducible from persisted data; the same date range and filters produce the same summary sections. | Defense 2026-11-07 |

---

## 4. Technical Constraints

| Constraint | Value |
|------------|-------|
| Kubernetes | 1.28+ (vanilla, EKS/GKE/AKS/k3s/kind compatible) |
| Container Base | Alpine Linux |
| Language | Python 3.11+ (FastAPI, scapy, python-nmap) |
| Persistence | SQLite 3 on PVC (single-node) |
| Ingress/API | HTTP/JSON only; `/metrics` for Prometheus; GUI served by Core |
| GUI | FastAPI + Jinja2 + HTMX + Tailwind/DaisyUI; server-rendered; operator-only access |
| Observability | Separate `kube-prometheus-stack` deployment |
| Network Policy | Default-deny; requires Calico/Cilium/k3s CNI |
| Sensor Privileges | `hostNetwork: true`, `CAP_NET_RAW`, `CAP_NET_ADMIN`, `CAP_SYS_ADMIN` (evaluate drop) |
| CI/CD | GitHub Actions / GitLab CI (full pipeline per Q23=A) |
| Documentation | Markdown in repository |

---

## 5. Extension Enforcement Status

| Extension | Status | Scope |
|-----------|--------|-------|
| Security | **MANDATORY (blocking)** | All phases — Q17=A |
| Resiliency | **SKIPPED** | Not applied — Q18=B (academic prototype) |
| Property-Based Testing | **PARTIAL (blocking for designated areas)** | Nmap XML parsing, flow normalization, baseline calculations — Q19=B |

---

## 6. Anti-Requirements (Explicit Exclusions)

| ID | Exclusion | Rationale |
|----|-----------|-----------|
| AR-AI-01 | No LLM/AI agent in product (MVP or future) | Scope locked per audit.md 2026-11-07T00:30:00Z |
| AR-AI-02 | No Tool Layer / function calling / agent orchestration | Deterministic product only |
| AR-AI-03 | No human confirmation workflows for agent operations | No agent exists |
| AR-AI-04 | PRD [TBD] items related to LLM model (local/remote) → resolved as "N/A" | Out of scope |
| AR-AI-05 | No AI-assisted analysis/decision features in Core or Sensor | Deterministic rule engine only |

---

## 7. Acceptance Criteria (Ground Truth)

Per Q16=B: **5 core cases** implemented as integration tests in CI:

| Case | Description | Expected Outcome |
|------|-------------|------------------|
| GT-01 | Normal operation | Assets discovered, traffic baseline established, no alerts |
| GT-02 | New host appears | Asset added to inventory; discovery detects new host |
| GT-03 | Host goes absent | Asset marked absent in inventory after configurable grace period |
| GT-04 | High traffic volume | `TrafficThresholdExceeded` alert (R-01) when > `μ + k·s` |
| GT-05 | Sensor down | Alert on missing ingestion heartbeat; gap documented in evidence |

**Stretch (post-MVP)**: Remaining 6 PRD §11 cases (port/service change, IP/MAC change, low traffic, ARP spike, legitimate noise, permission error).

---

## 8. Open Questions for Design Phase

| ID | Question | Owner |
|----|----------|-------|
| OQ-01 | Can `CAP_SYS_ADMIN` be dropped for AF_PACKET/TPACKET_V3? **→ RESOLVED 2026-11-19 (U5 Infra Q4=A): YES — `AF_PACKET` needs `CAP_NET_RAW`, promiscuous mode `CAP_NET_ADMIN`; `TPACKET_V3` does not require `CAP_SYS_ADMIN` (dropped from documented design, see `construction/u5-traffic/infrastructure-design/infrastructure-design.md` ID-U5-05/§3.3)** | Construction — Sensor design |
| OQ-02 | Exact SQLite schema for events, assets, alerts, baselines | Construction — Core design |
| OQ-03 | Helm values.yaml structure for all configurable parameters | Construction — Infrastructure design |
| OQ-04 | NetworkPolicy YAML templates for default-deny + allow rules | Construction — Infrastructure design |
| OQ-05 | Property-based test specifications for parsing/normalization/baseline | Construction — Test design |

---

## 9. Approval Gate

**Requirements Analysis: APPROVED by user (2026-11-07).**

**Change log**:
- 2026-11-07T16:25:32Z: Added module M10 (operator GUI + network report), FR-DISC-06 (`explicit_hosts` scope mode) and NFR-TECH-04 / NFR-OPS-04 / NFR-OPS-05. Re-approved by default per user instruction; recorded in `audit.md`.
- 2026-11-07T17:04:07Z: FR-GUI-07 adjusted after Application Design Q5=D: no public exposure (port-forward only); operator authentication out of scope for the MVP demo. Recorded in `audit.md`.

This document reflects all 24 decisions from `requirement-verification-questions.md` with the critical no-AI constraint enforced throughout.

**Next Stage**: Application Design (execution plan re-approved).
