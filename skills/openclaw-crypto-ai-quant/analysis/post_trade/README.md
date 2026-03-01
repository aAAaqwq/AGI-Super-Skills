# Post-Trade Analytics (AQC-905)

This folder contains a small, reproducible analysis pack for reviewing strategy behaviour from:

- a trade-level CSV export (MAE/MFE, exit reason codes, symbol contribution)
- a structured events JSONL (entry skips/opens and other audit breadcrumbs)

## 1. Generate Inputs

### Trade CSV (recommended: backtester replay)

```bash
mei-backtester replay \
  --config config/strategy_overrides.yaml \
  --interval 1h \
  --export-trades /tmp/trades.csv
```

### Events JSONL (engine)

By default, the engine writes events to:

- `artifacts/events/events.jsonl`

Override via:

- `AI_QUANT_EVENT_LOG_PATH`
- `AI_QUANT_EVENT_LOG_DIR`

## 2. Build The Analytics Pack

```bash
python tools/post_trade_analytics.py \
  --trades-csv /tmp/trades.csv
```

Outputs are written under `artifacts/analytics/post_trade_<timestamp>/`.

To run trade-only (no events):

```bash
python tools/post_trade_analytics.py \
  --trades-csv /tmp/trades.csv \
  --no-events
```

## 3. What You Get

- `trade_summary.json`: headline totals (P&L, fees, net win rate).
- `mae_mfe_summary.json`: MAE/MFE quantiles.
- `pnl_by_symbol.csv`: symbol contribution summary.
- `reason_code_stats.csv`: exit reason-code breakdown.
- `entry_event_counts.csv`: counts of `ENTRY_*` audit events from JSONL.
- `entry_event_counts_by_symbol.csv`: entry event counts split by symbol.

