# Worker 5 — Regime Gate & Missing Axis Resolution

**Auditor:** worker5-gap-resolution (subagent)  
**Date:** 2026-02-14  
**Scope:** Regime gate keys, `tp_partial_atr_mult`, `use_bbo_for_fills`, `ave_avg_atr_window` alias

---

## 1. Regime Gate Audit (6 Keys)

All six keys live **exclusively** in the Python engine layer. They are **not** present in Rust `config.rs` or `sweep.rs`.

### 1.1 `market_regime.enable_regime_gate`

| Aspect | Finding |
|---|---|
| **Python default** | `strategy/mei_alpha_v1.py:373` — `False` |
| **Engine usage** | `engine/core.py:1231` — `bool(rc.get("enable_regime_gate", False))`. When `False`, the gate is unconditionally ON (entries allowed). |
| **Rust presence** | ❌ Not in `config.rs` or `sweep.rs` |
| **Data needs** | Boolean toggle — no external data required |
| **Recommendation** | **Keep engine-only**. This is a master switch that controls whether the gate logic runs at all. In backtesting, the regime gate concept doesn't apply because the backtester doesn't have the same multi-symbol breadth context. Document as engine-only. |

### 1.2 `market_regime.regime_gate_breadth_high`

| Aspect | Finding |
|---|---|
| **Python default** | `mei_alpha_v1.py:375` — `80.0` |
| **Engine usage** | `core.py:1244` — upper bound of breadth chop zone. Breadth inside `[low, high]` → gate OFF (chop). Falls back to `auto_reverse_breadth_high` if not set. |
| **Rust presence** | ❌ Not in `config.rs` or `sweep.rs` |
| **Data needs** | Requires `_market_breadth_pct` — computed at `core.py:1706–1724` from cached EMA fast/slow alignment across the **full watchlist**. This is a **cross-asset aggregate** derived from live analysis cache. |
| **Could backtester simulate?** | **Theoretically yes** if all watchlist symbols' candle data were loaded simultaneously and EMA alignment computed per bar. However, the backtester currently runs **single-symbol** simulations; it has no multi-symbol breadth concept. Adding this would require a fundamentally different architecture (portfolio-level backtesting). |
| **Recommendation** | **Keep engine-only**. Document that breadth is a cross-asset live metric unavailable to the single-symbol backtester. |

### 1.3 `market_regime.regime_gate_breadth_low`

| Aspect | Finding |
|---|---|
| **Python default** | `mei_alpha_v1.py:374` — `20.0` |
| **Engine usage** | `core.py:1240` — lower bound of breadth chop zone. Falls back to `auto_reverse_breadth_low`. |
| **Rust presence** | ❌ Not in `config.rs` or `sweep.rs` |
| **Data needs** | Same as `breadth_high` — requires live cross-asset breadth. |
| **Recommendation** | **Keep engine-only**. Same rationale as `breadth_high`. |

### 1.4 `market_regime.regime_gate_btc_adx_min`

| Aspect | Finding |
|---|---|
| **Python default** | `mei_alpha_v1.py:376` — `20.0` |
| **Engine usage** | `core.py:1249,1337` — minimum BTC ADX for the gate to stay ON. Below this → gate OFF (`btc_adx_low`). Uses cached BTC analysis or computes ADX on-the-fly from BTC candle DataFrame. |
| **Rust presence** | ❌ Not in `config.rs` or `sweep.rs` |
| **Data needs** | BTC ADX — derivable from historical BTC candle data. |
| **Could backtester simulate?** | **Partially**. The backtester could compute BTC ADX if BTC candles were loaded alongside the target symbol. However, this would require a "reference symbol" data feed, which isn't currently supported. The single-symbol architecture makes this non-trivial. |
| **Recommendation** | **Keep engine-only for now**. If portfolio backtesting is ever added, this could be migrated. Document as engine-only with a note that the underlying metric (BTC ADX) is technically computable from historical data. |

### 1.5 `market_regime.regime_gate_btc_atr_pct_min`

| Aspect | Finding |
|---|---|
| **Python default** | `mei_alpha_v1.py:377` — `0.003` |
| **Engine usage** | `core.py:1253,1340` — minimum BTC ATR% for the gate to stay ON. Below this → gate OFF (`btc_atr_low`). |
| **Rust presence** | ❌ Not in `config.rs` or `sweep.rs` |
| **Data needs** | BTC ATR / close ratio — derivable from historical BTC candles. |
| **Could backtester simulate?** | Same as `btc_adx_min` — possible with a reference symbol feed. |
| **Recommendation** | **Keep engine-only**. Same rationale as `btc_adx_min`. |

### 1.6 `market_regime.regime_gate_fail_open`

| Aspect | Finding |
|---|---|
| **Python default** | `mei_alpha_v1.py:378` — `False` |
| **Engine usage** | `core.py:1232` — controls behaviour when breadth or BTC metrics are unavailable. `True` → gate stays ON (entries allowed); `False` → gate goes OFF (entries blocked). |
| **Rust presence** | ❌ Not in `config.rs` or `sweep.rs` |
| **Data needs** | Boolean policy toggle — no external data. |
| **Recommendation** | **Keep engine-only**. Pure policy setting for missing-data handling. |

### Regime Gate — Critical Observation

⚠️ **The regime gate state (`_regime_gate_on`) is computed and logged but never actually enforced for entry blocking.** The flag is set at `core.py:1347` and reported in heartbeat logs at `core.py:2084`, but there is **no code path** that checks `self._regime_gate_on` to skip or reject OPEN/ADD decisions. The entry execution flow at `core.py:1972` calls `_decision_execute_trade` unconditionally for OPEN/ADD actions.

This means `enable_regime_gate=True` will log gate state changes but **will not actually block entries**. This appears to be a **WIP/incomplete feature** — the gate computation logic is fully implemented but the enforcement hook is missing.

**Action item:** Wire `self._regime_gate_on` into the OPEN/ADD path (e.g., around `core.py:1928`) to actually block entries when the gate is OFF.

---

## 2. `trade.tp_partial_atr_mult` Gap

### Findings

| Layer | Status | Location |
|---|---|---|
| **Rust config** | ✅ Present | `config.rs:75` — `pub tp_partial_atr_mult: f64`, default `0.0` at line 179 |
| **Rust sweep** | ✅ Match arm present | `sweep.rs:143` — `"trade.tp_partial_atr_mult" => cfg.trade.tp_partial_atr_mult = value` |
| **Rust backtester simulation** | ✅ **Actively used** | `exits/take_profit.rs:53–108` — full partial TP logic with 8 unit tests (lines 261–340). When `> 0`, fires a separate closer partial TP level; when `== 0`, partial == full (legacy behaviour). |
| **Python strategy** | ✅ **Actively used** | `mei_alpha_v1.py:284` (default `0.0`), `mei_alpha_v1.py:2929–2932` (entry calc), `mei_alpha_v1.py:3350–3353,3469` (exit logic) |
| **`full_144v.yaml`** | ❌ **Missing** | Only `trade.tp_partial_min_notional_usd` (line 731) and `trade.tp_partial_pct` (line 736) are swept. `tp_partial_atr_mult` is absent. |

### Analysis

`tp_partial_atr_mult` is fully implemented and actively used in **both** Python and Rust. It controls where the partial take-profit level fires relative to ATR. The backtester has comprehensive test coverage. However, it's **not included in the sweep grid**, meaning optimisation never explores this axis.

### Recommendation

**Add to `full_144v.yaml`** with range:

```yaml
- path: trade.tp_partial_atr_mult
  values:
  - 0.0    # disabled (legacy: partial == full TP)
  - 2.0    # closer partial TP
  - 3.0    # moderate partial TP
  - 4.0    # wider partial TP
```

Place adjacent to existing `tp_partial_pct` / `tp_partial_min_notional_usd` entries (after line 739). Range should be below `tp_atr_mult` (typically 5.0–8.0) since partial TP is meant to fire earlier.

---

## 3. `trade.use_bbo_for_fills` Gap

### Findings

| Layer | Status | Location |
|---|---|---|
| **Python default** | `mei_alpha_v1.py:258` — `True` |
| **Python usage** | `mei_alpha_v1.py:812–827,1887–1889,2017,2098,2224,2233,2566,2639` — queries `hyperliquid_ws.hl_ws.get_bbo(sym, max_age_s=15.0)` for live best-bid/offer to improve fill pricing. Uses BBO mid as mark price when available. |
| **Rust config** | `config.rs:45` — `pub use_bbo_for_fills: bool`, default `true` at line 153 |
| **Rust sweep** | `sweep.rs:121` — match arm present |
| **Rust backtester usage** | ❌ **Not used in simulation logic**. Present in config struct and sweep parser, but `grep` across all `bt-core/src/*.rs` (excluding config/sweep) returns **zero hits**. The field is defined but never read by any backtester engine or exit module. |

### Analysis

`use_bbo_for_fills` is an **engine-only runtime feature** that requires a **live WebSocket orderbook feed** (`hyperliquid_ws`). The backtester cannot simulate BBO because:

1. **No orderbook data**: Historical OHLCV candles don't include bid/ask spread information.
2. **Exchange-specific**: BBO data comes from Hyperliquid's real-time WebSocket stream.
3. **Staleness logic**: The engine has BBO age checks (`bbo_age_s`, `core.py:976–995`) that are inherently live concepts.

The Rust config/sweep presence is vestigial — the field exists in the struct but the backtester simulation ignores it entirely.

### Recommendation

**Document as engine-only exclusion.** Do **not** add to sweep grids. The Rust config field can remain for schema completeness (avoids unknown-key warnings if configs are shared), but sweeping it would be meaningless since the backtester ignores the value.

**Exclusion reason:** Requires live orderbook (BBO) data from exchange WebSocket. Not simulatable from historical OHLCV candles. Backtester uses candle close/OHLC for fill pricing regardless of this flag.

---

## 4. `indicators.ave_avg_atr_window` Alias

### Findings

#### Alias Logic in `sweep.rs`

```rust
// sweep.rs:103-105
fn set_ave_avg_atr_window(cfg: &mut StrategyConfig, window: usize) {
    cfg.thresholds.entry.ave_avg_atr_window = window;
    cfg.indicators.ave_avg_atr_window = window;
}

// sweep.rs:203
"thresholds.entry.ave_avg_atr_window" => set_ave_avg_atr_window(cfg, value as usize),
// sweep.rs:297
"indicators.ave_avg_atr_window" => set_ave_avg_atr_window(cfg, value as usize),
```

**Both paths** (`indicators.ave_avg_atr_window` and `thresholds.entry.ave_avg_atr_window`) call the **same** `set_ave_avg_atr_window` function, which writes to **both** config locations atomically.

#### Config Structure

In `config.rs`, the field exists in **two** places:
- `config.rs:250` — `IndicatorConfig.ave_avg_atr_window` (default 50)
- `config.rs:357` — `EntryThresholds.ave_avg_atr_window` (default 50)

The canonical read path is `config.rs:582-584`:
```rust
pub fn effective_ave_avg_atr_window(&self) -> usize {
    self.thresholds.entry.ave_avg_atr_window  // thresholds.entry is the SSOT
}
```

This is used by `engine.rs:287` to create the indicator bank.

#### Test Coverage

Two dedicated tests in `sweep.rs:503-523`:
1. **`test_ave_avg_atr_window_sync_via_indicators`** (line 503): Sets different initial values (indicators=13, thresholds=21), applies override via `indicators.ave_avg_atr_window=77`, asserts both become 77. ✅
2. **`test_ave_avg_atr_window_sync_via_thresholds`** (line 516): Sets different initials (indicators=9, thresholds=15), applies via `thresholds.entry.ave_avg_atr_window=31`, asserts both become 31. ✅

An additional test in `config.rs:988-990` verifies `effective_ave_avg_atr_window()` returns the thresholds value.

#### Sync Bug Analysis

**No sync bugs found.** The alias design is correct:
- Write via either path → both fields updated atomically
- Read always goes through `effective_ave_avg_atr_window()` → `thresholds.entry` (SSOT)
- Tests cover both write directions
- The only theoretical risk would be direct field writes bypassing `set_ave_avg_atr_window`, but the sweep system is the only external write path and it always uses the sync function

**One minor note:** If someone constructs a `StrategyConfig` manually (not via sweep) and sets only `indicators.ave_avg_atr_window`, the `thresholds.entry` value won't be updated. This is safe because `effective_ave_avg_atr_window()` reads from thresholds (which keeps its default of 50), and the sweep/YAML path always goes through the sync function. No production code path creates this inconsistency.

---

## Summary Table

| Key / Feature | In Python | In Rust | In Sweep Grid | Recommendation |
|---|---|---|---|---|
| `enable_regime_gate` | ✅ defaults + engine | ❌ | N/A | Engine-only. **Fix: wire enforcement hook.** |
| `regime_gate_breadth_high` | ✅ defaults + engine | ❌ | N/A | Engine-only (needs cross-asset breadth) |
| `regime_gate_breadth_low` | ✅ defaults + engine | ❌ | N/A | Engine-only (needs cross-asset breadth) |
| `regime_gate_btc_adx_min` | ✅ defaults + engine | ❌ | N/A | Engine-only (needs BTC reference feed) |
| `regime_gate_btc_atr_pct_min` | ✅ defaults + engine | ❌ | N/A | Engine-only (needs BTC reference feed) |
| `regime_gate_fail_open` | ✅ defaults + engine | ❌ | N/A | Engine-only (policy toggle) |
| `tp_partial_atr_mult` | ✅ both | ✅ config + sweep + simulation | ❌ **Missing** | **Add to `full_144v.yaml`** |
| `use_bbo_for_fills` | ✅ live | ✅ config + sweep (vestigial) | N/A | Engine-only (needs live orderbook) |
| `ave_avg_atr_window` alias | N/A | ✅ Correct, tested | ✅ | No bugs. Both paths sync correctly. |

---

## Action Items

1. **P1 — Wire regime gate enforcement**: Add `if not self._regime_gate_on: continue` (or skip OPEN/ADD) in the engine entry path around `core.py:1928`. Currently the gate computes but never blocks.
2. **P2 — Add `tp_partial_atr_mult` to `full_144v.yaml`**: Values `[0.0, 2.0, 3.0, 4.0]` after the existing `tp_partial_pct` entry.
3. **P3 — Document exclusions**: Add a `docs/backtester_exclusions.md` listing engine-only keys (regime gate × 6, `use_bbo_for_fills`) with reasons.
