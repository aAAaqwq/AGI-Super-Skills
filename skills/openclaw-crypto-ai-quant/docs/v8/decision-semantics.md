# Decision Semantics Contract

This contract defines deterministic expectations for decision timing, missing data handling, and execution assumptions.

## 1) Timestamp normalisation / timezone rules

- Backtester candles are keyed by bar start in **epoch milliseconds** (`i64`).
- `run_simulation` iterates bars in ascending `t` from `build_timeline(candles)` (no additional timestamp coercion in Rust path).
- Entry/exit evaluation happens on each main-bar timestamp and, where provided, on sub-bar ranges.
- Exit sub-bar / entry sub-bar scan windows are interpreted as **`(ts, next_ts]`** in milliseconds.
- Python API time conversion helper (`engine._coerce_ts_ms`) follows these normalisation rules:
  - `datetime` values: naive inputs are interpreted as UTC.
  - ISO strings ending with `Z` are accepted.
  - numeric values are interpreted as epoch seconds unless magnitude implies milliseconds.
  - strings parse via `datetime.fromisoformat` fallback semantics.

## 2) Candle boundary and bar-close semantics

- Per timestamp loop in `run_simulation`:
  1. update indicators for symbols that have a bar at that timestamp,
  2. process exits,
  3. skip entries while warmup (`bar_count < lookback`),
  4. evaluate entry signals.
- Without sub-bars (`exit_candles = None`, `entry_candles = None`): exits and entries occur at indicator-bar boundaries.
- With exit sub-bars: exits are re-evaluated on sub-bars in each indicator bar range to reflect early stop/take-profit hits.
- With entry sub-bars: entries are evaluated per sub-bar, then ranked and executed.
- Final forced closure:
  - at end-of-backtest remaining open positions close at the last known close for that symbol.

## 3) Missing-data / missing-candle handling

- Timeline is a **sorted union of all candle timestamps** across all symbols.
- If a symbol has no bar for a timestamp:
  - no indicator update for that symbol,
  - no signal generation for that symbol in that timestamp,
  - no entry/exit ranking for that symbol.
- There is **no interpolation or synthetic candle fill** for missing bars.
- Missing bars therefore delay that symbol's `bar_count` and may delay when it becomes trade-eligible.

## 4) Indicator warmup and NaN policy

- Indicators are continuously updated on every available bar.
- Entry path applies a global warmup guard (`bar_count < lookback`) before producing candidate entries.
- Exits are evaluated even during warmup.
- Indicator defaults avoid NaN fallbacks by construction in current implementation:
  - RSI returns `50.0` until warmed enough,
  - ATR/ADX/EMA start from seeded values and only become meaningful as their internal windows fill.
- Decisions should be interpreted against this warmup model; indicator snapshots are valid but may be conservative until warmup windows are satisfied.

## 5) Fee, funding, and size/factor assumptions

- Backtester fee rate is fixed at `FEE_RATE = 0.00035` (taker fee) and applied on every executed fill.
- Entry/exit notional is `size * fill_price` and fee is `notional * FEE_RATE`.
- If `notional < cfg.trade.min_notional_usd`:
  - entry is allowed only when `cfg.trade.bump_to_min_notional == true` (size is bumped),
  - otherwise candidate is skipped.
- Size/rounding policy in execution wrappers:
  - `round_size` (engine API helper) rounds **down** to exchange size decimals,
  - `round_size_up` rounds **up**,
  - `min_size_for_notional` returns ceil-rounded size to satisfy minimum notional.
- Funding integration:
  - optional `funding_rates` input,
  - applied only on hourly boundaries crossed by the main-bar loop,
  - sign convention: positive rate is payment by long, rebate to short (`delta = -signed_size * price * rate`).

