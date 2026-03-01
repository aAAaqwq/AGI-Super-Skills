# Replay Bundle Alignment Gate

## Objective

Provide one strict pass/fail gate across all bundle alignment reports:

- `state_alignment_report.json`
- `trade_reconcile_report.json`
- `action_reconcile_report.json`
- `live_paper_action_reconcile_report.json` (optional unless required)
- `live_paper_decision_trace_reconcile_report.json` (optional unless required)

This enables deterministic validation in CI or manual workflows.

## Command

```bash
python tools/assert_replay_bundle_alignment.py \
  --bundle-dir /tmp/live_replay_bundle_1h \
  --live-paper-report /tmp/live_replay_bundle_1h/live_paper_action_reconcile_report.json \
  --require-live-paper \
  --live-paper-decision-trace-report /tmp/live_replay_bundle_1h/live_paper_decision_trace_reconcile_report.json \
  --require-live-paper-decision-trace \
  --output /tmp/live_replay_bundle_1h/alignment_gate_report.json
```

Default behaviour:

- requires state report `ok = true`
- requires trade/action report `status.strict_alignment_pass = true`
- when `--require-live-paper` is set, requires live/paper report `status.strict_alignment_pass = true`
- when `--require-live-paper-decision-trace` is set, requires live/paper decision-trace report `status.strict_alignment_pass = true`
- allows accepted residuals unless explicitly disabled

To fail on any accepted residuals:

```bash
python tools/assert_replay_bundle_alignment.py \
  --bundle-dir /tmp/live_replay_bundle_1h \
  --strict-no-residuals
```

## Exit Code Contract

- `0`: all required checks passed
- `1`: one or more checks failed (see `failures` in output JSON)
