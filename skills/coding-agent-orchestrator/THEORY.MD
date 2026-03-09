# Theory: ACP-First Routing with CLI Durability

## Problem

The skill pack has had a strong CLI fallback story (`codex`, `claude`, optional
`gemini`) but no ACP-first behavior, even though OpenClaw sessions increasingly
route coding work through ACP harnesses. That mismatch creates policy drift:
skill docs imply modern harness orchestration while wrappers still start from
direct CLI execution.

The practical risk is inconsistent behavior by entrypoint. A user may ask for
ACP-style delegation in chat, but local wrapper flows still behave as
CLI-first, which weakens predictability and makes troubleshooting harder.

## Operating Theory

ACP-first should be treated as a routing preference, not as a hard dependency.
In this repo, wrappers are shell scripts and cannot directly call
`sessions_spawn`, so the shell-native ACP mechanism is `acpx`. That means the
right implementation is:

1. Attempt ACP through `acpx` first.
2. Preserve existing CLI chain as a reliability backstop.

This keeps operational continuity when ACPX is missing or unhealthy, while
making harness-aware flows the default when ACPX is present.

The key boundaries are install/repair behavior and review quality.
Auto-installing ACPX inside this skill pack would create side effects and
environment coupling that are out of scope for a routing upgrade. So ACPX
discovery should be explicit and cheap: `CODING_AGENT_ACPX_CMD` override first,
then `acpx` on `PATH`. For review mode, preserving review-native behavior
(`codex review --base`) is the quality baseline, with ACP kept as fallback.

## Strategy

The leverage point is `scripts/safe-fallback.sh`, because it already owns the
tool ordering and blocker reporting contract. Implementing ACP routing there
upgrades wrapper behavior without introducing a new command surface.

To keep behavior legible and reversible:

- Add `CODING_AGENT_ACP_ENABLE` (`1` default, `0` kill switch).
- Add `CODING_AGENT_ACP_AGENT` (default `codex`).
- Keep implementation ACP-first, but keep review mode on `codex review --base`
  first and use ACP as fallback to avoid review-quality regression.
- Keep `safe-fallback` timeout semantics and existing CLI sequence unchanged
  after ACP failure.
- Make `doctor` report ACPX as warning-only so missing ACPX does not falsely
  mark environments unusable.

Documentation must mirror runtime behavior in the same change set; otherwise
users get contradictory guidance and reviewers cannot verify intent from docs.

## Key Discoveries

Initially, the repo’s workflow docs and quick references were entirely
CLI-centric, and smoke tests assumed Codex direct execution is always first.
Once ACP-first became the target, the important pivot was to make fake ACPX
fail by default in smoke tests. That preserves existing test expectations while
allowing explicit ACP-success tests to prove the new precedence rule.

Another discovery was that ACP-first review mode degrades confidence compared
to `codex review --base` semantics. The strategy pivot is to keep review-native
CLI first and retain ACP as the fallback path for review mode.

## Open Questions

- Whether wrappers should later add ACPX auto-repair/install logic, or keep
  this repo strictly side-effect free and rely on upstream environment setup.
- Whether `safe-impl.sh`/`safe-review.sh` should eventually get native ACP entry
  modes, or whether `safe-fallback.sh` remains the only ACP-routing wrapper.
- Whether the default ACP agent should stay `codex` or become context-aware by
  task type and user preference.
