# Scheduled Replay Alignment Gate

## Objective

Automate deterministic replay alignment checks on a schedule and maintain a
machine-readable release blocker status.

The scheduled gate performs:

1. replay bundle build for a recent live window
2. paper deterministic replay harness execution
3. strict alignment gate evaluation (including live/paper reconcile and GPU parity)
4. release-blocker status update

The strict gate is fail-closed for live run continuity:

- the replay bundle records `manifest.live_run_fingerprint_provenance`
- alignment asserts `run_fingerprint_distinct <= 1` by default
- windows spanning live daemon restarts (multiple run fingerprints) fail as `state_initialisation_gap`

This prevents mixing multiple live runtime states into one deterministic replay claim.

## Command

```bash
python tools/run_scheduled_replay_alignment_gate.py \
  --candles-db ./candles_dbs/candles_1h.db \
  --funding-db ./backtester/data/funding_rates_1h.db \
  --interval 1h \
  --window-minutes 240 \
  --lag-minutes 2 \
  --min-live-trades 1 \
  --strict-no-residuals
```

Default output locations:

- run report: `<bundle-dir>/scheduled_alignment_gate_run.json`
- blocker status: `<bundle-root>/release_blocker.json`

## Environment Variables

You may configure the scheduler via environment variables:

- `AI_QUANT_REPLAY_GATE_LIVE_DB`
- `AI_QUANT_REPLAY_GATE_PAPER_DB`
- `AI_QUANT_REPLAY_GATE_CANDLES_DB`
- `AI_QUANT_REPLAY_GATE_FUNDING_DB` (optional)
- `AI_QUANT_REPLAY_GATE_INTERVAL`
- `AI_QUANT_REPLAY_GATE_WINDOW_MINUTES`
- `AI_QUANT_REPLAY_GATE_LAG_MINUTES`
- `AI_QUANT_REPLAY_GATE_MIN_LIVE_TRADES`
- `AI_QUANT_REPLAY_GATE_STRICT_NO_RESIDUALS`
- `AI_QUANT_REPLAY_GATE_BUNDLE_ROOT`
- `AI_QUANT_REPLAY_GATE_BLOCKER_FILE`

## Release Blocker Semantics

`release_blocker.json` is fail-closed:

- `blocked = true`: do not proceed with strategy/runtime rollout
- `blocked = false`: latest scheduled gate run passed

The file also records `reason_codes` and the exact report path for audit.

## Operating Notes for Run-Fingerprint Drift

When a scheduled run fails with `live_run_fingerprint_drift_within_window`:

1. Prefer a narrower replay window that stays within one live run fingerprint.
2. Re-run after the live daemon has remained stable for the full target window.
3. Use an override only for emergency diagnostics, not for release promotion.

## Execution-Model Assumptions in Replay Manifests

`replay_bundle_manifest.json` now includes `alignment_assumptions.bbo_fill_model`.

- `enabled_any=true` means one or more strategy scopes use `trade.use_bbo_for_fills`.
- Live/paper may then execute entries/exits with BBO-derived fill prices, while current backtester replay remains candle-price based.
- In that mode, price/PnL drift can be an expected model residual and must be labelled explicitly in audit triage.

Do not treat this as an unknown deterministic logic bug unless BBO execution is also simulated in replay.
