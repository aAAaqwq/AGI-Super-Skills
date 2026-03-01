# Live vs Paper Decision Trace Reconciliation

## Objective

Audit decision-level trace parity (not only trade rows) between `live` and `paper` SQLite databases using `decision_events`.

## Command

```bash
python tools/audit_live_paper_decision_trace.py \
  --live-db ./trading_engine_live.db \
  --paper-db ./trading_engine.db \
  --from-ts 1770700000000 \
  --to-ts 1771200000000 \
  --timestamp-bucket-ms 1 \
  --output /tmp/live_paper_decision_trace_reconcile.json
```

To fail on strict mismatch:

```bash
python tools/audit_live_paper_decision_trace.py \
  --live-db ./trading_engine_live.db \
  --paper-db ./trading_engine.db \
  --from-ts 1770700000000 \
  --to-ts 1771200000000 \
  --fail-on-mismatch \
  --output /tmp/live_paper_decision_trace_reconcile.json
```

## Matching Key

Rows are matched by:

- `symbol`
- `event_type`
- `status`
- `decision_phase`
- `action_taken`
- `triggered_by`
- `timestamp_ms` (bucketed by `--timestamp-bucket-ms`)

## Mismatch Types

- `deterministic_logic_divergence`
  - missing decision event on either side
  - rejection reason mismatch
- `state_initialisation_gap`
  - trade linkage mismatch (`trade_id` present on one side only)

## Pass Criteria

`status.strict_alignment_pass = true` only when there are no mismatches.
