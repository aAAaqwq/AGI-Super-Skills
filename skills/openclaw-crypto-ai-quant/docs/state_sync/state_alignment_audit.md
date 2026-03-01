# State Alignment Audit

## Objective

Generate a deterministic, machine-readable audit report for live, paper, and optional snapshot alignment before replay/parity runs.

## Command

```bash
python tools/audit_state_sync_alignment.py \
  --live-db ./trading_engine_live.db \
  --paper-db ./trading_engine.db \
  --snapshot /tmp/live_init_state_v2.json \
  --output /tmp/state_alignment_report.json
```

## Output

The report contains:

- summary metrics (balance, open positions, open orders)
- typed diffs with classifications
- strict pass/fail (`ok`)

Current mismatch classifications:

- `state_initialisation_gap`
- `numeric_policy_divergence`

The typed diffs cover:

- balance mismatches
- reconstructed open-position mismatches
- open-order mismatches

Use this report as a required artefact for state-sync checkpoints before CPU/GPU parity replay runs.
