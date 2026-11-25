# Story Generation Plan — Sentinel

**Phase**: INCEPTION — User Stories
**Status**: APPROVED by user on 2026-11-07T07:09:38Z — generating stories
**Inputs**: `entradas/prd.md` (v3.0), `aidlc-docs/inception/requirements/requirements.md` (approved), `entradas/pvb.md`, `aidlc-docs/inception/plans/user-stories-assessment.md`
**Scope Lock**: AI/LLM/agent/orchestration explicitly excluded. No stories may include agent interaction, LLM, function calling, or AI-assisted analysis.
**Date**: 2026-11-07

---

## 1. Purpose

Convert the approved requirements into user-centered stories that:
- Trace each story to the PRD v3.0 section and to the corresponding FR/NFR/GT identifier in `requirements.md`.
- Carry acceptance criteria that are verifiable by a command or a measurable check.
- Represent the personas that operate and administer Sentinel.
- Provide the direct basis for design, implementation, and the ground-truth integration tests (GT-01..GT-05).

No code will be written in this stage.

---

## 2. Story Approach Options

| Approach | Description | Benefits | Trade-offs |
|---|---|---|---|
| A. Feature-based by module (recommended) | Stories grouped by functional module (M1..M9) and FR clusters | Direct traceability FR→story; easy to map to units later | Can feel system-centric rather than user-centric |
| B. User journey-based | Stories follow UC-01..UC-05 and PRD §7 journeys | Strong narrative; good acceptance criteria | Some technical requirements lack a natural journey; risk of gaps |
| C. Persona-based | Stories grouped by operator, administrator, security reviewer | Very user-centered | Cross-cutting capabilities appear in multiple groups; duplication risk |
| D. Epic-based hierarchical | Epics per module with sub-stories | Handles large scope; clear hierarchy | More overhead; may over-structure a prototype |
| E. Hybrid feature-based + epics | Feature grouping with a few epics for cross-cutting areas | Balance of traceability and narrative | Slightly more complex to maintain |

**Recommendation**: **A (Feature-based by module)**, because the requirements are already organized by module and FR IDs, and the requested traceability is explicit. A traceability matrix plus personas preserves the user-centric view without fragmenting stories.

---

## 3. Proposed Personas (confirmed by Q3=A)

| Persona | Primary goals | Main touchpoints |
|---|---|---|
| Network Operator | Understand which assets exist, what changed, and whether traffic/ARP conditions exceeded thresholds | Grafana dashboards, Alertmanager, CSV/JSON exports |
| Platform Administrator | Deploy and operate Sentinel on Kubernetes safely and reproducibly | Helm values, kubectl, PVC, ServiceMonitor, RBAC, NetworkPolicy |
| Security Reviewer | Verify least privilege, no remote writes, and auditable deterministic evidence | RBAC manifests, NetworkPolicy, capability review, test evidence |

---

## 4. Proposed Story Map (outline, not final stories)

| Group | Candidate stories | Source |
|---|---|---|
| M1 Configuration & scope | Authorized ranges/ports/windows; Helm-configurable values | FR-DISC-03/04/05, NFR-OPS-01, PRD §8, M1 |
| M2 Discovery | Periodic ARP/ICMP/TCP discovery; service/version probing; SNMP optional | FR-DISC-01..05, UC-01, M2 |
| M2 Inventory reconciliation | First seen; missing after successful cycles; port/service change | E-01..E-03, UC-02, GT-02/GT-03 |
| M3 Traffic sensor | Metadata capture; window aggregation; ingestion export | FR-TRAF-01..05, UC-03, M3 |
| M3 ARP | ARP request/reply observation; IP↔MAC mapping changes; ARP rate | FR-ARP-01..04, UC-05 |
| M4/M5 Core & baselines | Ingestion/query API; normalization/correlation; baseline stats; persistence | FR-CORE-01/03/05, FR-BASE-01..04, M4, M5 |
| M4 Export & evidence | JSON Lines logs; CSV bulk export; stable event identity | FR-EXP-01..03, FR-CORE-04, U5 |
| M6 Metrics | `/metrics` on 9108; aggregated indicators; ServiceMonitor | FR-CORE-02, FR-OBS-02, M6 |
| M7 Observability & alerting | Traffic threshold; ARP rate/mapping; sensor unavailable; dashboards; webhook | FR-BASE-05, FR-OBS-01/03/04, R-01..R-04, GT-04/GT-05 |
| M8 Runtime Kubernetes | Helm chart; CronJobs/Deployments/Services/PVC; kind/k3s deployment | FR-OBS-01, NFR-TECH-01, M8 |
| M9 Security & tests | RBAC; NetworkPolicy; Pod Security; no-write proof | FR-SEC-01..04, NFR-SEC-01..03, PRD §6/§8, M9 |
| Enablers | CI pipeline; property-based tests; documentation | NFR-OPS-02/03, NFR-TECH-03 |

---

## 5. Questions (answer each after `[Answer]:`)

### Question 1
In what language should `stories.md` and `personas.md` be written?

A) Spanish — consistent with the PRD v3.0 and the working team language

B) English — consistent with the current `requirements.md`

C) Bilingual — Spanish body with English identifiers and titles

D) Other (please describe after [Answer]: tag below)

[Answer]: C — Spanish body with English identifiers (consistente con PRD/PVB en español y requirements.md en inglés)

### Question 2
Which story breakdown approach should be used?

A) Feature-based by module (M1..M9) with a traceability matrix — recommended for explicit FR→story mapping

B) User journey-based (UC-01..UC-05 and PRD §7)

C) Persona-based grouping

D) Epic-based hierarchy

E) Hybrid feature-based + epics

F) Other (please describe after [Answer]: tag below)

[Answer]: A — Feature-based by module (M1..M9) con matriz de trazabilidad FR→story

### Question 3
Which persona set should be documented?

A) Three personas: Network Operator, Platform Administrator, Security Reviewer — recommended

B) Two personas: Network Operator and Platform Administrator

C) Four personas: add an Academic Evaluator

D) Use only the ICP profile in the PRD without new persona definitions

E) Other (please describe after [Answer]: tag below)

[Answer]: A — Three personas: Network Operator, Platform Administrator, Security Reviewer

### Question 4
What format should acceptance criteria use?

A) Given/When/Then plus a `Verification:` line with the exact command or check — recommended

B) A table with columns Criterion / Command or check / Expected result

C) Simple bullet list with the verification in parentheses

D) Other (please describe after [Answer]: tag below)

[Answer]: A — Given/When/Then + Verification: line with exact command or measurable check

### Question 5
How should non-functional requirements and engineering enablers be represented?

A) Functional stories plus a separate `Enabler stories` section for verifiable NFRs (CI, Helm, security, PBT) — recommended

B) Only functional stories; NFRs appear as cross-cutting acceptance criteria

C) One story per NFR

D) Other (please describe after [Answer]: tag below)

[Answer]: A — Functional stories + separate Enabler stories section for verifiable NFRs

### Question 6
Should each story carry a priority?

A) Yes, MoSCoW (Must/Should/Could) aligned with the PRD — recommended

B) No priority; order only by dependency

C) Numeric priority P0/P1/P2

D) Other (please describe after [Answer]: tag below)

[Answer]: A — MoSCoW aligned with PRD §8

### Question 7
The project is greenfield, so verification commands do not run yet. How should they be expressed?

A) Target commands (`helm`, `kubectl`, `curl`, `pytest`) defined now and runnable once implemented — recommended

B) Only conceptual measurable checks without concrete commands

C) Generate runnable verification scripts now (would imply writing code, out of scope)

D) Other (please describe after [Answer]: tag below)

[Answer]: A — Target commands defined now (helm, kubectl, curl, pytest); runnable once implemented

---

## 5.1 Answer Validation (Step 9)

All 7 `[Answer]:` tags are complete and valid. No ambiguities, contradictions, or vague responses detected.

| Q | Answer | Effect on generation |
|---|---|---|
| Q1 | C — bilingual | Spanish body; IDs, titles, and command names in English |
| Q2 | A — feature-based | Stories grouped by M1..M9; traceability matrix included |
| Q3 | A — three personas | Network Operator, Platform Administrator, Security Reviewer |
| Q4 | A — Given/When/Then + Verification | Every story uses G/W/T plus an exact target command or measurable check |
| Q5 | A — functional + enablers | Functional stories in main section; verifiable NFRs in a separate Enabler stories section |
| Q6 | A — MoSCoW | Every story tagged Must/Should/Could per PRD §8 |
| Q7 | A — target commands | Commands are defined now and become runnable after implementation; no code is written in this stage |

No follow-up questions required.

---

## 6. Generation Plan (executed only after plan approval)

- [x] Record answers and verify all `[Answer]:` tags are complete
- [x] Analyze answers for ambiguity/contradictions; ask follow-ups if needed (none required)
- [x] Log plan approval prompt in `aidlc-docs/audit.md`
- [x] Obtain explicit user approval of this plan
- [x] Generate `aidlc-docs/inception/user-stories/personas.md` (mandatory)
- [x] Generate `aidlc-docs/inception/user-stories/stories.md` (mandatory) following INVEST
- [x] Add acceptance criteria to every story in the approved format
- [x] Add traceability matrix (FR/NFR/GT → story)
- [x] Add enabler stories if approved in Q5
- [x] Map personas to stories
- [x] Verify no story references AI/LLM/agent (scope lock)
- [x] Mark each step `[x]` immediately upon completion
- [x] Update `aidlc-docs/aidlc-state.md`
- [x] Log completion message and stories approval prompt
- [x] Stop at the User Stories approval gate; do NOT self-approve

---

## 7. Mandatory Artifacts

- `aidlc-docs/inception/user-stories/personas.md`
- `aidlc-docs/inception/user-stories/stories.md`

Stories must be Independent, Negotiable, Valuable, Estimable, Small, and Testable.

---

## 8. Approval Required

All questions are answered and validated. This plan is now at the explicit approval gate.

**To approve**, reply with an unambiguous statement such as: `Apruebo el story-generation-plan.md; procede a generar personas.md y stories.md.`

Generation will not start until that explicit approval is recorded. If you want changes, state them and I will update this plan and re-request approval.
