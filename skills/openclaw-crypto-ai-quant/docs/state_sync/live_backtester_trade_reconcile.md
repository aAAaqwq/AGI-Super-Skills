# Live vs Backtester Trade Reconciliation

## Objective

Provide a deterministic, machine-readable reconciliation report between:

- live baseline trades captured in replay bundle (`live_baseline_trades.jsonl`)
- backtester replay trade export (`backtester_trades.csv`)

This validates the simulatable exit path (`CLOSE` / `REDUCE`) for financial-grade parity.

## Command

```bash
python tools/audit_live_backtester_trade_reconcile.py \
  --live-baseline /tmp/live_replay_bundle_1h/live_baseline_trades.jsonl \
  --backtester-trades /tmp/live_replay_bundle_1h/backtester_trades.csv \
  --timestamp-bucket-ms 1 \
  --output /tmp/live_replay_bundle_1h/trade_reconcile_report.json
```

Set `--timestamp-bucket-ms` above `1` only when your live timestamp serialisation is coarser than replay timestamps.

## Comparison Scope

- Compared:
  - `symbol`
  - `side`
  - `exit_ts_ms`
  - `exit_size`
  - `pnl_usd`
  - `fee_usd`
- Out of scope (tracked as accepted residual only):
  - `FUNDING` actions (`non-simulatable_exchange_oms_effect`)
  - replay-only forced exits with reason code `exit_end_of_backtest` (`state_initialisation_gap`)
- Informational only:
  - live `OPEN` and `ADD` actions

## Taxonomy in Report

- `deterministic_logic_divergence`:
  - missing exit in backtester, or missing exit in live baseline
- `numeric_policy_divergence`:
  - matched exit key exists, but `exit_size` / `pnl_usd` / `fee_usd` exceeds tolerance
- `non-simulatable_exchange_oms_effect`:
  - funding events counted as accepted residuals
- `state_initialisation_gap`:
  - replay-only exits with reason code `exit_end_of_backtest` (window-boundary force-close)

## Pass Criteria

`status.strict_alignment_pass` is `true` only when:

- no unmatched exits on either side
- no numeric mismatches beyond configured tolerances

Accepted residuals (`FUNDING` plus `exit_end_of_backtest` boundary closes) do not fail strict replay parity and are reported under `accepted_residuals`.
