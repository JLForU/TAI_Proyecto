# PRIORITY: This workflow OVERRIDES all other built-in workflows
# When user requests software development, ALWAYS follow this workflow FIRST

This file is the AI-DLC dispatcher. It is loaded into every session, so it stays
small (<300 lines). Detailed, phase-specific instructions live in the rule-details
directory and are loaded **just-in-time** — only for the phase you are currently in.
Do not inline phase detail here; add it to the relevant rule-details file instead.

## Project Context
- **WHAT**: Sentinel — plataforma self-hosted de monitoreo de activos de red sobre Kubernetes, con un agente de IA que guía al operador. Requisitos en `entradas/prd.md`; visión en `entradas/pvb.md`.
- **WHY**: Reducir el tiempo y esfuerzo operacional de workflows repetitivos de monitoreo sin ceder al agente capacidad de actuación directa sobre los activos. North Star: tiempo mediano de workflow con evidencia válida (con IA vs sin IA).
- **HOW**: Greenfield, sin código. Comandos de build/prueba se definen por unidad en CONSTRUCTION. `entradas/prd.md` es la fuente autoritativa.

## Adaptive Workflow Principle
**The workflow adapts to the work, not the other way around.**

The AI model intelligently assesses what stages are needed based on:
1. User's stated intent and clarity
2. Existing codebase state (if any)
3. Complexity and scope of change
4. Risk and impact assessment

## MANDATORY: Rule Details Loading (bootstrap — do this first)
**CRITICAL**: When performing any phase, you MUST read and use relevant content from rule detail files. Check these paths in order and use the first one that exists, regardless of which IDE or setup method was used:
- `.aidlc/aidlc-rules/aws-aidlc-rule-details/` (typical with AI-assisted setup)
- `.aidlc-rule-details/` (typical with Cursor, Cline, Claude Code, GitHub Copilot, OpenAI Codex)
- `.kiro/aws-aidlc-rule-details/` (typical with Kiro IDE and CLI)
- `.amazonq/aws-aidlc-rule-details/` (typical with Amazon Q Developer)

All rule-detail references below (e.g. `common/process-overview.md`, `inception/_inception-orchestration.md`) are relative to whichever rule-details directory was resolved above.

**ALWAYS load these common rules at workflow start** (small, universally applicable):
- `common/process-overview.md` — three-phase workflow overview + Mermaid diagram
- `common/session-continuity.md` — session resumption / resume-from-aidlc-state.md guidance
- `common/content-validation.md` — content validation requirements (see also below)
- `common/question-format-guide.md` — question formatting rules
- `common/audit-and-logging.md` — audit trail, prompts logging, checkbox enforcement (see below)

## Phase Dispatch (load only the ACTIVE phase's orchestration)
**CRITICAL context-control rule**: Do NOT load all three phases at once. Determine the
current phase (from the user request, or from `aidlc-docs/aidlc-state.md` on resume), then
load ONLY that phase's orchestration file. It contains every stage, gate, and approval step
for the phase. Move to the next phase's file only when the current phase's required stages
are approved.

| Active phase | Load this orchestration file | Then it sequences stages via |
|---|---|---|
| 🔵 INCEPTION — *what & why* | `inception/_inception-orchestration.md` | `inception/*.md` |
| 🟢 CONSTRUCTION — *how + build/test* | `construction/_construction-orchestration.md` | `construction/*.md` |
| 🟡 OPERATIONS — *deploy/run (placeholder)* | `operations/_operations-orchestration.md` | `operations/*.md` |

Each orchestration file lists its phase's stages, which are ALWAYS vs CONDITIONAL, the
"Execute IF / Skip IF" criteria, and the per-stage approval gates. Follow it exactly; it
points to the individual stage rule files to load when each stage runs.

**Typical entry points**:
- New software request → start INCEPTION (Workspace Detection runs first, ALWAYS).
- Resuming a project → read `aidlc-docs/aidlc-state.md`, follow `common/session-continuity.md`, then load the orchestration file for the current phase only.

## MANDATORY: Custom Welcome Message
When starting ANY software development request, display the welcome message ONCE:
1. Load `common/welcome-message.md`
2. Display the complete message to the user
3. Only once at the start of a new workflow — do NOT reload it in later interactions (saves context)

## MANDATORY: Extensions Loading (Context-Optimized)
At workflow start, scan `extensions/` recursively and load ONLY the lightweight `*.opt-in.md` files — never the full rule files. Present opt-in prompts during Requirements Analysis; load an extension's full rule file ONLY when the user opts in. Extensions with no `*.opt-in.md` are always enforced (load at start). Enabled extension rules are hard constraints and a non-compliance is a blocking finding.
**Full mechanics (deferred loading, enforcement, conditional enable/disable): see `common/extensions-loading.md`.**

## MANDATORY: Content Validation
Before creating ANY file, validate content per `common/content-validation.md`:
- Validate Mermaid diagram syntax
- Validate ASCII art diagrams (see `common/ascii-diagram-standards.md`)
- Escape special characters properly
- Provide text alternatives for complex visual content
- Test content parsing compatibility

## MANDATORY: Question File Format
When asking questions at any phase, follow `common/question-format-guide.md`:
- Multiple choice format (A, B, C, D, E options)
- [Answer]: tag usage
- Answer validation and ambiguity resolution
- ALWAYS ask clarification/feedback questions in `.md` files, NOT inline in chat

## MANDATORY: Audit Trail & Checkbox Enforcement
Full rules in `common/audit-and-logging.md`. The non-negotiable essence:
- Log EVERY user input (complete raw input, never summarized) with an ISO 8601 timestamp in `aidlc-docs/audit.md`, plus every approval prompt and response.
- ALWAYS **append/Edit** audit.md — NEVER overwrite its full contents (causes duplication).
- After completing ANY plan step, mark it `[x]` in the SAME interaction (plan-level); track overall progress in `aidlc-docs/aidlc-state.md` (stage-level).

## Key Principles
- **Adaptive Execution**: Only execute stages that add value
- **Transparent Planning**: Always show the execution plan before starting
- **User Control**: User can request stage inclusion/exclusion
- **Progress Tracking**: Update aidlc-state.md with executed and skipped stages
- **Complete Audit Trail**: Log all inputs/responses with timestamps (see audit-and-logging.md)
- **Quality Focus**: Complex changes get full treatment, simple changes stay efficient
- **Content Validation**: Always validate content before file creation
- **NO EMERGENT BEHAVIOR**: Construction stages MUST use the standardized 2-option completion messages defined in their rule files. DO NOT create 3-option menus or other emergent navigation patterns.

## Directory Structure

```text
<WORKSPACE-ROOT>/                   # ⚠️ APPLICATION CODE HERE
├── [project-specific structure]    # Varies by project (see code-generation.md)
│
├── aidlc-docs/                     # 📄 DOCUMENTATION ONLY
│   ├── inception/                  # 🔵 INCEPTION PHASE
│   │   ├── plans/
│   │   ├── reverse-engineering/    # Brownfield only
│   │   ├── requirements/
│   │   ├── user-stories/
│   │   └── application-design/
│   ├── construction/               # 🟢 CONSTRUCTION PHASE
│   │   ├── plans/
│   │   ├── {unit-name}/
│   │   │   ├── functional-design/
│   │   │   ├── nfr-requirements/
│   │   │   ├── nfr-design/
│   │   │   ├── infrastructure-design/
│   │   │   └── code/               # Markdown summaries only
│   │   └── build-and-test/
│   ├── operations/                 # 🟡 OPERATIONS PHASE (placeholder)
│   ├── aidlc-state.md
│   └── audit.md
```

**CRITICAL RULE**:
- Application code: Workspace root (NEVER in aidlc-docs/)
- Documentation: aidlc-docs/ only
- Project structure: See code-generation.md for patterns by project type
