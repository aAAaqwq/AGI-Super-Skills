# Worker 4 — End-to-End Config Flow Validation

**Date:** 2026-02-14T22:09Z  
**Scope:** YAML config flow through Rust backtester and Python engine, deep-merge parity, symbol overrides, live section, hot-reload, regime gate keys, tp_partial_atr_mult.

---

## 1. YAML Config Flow Through Each System

### 1.1 Rust Path

```
strategy_overrides.yaml
  → config.rs::load_config(yaml_path, symbol, is_live)
  → YamlRoot { global, symbols, live } parsed by serde_yaml
  → defaults_as_value()  [StrategyConfig::default() → JSON → YAML Value]
  → deep_merge(defaults, global)
  → deep_merge(merged, symbols.<SYMBOL>)   [if symbol given]
  → deep_merge(merged, live)               [if is_live=true]
  → serde_yaml::from_value(merged) → StrategyConfig struct
  → used in engine::run_simulation() and sweep::run_sweep()
```

**Key files:**
- `backtester/crates/bt-core/src/config.rs` — `load_config()`, `deep_merge()`, `StrategyConfig` struct, `YamlRoot`
- `backtester/crates/bt-core/src/sweep.rs` — `apply_overrides()` (sweep axes applied on top of base config)
- `backtester/crates/bt-core/src/engine.rs` — consumes `StrategyConfig`

**Merge hierarchy:** `defaults ← global ← symbols.<SYMBOL> ← live (if is_live)`

### 1.2 Python Path

```
strategy_overrides.yaml
  → mei_alpha_v1._load_strategy_overrides()    [reads YAML with yaml.safe_load()]
  → _STRATEGY_OVERRIDES dict (legacy fallback)
  
  OR (preferred):
  
  → StrategyManager.bootstrap(defaults=_DEFAULT_STRATEGY_CONFIG, yaml_path=...)
  → StrategyManager._load_yaml()              [yaml.safe_load()]
  → stored as self._overrides
  
  Per-call:
  → get_strategy_config(symbol)
    → StrategyManager.get_config(symbol)
      → defaults = copy.deepcopy(_DEFAULT_STRATEGY_CONFIG)
      → deep_merge(cfg, overrides["global"])
      → deep_merge(cfg, overrides["symbols"][SYMBOL])
      → deep_merge(cfg, overrides["live"])     [if mode in {live, dry_live}]
      → deep_merge(cfg, overrides["modes"][mode_key])  [if AI_QUANT_STRATEGY_MODE set]
    → returns merged dict
  → used in engine/core.py (UnifiedEngine) and PaperTrader
```

**Key files:**
- `strategy/mei_alpha_v1.py` — `_DEFAULT_STRATEGY_CONFIG`, `_load_strategy_overrides()`, `get_strategy_config()`, `_deep_merge()`
- `engine/strategy_manager.py` — `StrategyManager.get_config()`, uses `engine.utils.deep_merge()`
- `engine/utils.py` — `deep_merge()` (canonical Python implementation)
- `engine/core.py` — `UnifiedEngine.__init__()` reads `engine:` section from config

**Merge hierarchy:** `defaults ← global ← symbols.<SYMBOL> ← live (if live/dry_live mode) ← modes.<MODE> (if AI_QUANT_STRATEGY_MODE set)`

### 1.3 Flow Comparison

| Aspect | Rust | Python |
|--------|------|--------|
| YAML loader | `serde_yaml` | `yaml.safe_load()` |
| Defaults source | `StrategyConfig::default()` impl blocks | `_DEFAULT_STRATEGY_CONFIG` dict literal |
| Merge order | defaults ← global ← symbol ← live | defaults ← global ← symbol ← live ← modes |
| `modes:` support | ❌ Not supported | ✅ Supported (AQC-1002) |
| Config type | Typed struct (`StrategyConfig`) | Untyped dict |
| Unknown keys | Silently ignored by `#[serde(default)]` | Passed through (dict merge) |

**⚠️ FINDING: Rust does not support `modes:` section.** The `modes:` section in YAML (primary/fallback/conservative/flat) is Python-engine-only. This is intentional (backtester doesn't need runtime mode switching), but the YAML comment should clarify this. Currently the YAML has `modes:` with `global.engine.interval` overrides — these affect engine-only config and are correctly irrelevant to the backtester.

---

## 2. Deep-Merge Logic Equivalence

### 2.1 Rust `deep_merge()` (config.rs lines 525-540)

```rust
fn deep_merge(base: &mut serde_yaml::Value, overlay: &serde_yaml::Value) {
    match (base, overlay) {
        (Value::Mapping(base_map), Value::Mapping(overlay_map)) => {
            for (key, overlay_val) in overlay_map.iter() {
                if let Some(base_val) = base_map.get_mut(key) {
                    deep_merge(base_val, overlay_val);  // recurse
                } else {
                    base_map.insert(key.clone(), overlay_val.clone());  // new key
                }
            }
        }
        (base, overlay) => {
            if !overlay.is_null() {
                *base = overlay.clone();  // scalar/array replacement
            }
        }
    }
}
```

### 2.2 Python `deep_merge()` (engine/utils.py lines 11-24)

```python
def deep_merge(base: dict, override: dict) -> dict:
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)  # recurse
        else:
            base[k] = v  # scalar/list replacement
    return base
```

### 2.3 Legacy `_deep_merge()` (mei_alpha_v1.py lines 471-477)

```python
def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
```

### 2.4 Equivalence Analysis

| Behavior | Rust | Python (utils) | Python (mei_alpha) |
|----------|------|----------------|-------------------|
| Dict + Dict → recurse | ✅ | ✅ | ✅ |
| Scalar replacement | ✅ | ✅ | ✅ |
| Array replacement (not concat) | ✅ | ✅ | ✅ |
| Null overlay → skip | ✅ (explicit null check) | ❌ (None replaces) | ❌ (None replaces) |
| New key insertion | ✅ | ✅ | ✅ |
| In-place mutation | ✅ | ✅ | ✅ |

**⚠️ MINOR DIFFERENCE: Null handling.** Rust skips null overlays (`if !overlay.is_null()`), preserving the base value. Python replaces base with `None` if the override dict has `key: None`. In practice, YAML `key: null` entries are extremely rare in strategy_overrides.yaml (none exist currently), so this difference is benign. However, if someone writes `leverage: null` in YAML, Rust would keep the default while Python would set it to `None` (likely causing a runtime error later).

**✅ VERDICT: Functionally equivalent for all real-world YAML configurations.** The null-handling difference is a theoretical edge case that doesn't affect current configs.

---

## 3. Symbol-Level Override Handling

### 3.1 YAML Structure

The current `config/strategy_overrides.yaml` has only a `global:` section (no `symbols:` section). However, the YAML schema supports:

```yaml
global:
  trade: { ... }
symbols:
  BTC:
    trade: { leverage: 10.0, sl_atr_mult: 1.5 }
  ETH:
    trade: { allocation_pct: 0.10 }
```

### 3.2 Rust Per-Symbol Support

**✅ Fully supported.** `config.rs::load_config()` (lines 567-582):
- Parses `YamlRoot.symbols` as a `serde_yaml::Value`
- Looks up symbol key (exact match then uppercase)
- Deep-merges symbol overrides on top of global

```rust
if let Some(sym) = symbol {
    if let serde_yaml::Value::Mapping(ref symbols_map) = root.symbols {
        let sym_key = serde_yaml::Value::String(sym.to_string());
        let sym_key_upper = serde_yaml::Value::String(sym.to_uppercase());
        let sym_val = symbols_map.get(&sym_key).or_else(|| symbols_map.get(&sym_key_upper));
        if let Some(sym_overrides) = sym_val {
            deep_merge(&mut merged, sym_overrides);
        }
    }
}
```

Unit tests confirm this works: `test_load_yaml_symbol_override()` and `test_full_merge_hierarchy()`.

### 3.3 Python Per-Symbol Support

**✅ Fully supported.** `strategy_manager.py::get_config()`:

```python
deep_merge(cfg, (overrides.get("symbols") or {}).get(sym) or {})
```

And in legacy path (`mei_alpha_v1.py::get_strategy_config()`):

```python
_deep_merge(cfg, (overrides.get("symbols") or {}).get(symbol) or {})
```

### 3.4 Parity

**✅ Both systems handle per-symbol overrides identically:** `defaults ← global ← symbols.BTC`. The Rust side has a case-insensitive fallback (tries exact then `.to_uppercase()`), while Python normalizes to `.upper()` before lookup — effectively the same behavior.

---

## 4. `live:` Section Handling

### 4.1 Current State

The YAML file explicitly states:
```yaml
# No `live:` section — live engine uses identical global config as backtester.
# What you replay = what you trade.
```

No `live:` section exists in any of the config files (`strategy_overrides.yaml`, `strategy_overrides.paper1.yaml`, etc.).

### 4.2 Rust Backtester Handling

**✅ Correctly ignores `live:` when `is_live=false`.** In `config.rs::load_config()`:

```rust
if is_live && !root.live.is_null() {
    deep_merge(&mut merged, &root.live);
}
```

The `bt-cli` binary and sweep runner call `load_config(yaml_path, symbol, false)` — the `is_live` parameter is always `false` for backtesting. The live layer is only applied when explicitly requested.

### 4.3 Python Engine Handling

**✅ Correctly applies `live:` only for live/dry_live modes.** In `strategy_manager.py::get_config()`:

```python
mode = str(os.getenv("AI_QUANT_MODE", "paper")).strip().lower()
if mode in {"live", "dry_live"}:
    live_over = overrides.get("live") or {}
    ...
```

Paper mode (default) skips the live overlay entirely.

### 4.4 Verdict

**✅ The `live:` section is correctly mode-gated in both systems.** Since the current YAML has no `live:` section, this is a no-op in practice but the code is ready for when live-specific overrides are needed.

---

## 5. Hot-Reload Mechanism

### 5.1 Python Engine Hot-Reload

**✅ StrategyManager watches file mtime.** In `strategy_manager.py::_load_if_needed()`:

```python
yaml_mtime = file_mtime(self._yaml_path)
...
yaml_needs_reload = yaml_mtime > self._yaml_mtime
```

Called from:
1. `StrategyManager.maybe_reload()` — invoked every engine loop iteration
2. `StrategyManager.get_config(symbol)` — also calls `_load_if_needed()`

The reload is **per-config-request**: every call to `get_strategy_config(symbol)` triggers a mtime check. If the file changed, YAML is re-parsed and stored.

### 5.2 What Gets Reloaded

All ~142+ strategy axes in the YAML `global:` section are reloaded because the entire file is re-parsed with `yaml.safe_load()` and stored as `self._overrides`. Every subsequent `get_config(symbol)` call rebuilds the merged dict from scratch: `defaults ← new_overrides.global ← new_overrides.symbols.SYM`.

**Notable exceptions (NOT hot-reloadable):**
- `engine.interval` — WS subscriptions are tied to this; requires daemon restart
- Any Python module-level constants (e.g., `INTERVAL`, `LOOKBACK_HOURS`) — set at import time

**Hot-reloadable (confirmed in `engine/core.py::_refresh_engine_config()`):**
- `engine.entry_interval`
- `engine.exit_interval`

### 5.3 Rust Backtester

**N/A** — the backtester loads the YAML once at startup via `load_config()` and doesn't hot-reload (it's a batch process that runs to completion).

### 5.4 Verdict

**✅ Python engine hot-reloads all 142+ axes via file mtime on every loop iteration.** The reload is thread-safe (uses `threading.RLock`). The strategy_manager.py StrategySnapshot tracks `overrides_sha1` for change detection in audit logs.

---

## 6. `market_regime.regime_gate_*` Keys

### 6.1 The 6 Keys

From `strategy_overrides.yaml` under `global.market_regime`:

| Key | Default | Description |
|-----|---------|-------------|
| `enable_regime_gate` | `false` | Master switch for global entry blocking |
| `regime_gate_breadth_low` | `20.0` | Breadth chop zone lower bound |
| `regime_gate_breadth_high` | `80.0` | Breadth chop zone upper bound |
| `regime_gate_btc_adx_min` | `20.0` | BTC ADX minimum for trend OK |
| `regime_gate_btc_atr_pct_min` | `0.003` | BTC ATR% minimum for trend OK |
| `regime_gate_fail_open` | `false` | Behavior when metrics are missing |

### 6.2 Python Engine Usage — ✅ PRESENT AND USED

All 6 keys are actively used in `engine/core.py::_update_regime_gate()` (lines 1201-1367):

```python
enabled = bool(rc.get("enable_regime_gate", False))
fail_open = bool(rc.get("regime_gate_fail_open", False))
chop_lo = float(rc.get("regime_gate_breadth_low", ...))
chop_hi = float(rc.get("regime_gate_breadth_high", ...))
btc_adx_min = float(rc.get("regime_gate_btc_adx_min", 20.0))
btc_atr_pct_min = float(rc.get("regime_gate_btc_atr_pct_min", 0.003))
```

The regime gate logic:
1. Computes market breadth % (% of watchlist with bullish EMA alignment)
2. If breadth is inside [low, high] → gate OFF (chop regime, block entries)
3. If breadth is outside → check BTC ADX and BTC ATR%
4. If BTC ADX ≥ min AND BTC ATR% ≥ min → gate ON (trend OK, entries allowed)
5. Otherwise → gate OFF

When gate is OFF, entries are blocked but exits still run.

### 6.3 Rust Backtester — ❌ COMPLETELY ABSENT

**Confirmed: zero references to `regime_gate` in any Rust source files.**

```bash
$ grep -rn "regime_gate" backtester/crates/ --include="*.rs"
(no output)
```

The Rust `MarketRegimeConfig` struct (config.rs lines 300-311) contains only:
- `enable_regime_filter`
- `breadth_block_short_above`
- `breadth_block_long_below`
- `enable_auto_reverse`
- `auto_reverse_breadth_low`
- `auto_reverse_breadth_high`

The `regime_gate_*` keys are in the YAML and Python defaults but absent from the Rust struct. Since serde uses `#[serde(default)]`, these keys are silently ignored during YAML deserialization — no error, but no effect.

### 6.4 Should They Be in the Sweep?

**Analysis:**

The regime gate is a **cross-symbol, market-wide filter** that requires:
- Real-time market breadth computation (% of symbols bullish)
- BTC-specific ADX and ATR% from live/streaming data

The backtester runs per-symbol simulations. To simulate the regime gate, it would need:
1. Multi-symbol candle data loaded simultaneously
2. Per-bar breadth computation across the entire universe
3. BTC indicator computation in parallel

**Current backtester architecture:** runs simulations per-symbol independently (see `sweep.rs::run_sweep()` — each combo runs `engine::run_simulation` which processes one set of candle data). The engine has BTC alignment support (via `require_btc_alignment` filter and BTC candle data), but breadth requires ALL symbols.

**Recommendation:** 
- **Not suitable for the 144v sweep as-is.** The sweep tests single-parameter sensitivity; adding regime gate would require architectural changes.
- **Could be added as a separate multi-symbol backtest mode** if breadth data were precomputed and stored alongside candle data.
- The 6 regime gate params could theoretically be swept IF breadth were treated as an external input timeseries (similar to how funding rates are loaded). This would be a significant enhancement.

---

## 7. `trade.tp_partial_atr_mult` Analysis

### 7.1 Rust Backtester — ✅ FULLY IMPLEMENTED

**Config:** `config.rs` — `TradeConfig.tp_partial_atr_mult: f64` (default `0.0`)

**Logic:** `backtester/crates/bt-core/src/exits/take_profit.rs` (lines 53-108):
- When `tp_partial_atr_mult > 0`: partial TP fires at a **separate, closer level** (`entry ± atr × tp_partial_atr_mult`)
- When `tp_partial_atr_mult == 0`: partial TP fires at the same level as full TP (`tp_atr_mult`)
- After partial TP taken, if `tp_partial_atr_mult > 0`, the full TP at `tp_atr_mult` remains active for the remainder

**Sweep support:** `sweep.rs` line 143: `"trade.tp_partial_atr_mult" => cfg.trade.tp_partial_atr_mult = value`

Comprehensive unit tests exist: `test_partial_tp_separate_level_hold_before_hit`, `test_partial_tp_separate_level_reduce_at_hit`, etc.

### 7.2 Python Engine — ✅ FULLY IMPLEMENTED

**Config:** `mei_alpha_v1.py` line 284: `"tp_partial_atr_mult": 0.0`

**Logic:** `mei_alpha_v1.py` lines 2929-2932 and 3350-3469:
```python
tp_partial_atr_mult_val = float(trade_cfg.get("tp_partial_atr_mult", 0))
if tp_partial_atr_mult_val > 0 and tp1_taken == 0:
    tp_check_price = entry + (atr * tp_partial_atr_mult_val) if pos_type == 'LONG' else entry - (atr * tp_partial_atr_mult_val)
```

Identical semantics: 0 = same level as full TP, >0 = separate partial TP level.

### 7.3 In the 144v Sweep? — ❌ NOT INCLUDED

Scanning `backtester/sweeps/full_144v.yaml`: **`tp_partial_atr_mult` is NOT listed as a sweep axis.**

The sweep includes related partial TP axes:
- `trade.tp_partial_pct` (3 values: 0.35, 0.5, 0.65)
- `trade.tp_partial_min_notional_usd` (3 values: 7.0, 10.0, 13.0)
- `trade.enable_partial_tp` (toggle)
- `trade.tp_atr_mult` (11 values: 3.0–8.0)

But `tp_partial_atr_mult` itself is missing.

### 7.4 Should It Be Added?

**Yes.** `tp_partial_atr_mult` materially changes trade behavior:
- At `0.0` (current default): partial TP only fires at the full TP level, making it essentially the same as a full close with reduced size
- At `1.0` (current YAML override): partial TP fires much sooner (at 1×ATR vs 6×ATR for full TP), locking in early profits while leaving a runner

The YAML currently sets it to `1.0` (swept v6.100), suggesting it's already been identified as impactful. Adding it to the 144v sweep would validate whether the current value is optimal or if alternatives (e.g., 0.5, 1.5, 2.0, 3.0) perform better.

**Recommended sweep values:** `[0.0, 0.5, 1.0, 1.5, 2.0, 3.0]`

This would bring the sweep to **145 axes** (or replace one of the less sensitive axes to stay at 144).

---

## Summary of Findings

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Config flow through Rust | ✅ PASS | `load_config()` → deep-merge → typed struct |
| 1 | Config flow through Python | ✅ PASS | StrategyManager → deep-merge → untyped dict |
| 2 | Deep-merge equivalence | ✅ PASS (practical) | Minor null-handling difference (benign) |
| 3 | Symbol-level overrides | ✅ PASS | Both systems support `symbols:` with identical merge |
| 4 | `live:` section handling | ✅ PASS | Both correctly gate on mode; no live section in current YAML |
| 5 | Hot-reload | ✅ PASS | Python reloads all axes via mtime; Rust is batch (N/A) |
| 6 | `regime_gate_*` in Python | ✅ USED | 6 keys actively used in `_update_regime_gate()` |
| 6 | `regime_gate_*` in Rust | ❌ ABSENT | Not in struct, silently ignored |
| 6 | `regime_gate_*` in sweep | ❌ N/A | Requires multi-symbol breadth — not suitable for current sweep arch |
| 7 | `tp_partial_atr_mult` Rust | ✅ IMPLEMENTED | Used in take_profit.rs, sweepable via sweep.rs |
| 7 | `tp_partial_atr_mult` Python | ✅ IMPLEMENTED | Used in mei_alpha_v1.py exit logic |
| 7 | `tp_partial_atr_mult` in 144v | ⚠️ MISSING | Should be added — materially impacts trade behavior |

### Action Items

1. **Low priority:** Add YAML comment clarifying `modes:` section is Python-engine-only
2. **Low priority:** Consider adding null-guard to Python `deep_merge()` to match Rust behavior
3. **Medium priority:** Add `trade.tp_partial_atr_mult` to the 144v sweep (recommended values: `[0.0, 0.5, 1.0, 1.5, 2.0, 3.0]`)
4. **Future:** If regime gate proves valuable in live trading, consider adding breadth as a precomputed timeseries for backtester simulation
