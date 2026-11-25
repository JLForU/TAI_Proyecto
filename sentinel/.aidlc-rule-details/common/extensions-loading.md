# Extensions Loading & Enforcement (Context-Optimized)

**Referenced by CLAUDE.md. At session start, only the lightweight trigger applies (scan
`extensions/` for `*.opt-in.md`). The full mechanics below are loaded just-in-time — they
matter at Requirements Analysis (opt-in) and at each stage's compliance check.**

## Loading process
**CRITICAL**: At workflow start, scan the `extensions/` directory recursively but load ONLY lightweight opt-in files — NOT full rule files. Full rule files are loaded on-demand after the user opts in.

1. List all subdirectories under `extensions/` (e.g., `extensions/security/`, `extensions/compliance/`)
2. In each subdirectory, load ONLY `*.opt-in.md` files — these contain the extension's opt-in prompt. The corresponding rules file is derived by convention: strip the `.opt-in.md` suffix and append `.md` (e.g., `security-baseline.opt-in.md` → `security-baseline.md`)
3. Do NOT load full rule files (e.g., `security-baseline.md`) at this stage

## Deferred Rule Loading
- During Requirements Analysis, opt-in prompts from the loaded `*.opt-in.md` files are presented to the user
- When the user opts IN for an extension, load the corresponding rules file (derived by naming convention) at that point
- When the user opts OUT, the full rules file is never loaded — saving context
- Extensions without a matching `*.opt-in.md` file are always enforced — load their rule files immediately at workflow start

## Enforcement (applies only to loaded/enabled extensions)
- Extension rules are hard constraints, not optional guidance
- At each stage, intelligently evaluate which extension rules are applicable based on the stage's purpose, the artifacts being produced, and the context — enforce only those that are relevant
- Rules not applicable to the current stage are marked N/A in the compliance summary (not a blocking finding)
- Non-compliance with any applicable enabled extension rule is a **blocking finding** — do NOT present stage completion until resolved
- When presenting stage completion, include a summary of extension rule compliance (compliant/non-compliant/N/A per rule, with brief rationale for N/A determinations)

## Conditional Enforcement
Extensions may be conditionally enabled/disabled. See `inception/requirements-analysis.md` for the opt-in mechanism. Before enforcing any extension at ANY stage, check its `Enabled` status in `aidlc-docs/aidlc-state.md` under `## Extension Configuration`. Skip disabled extensions and log the skip in audit.md. Default to enforced if no configuration exists.
