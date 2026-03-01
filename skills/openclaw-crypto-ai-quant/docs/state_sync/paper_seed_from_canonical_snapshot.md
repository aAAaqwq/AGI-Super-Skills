# Paper Seed from Canonical Snapshot

## Objective

Apply a live-canonical snapshot into the paper DB so `PaperTrader.load_state()` reconstructs the same position baseline as the replay seed.

## Export Canonical Snapshot

```bash
python tools/export_live_canonical_snapshot.py \
  --source live \
  --output /tmp/live_init_state_v2.json
```

## Apply Snapshot to Paper DB

```bash
python tools/apply_canonical_snapshot_to_paper.py \
  --snapshot /tmp/live_init_state_v2.json \
  --target-db ./trading_engine.db
```

This performs:

- synthetic `trades` seed rows (`reason=state_sync_seed`)
- balance seed row (`reason=state_sync_balance_seed`)
- `position_state` refresh aligned to seeded open trade IDs
- `runtime_cooldowns` seed (entry/exit cooldown maps from snapshot runtime state)
- optional `oms_open_orders` replacement from snapshot canonical metadata

## Deterministic Replay Pairing

Use the same snapshot as the backtester seed:

```bash
cd backtester
./target/release/mei-backtester replay \
  --candles-db ../candles_dbs/candles_1h.db \
  --init-state /tmp/live_init_state_v2.json
```

With this pairing, paper and backtester start from the same canonical seed artefact.
