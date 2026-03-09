# TODOs

## PLAN_REVIEW_LIVE_ALLOW_NON_TTY deprecation check
- What: Evaluate deprecating `PLAN_REVIEW_LIVE_ALLOW_NON_TTY` after one release cycle.
- Why: `plan-review-live` now supports explicit non-TTY resolution inputs (`--resolve-file` or `--decisions/--blocking`) that are safer and more auditable.
- Context: Added to close issue #30 (chat/non-TTY dead-end for `plan-review-live`).
- Depends on/blocked by: One stable release cycle of smoke + real chat automation runs with the new non-TTY apply path.
