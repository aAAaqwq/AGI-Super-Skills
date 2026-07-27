# Product document system

## Shared fact matrix

Maintain a table with these columns:

| Claim/feature | Version/platform | User outcome | Side effect | Source code/config | Test/runtime evidence | Screenshot | Status/limitation |
|---|---|---|---|---|---|---|---|

Resolve conflicts before writing. Prefer the scoped commit and observed behavior over a broad planning document. Preserve an explicit “planned” label when implementation is absent.

## Document roles

### Product description

Cover audience, problem, value, differentiators, capability summary, control model, data boundary, external prerequisites, honest limitations, and supported platforms. Avoid becoming an installation manual.

### Full user manual

Cover prerequisites, installation, login, first-run checks, first successful workflow, interface map, every major operation, parameter semantics, preview/real execution, data locations, troubleshooting, upgrade, backup, and uninstall.

### Daily operations guide

Cover the recurring rhythm, automation schedules, human checkpoints, routine exceptions, and a compact FAQ. Link to the full manual instead of duplicating it.

### Technical specification

Cover architecture, components, interfaces, process boundaries, configuration, data model, security controls, deployment, observability, failure handling, and non-functional constraints. Map statements to source evidence.

### Acceptance document

For each item record:

- identifier and priority;
- environment and prerequisites;
- exact steps and input;
- expected externally observable result;
- evidence location;
- pass/fail/NA result;
- known limitation and owner.

Separate unit, integration, installed-app, and real external-system evidence. A test count is not a substitute for a feature-specific acceptance result.

## User-journey skeleton

1. What the product does and does not decide.
2. Supported environment and data boundary.
3. Install and launch.
4. Authentication and prerequisites.
5. Self-check and first safe preview.
6. First real outcome.
7. Normal daily workflow.
8. Advanced configuration and scheduling.
9. Data, backup, privacy, and cloud behavior.
10. Troubleshooting, recovery, upgrade, and support.

## Quality gates

- All version/platform references agree.
- Commands and paths are valid for the target platform.
- Every screenshot is current, legible, and privacy-reviewed.
- Preview/dry-run semantics are operation-specific.
- Output terms distinguish intent from verified result.
- No promised feature lacks implementation evidence.
- Unsupported states and external service limits are explicit.
- Relative links resolve and generated documents render correctly.
- Archived documents point to the current replacement.
