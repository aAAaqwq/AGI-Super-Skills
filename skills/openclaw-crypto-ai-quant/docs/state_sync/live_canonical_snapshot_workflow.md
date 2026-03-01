# Live-Canonical Snapshot Workflow

## Objective

Seed `paper` and `backtester` from the same live-derived state so replay and parity checks are deterministic and auditable.

## Snapshot Export

Export a v2 init-state snapshot from the live database:

```bash
python tools/export_live_canonical_snapshot.py \
  --source live \
  --output /tmp/live_init_state_v2.json
```

The output includes:

- `balance`
- `positions`
  - for `--as-of-ts` snapshots, position runtime fields (`adds_count`, `tp1_taken`, `last_add_time_ms`) are reconstructed from historical `ADD`/`REDUCE` fills
  - `margin_used` is recalculated from reconstructed `size * entry_price / leverage` so reduced positions carry correct margin headroom
- `runtime.entry_attempt_ms_by_symbol`
- `runtime.exit_attempt_ms_by_symbol`
- canonical metadata (`open_orders`, `cursors`, warnings)

## Backtester Replay Seed

Use the exported file directly with replay:

```bash
cd backtester
./target/release/mei-backtester replay \
  --candles-db ../candles_dbs/candles_1h.db \
  --init-state /tmp/live_init_state_v2.json
```

`bt-core` accepts v1 and v2 init-state schemas. With v2, cooldown markers are restored into runtime state.

## Paper Alignment Notes

This snapshot is the canonical seed artefact for paper/backtester alignment. For paper DB mirroring, continue using `tools/mirror_live_state.py` where needed for OMS table projection.

## Audit Expectations

For each replay/alignment run, record:

- snapshot file path + hash
- source DB path
- replay window (`from_ts`, `to_ts`)
- first divergence event (if any)
- mismatch classification (logic, numeric, state, data, non-simulatable OMS)
