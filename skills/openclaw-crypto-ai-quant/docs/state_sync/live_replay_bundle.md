# Live Replay Bundle

## Objective

Create a deterministic replay bundle for a fixed live window so all alignment runs use the same inputs and commands.

## Build Bundle

```bash
python tools/build_live_replay_bundle.py \
  --live-db ./trading_engine_live.db \
  --paper-db ./trading_engine.db \
  --candles-db ./candles_dbs/candles_1h.db \
  --funding-db ./backtester/data/funding_rates_1h.db \
  --interval 1h \
  --from-ts 1770700000000 \
  --to-ts 1771200000000 \
  --bundle-dir /tmp/live_replay_bundle_1h
```

## Bundle Contents

- `replay_bundle_manifest.json`
- `live_baseline_trades.jsonl`
- `backtester_replay_report.json`
- `live_paper_action_reconcile_report.json`
- `live_paper_decision_trace_reconcile_report.json`
- `event_order_parity_report.json`
- `gpu_smoke_parity_report.json`
- `alignment_gate_report.json`
- `paper_deterministic_replay_run.json`
- `run_01_export_and_seed.sh`
- `run_02_replay.sh`
- `run_03_audit.sh`
- `run_04_trade_reconcile.sh`
- `run_05_action_reconcile.sh`
- `run_06_live_paper_action_reconcile.sh`
- `run_07_live_paper_decision_trace_reconcile.sh`
- `run_07b_event_order_parity.sh`
- `run_07c_gpu_parity.sh`
- `run_08_assert_alignment.sh`
- `run_09_paper_deterministic_replay.sh`

## Usage Sequence

1. Run `run_01_export_and_seed.sh`
2. Run `run_02_replay.sh`
3. Run `run_03_audit.sh`
4. Run `run_04_trade_reconcile.sh`
5. Run `run_05_action_reconcile.sh`
6. Run `run_06_live_paper_action_reconcile.sh`
7. Run `run_07_live_paper_decision_trace_reconcile.sh`
8. Run `run_07b_event_order_parity.sh`
9. Run `run_07c_gpu_parity.sh`
10. Run `run_08_assert_alignment.sh`
11. Optional one-shot harness: `run_09_paper_deterministic_replay.sh`

For strict shortcut mode:

```bash
STRICT_NO_RESIDUALS=1 /tmp/live_replay_bundle_1h/run_09_paper_deterministic_replay.sh
```

This keeps snapshot seeding, replay execution, state alignment audit, backtester trade/action reconciliation, live/paper action reconciliation, live/paper decision-trace reconciliation, live-baseline/paper event-order parity, bundle-scoped CPU/GPU parity, and final strict alignment gate tied to one immutable bundle manifest.

The manifest records both file-level and window-level market-data provenance:

- input file hashes (`candles_db_sha256`, optional `funding_db_sha256`)
- `candles_provenance.window_hash_sha256` for the exact `(interval, from_ts, to_ts)` window rows
- `candles_provenance.universe_hash_sha256` and `candles_provenance.symbols` for universe lock

`run_08_assert_alignment.sh` now validates this candle provenance by recomputing the same window hash/universe fingerprint from the candles DB and failing the gate on mismatch.
It also requires `event_order_parity_report.json` to pass, so live-baseline vs paper event ordering drift fails the same gate.
It also requires `gpu_smoke_parity_report.json` lane ranking assertions to pass, so bundle-scoped CPU/GPU drift fails the same gate.

If the candles DB path differs across environments, pass an explicit override:

```bash
python tools/assert_replay_bundle_alignment.py \
  --bundle-dir /tmp/live_replay_bundle_1h \
  --candles-db /path/to/candles_1h.db
```

The generated `run_08_assert_alignment.sh` also honours `CANDLES_DB` for this override path.

## GPU Requirement

`run_07c_gpu_parity.sh` requires a CUDA-capable environment because it runs both CPU and GPU sweep lanes for parity comparison.

## Execution Context

The generated scripts auto-detect bundle-local artefact paths via `BUNDLE_DIR` and use `REPO_ROOT` for tool/binary paths.

- default `REPO_ROOT` is the current shell working directory
- set `REPO_ROOT=/path/to/openclaw-crypto-ai-quant` when running outside repo root
