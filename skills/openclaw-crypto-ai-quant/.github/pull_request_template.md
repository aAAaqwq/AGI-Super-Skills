## Summary
<!-- 1-3 bullet points describing the change -->

## Risk checklist

> Complete this section for **every** PR. If any box is checked, `@fol2` review is required before merge.

- [ ] This PR modifies **kill-switch or risk-limit** logic (`engine/risk.py`, `docs/success_metrics.md`)
- [ ] This PR modifies **order sizing, leverage, or margin** logic (`engine/oms.py`, `engine/oms_reconciler.py`, `risk-core/`)
- [ ] This PR modifies **live order execution** code (`live/`, `exchange/`)
- [ ] This PR modifies **production config** (`config/strategy_overrides.yaml`)
- [ ] This PR modifies the **strategy lifecycle or promotion gates** (`docs/strategy_lifecycle.md`, `tools/promote_to_live.py`)
- [ ] This PR modifies **decision kernel logic** (`bt-signals/`, `bt-core/src/decision_kernel.rs`, `bt-core/src/exits/`)
- [ ] This PR modifies **GPU codegen** (`bt-gpu/codegen/`, `bt-gpu/kernels/`)

### If any box above is checked:

- [ ] Backtest replay run confirms no regression (attach summary or link)
- [ ] Paper trading verified (or not applicable — explain why)
- [ ] No kill-switch or guardrail thresholds were weakened without explicit sign-off

## Test plan
<!-- How was this tested? -->
