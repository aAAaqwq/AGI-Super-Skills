# 17-Phase 144v Sweep Pack

This directory contains a phase-based grid sweep pack generated from
`backtester/sweeps/full_144v.yaml`.

## Why this pack exists

- `full_144v.yaml` gives broad parameter coverage, but the full cartesian grid is intractable.
- This pack keeps **all sweepable 142 axes** while reducing value density per axis for practical grid runs.
- Total scale is auto-tuned to a practical CPU grid target.

## Current scale

- Phases: **17**
- Axes covered: **142** (all sweepable `full_144v` axes, each exactly once)
- Default target combos per interval: **100,000**
- Current generated combos per interval: **100,602**
- No-op axis excluded from optimisation: `trade.use_bbo_for_fills`

## Files

- `p01_144v.yaml` ... `p17_144v.yaml`: phase specs
- `manifest.yaml`: phase metadata, combo counts, and path assignment

## Regeneration

From repo root:

```bash
python3 backtester/sweeps/generate_17phase_144v.py --target-combo 100000
```

This rewrites all phase files and `manifest.yaml` deterministically.
