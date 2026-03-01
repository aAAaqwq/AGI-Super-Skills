# Plan: 142-Axis SSOT Validation & Profile Upgrade

**Date:** 2026-02-14
**Author:** Mei (AI) + WJEN
**Status:** Complete — validation results in `docs/validation/`

---

## 1. Objective

Ensure all 142 sweepable axes behave correctly and identically across:
- **Rust backtester** (GPU sweep / TPE)
- **Rust backtester** (CPU replay)
- **Python engine** (live/paper daemon)
- **YAML config** (strategy_overrides.yaml — the SSOT)
- **Sweep specs** (full_144v.yaml)

Then update factory profiles to use GPU-only with proper trial counts and 20→3 candidate promotion.

---

## 2. Current State (Audit Summary)

| Layer | Count | Source |
|---|---|---|
| YAML config keys (excl engine/watchlist) | **149** | `config/strategy_overrides.yaml` |
| Rust `sweep.rs::apply_one` match arms | **144** | `backtester/crates/bt-core/src/sweep.rs` |
| 144v sweep spec axes | **142** | `backtester/sweeps/full_144v.yaml` |

### Known Gaps (pre-validation)

| Gap | Keys | Severity | Notes |
|---|---|---|---|
| In YAML config but NOT in Rust sweep | 6 `market_regime.regime_gate_*` | **HIGH** — Python engine uses these but Rust backtester ignores them | Regime gate is engine-only (live data dependency) — may be intentional but needs explicit documentation |
| In YAML config but NOT in 144v sweep | `trade.tp_partial_atr_mult` | **MEDIUM** — sweepable in Rust (has match arm) but not swept | Should be added to 144v or documented as locked |
| In YAML config but NOT in 144v sweep | `trade.use_bbo_for_fills` | **LOW** — engine-only (orderbook), backtester has no BBO data | Intentional exclusion, document |
| Legacy alias | `indicators.ave_avg_atr_window` | **INFO** — Rust alias for `thresholds.entry.ave_avg_atr_window` | Both paths work; sync is handled in `set_ave_avg_atr_window()` |

---

## 3. Validation Plan

### Phase A: Axis-Level SSOT Parity (Sub-agent tasks)

For **each** of the 142 axes in `full_144v.yaml`, validate:

#### A1. Rust Sweep Path Resolution
- [ ] Every axis `path` in `full_144v.yaml` has a matching `match` arm in `sweep.rs::apply_one`
- [ ] No path silently falls through to the `_ => eprintln!` catch-all
- [ ] **Test:** Run existing sweep.rs unit tests (`test_apply_overrides_*`)
- [ ] **New test:** Programmatically apply every 144v axis path and verify the target field changes

#### A2. Rust Config Struct Coverage
- [ ] Every axis maps to a real field in `StrategyConfig` (not silently ignored)
- [ ] Boolean axes (`0.0/1.0`) use `value != 0.0` correctly
- [ ] Enum axes (Confidence, MacdMode) decode correctly: 0→Low/Accel, 1→Medium/Sign, 2→High/None
- [ ] Integer axes (`as usize`) don't truncate unexpected values

#### A3. Python Engine Parity
- [ ] Every axis has a corresponding key in `mei_alpha_v1.py` default config dict
- [ ] `get_strategy_config(symbol)` returns the axis value from YAML correctly
- [ ] The engine actually **reads and uses** each axis value (not just stores it)
- [ ] Type handling matches Rust: booleans, ints, floats consistent

#### A4. YAML ↔ Rust Default Parity
- [ ] For each axis: `StrategyConfig::default()` in Rust == hardcoded default in `mei_alpha_v1.py`
- [ ] When YAML is loaded, both Rust and Python produce the same effective config
- [ ] Deep-merge logic in Rust (`deep_merge`) and Python (`_deep_merge`) are semantically identical

#### A5. Replay Equivalence
- [ ] CPU replay with a known config produces identical PnL to GPU sweep for the same config
- [ ] `_REPLAY_EQUIVALENCE_MODES = ("live", "paper", "backtest")` — paper mode replay matches

### Phase B: Gap Resolution

#### B1. Regime Gate (6 keys)
- [ ] Confirm these are engine-only (require live market breadth data)
- [ ] If backtester should simulate regime gate → add to Rust `StrategyConfig` + `sweep.rs`
- [ ] If intentionally engine-only → add to `full_144v.yaml` header as documented exclusions
- [ ] Add unit test asserting these 6 keys are NOT in sweep spec (so future devs don't wonder)

#### B2. `trade.tp_partial_atr_mult`
- [ ] Rust has the match arm already — add to `full_144v.yaml` with appropriate values
- [ ] Or document as locked if the param is deprecated

#### B3. `trade.use_bbo_for_fills`
- [ ] Confirm backtester has no BBO/orderbook simulation
- [ ] Document exclusion in sweep spec header

### Phase C: Profile & Candidate Promotion Upgrade

#### C1. Profile Defaults (GPU-only, no CPU fallback)

```python
PROFILE_DEFAULTS = {
    "smoke": {
        "tpe_trials": 2_000,
        "num_candidates": 2,
        "shortlist_per_mode": 3,
        "shortlist_max_rank": 20,
    },
    "daily": {
        "tpe_trials": 200_000,       # ~1hr on GPU w/ batch=4096
        "num_candidates": 5,          # legacy fallback
        "shortlist_per_mode": 20,     # 20 candidates total (across modes)
        "shortlist_max_rank": 150,
    },
    "weekly": {                       # NEW — rename "deep" to "weekly"
        "tpe_trials": 2_000_000,      # ~4-8hr on GPU w/ batch=4096
        "num_candidates": 10,
        "shortlist_per_mode": 30,
        "shortlist_max_rank": 400,
    },
}
```

**Trial count rationale (142 axes):**
- daily 200K → ~1,408 samples/axis (TPE guided, sufficient for primary basin)
- weekly 2M → ~14,084 samples/axis (good interaction coverage)

#### C2. Candidate Pipeline: 20 → 3 Promotion

Current flow: sweep → shortlist → replay → done.

New flow:
```
GPU TPE sweep (142 axes)
    → generate 20 candidates (shortlist dedup across modes)
    → CPU replay all 20 (full validation: walk-forward + slippage stress)
    → score & rank 20 candidates
    → promote top 3 to paper:
        1. PRIMARY    — best balanced score (PnL × drawdown × profit factor)
        2. FALLBACK   — best drawdown-adjusted score (conservative but profitable)
        3. CONSERVATIVE — lowest max-drawdown, positive PnL required
```

Implementation:
- [ ] Add `--promote-count` CLI arg (default 3)
- [ ] Add `--promote-roles` arg (default: `primary,fallback,conservative`)
- [ ] Define scoring functions for each role
- [ ] Output `promoted_configs/` directory with `primary.yaml`, `fallback.yaml`, `conservative.yaml`
- [ ] Paper daemon reads from `promoted_configs/` with role-based fallback

#### C3. Keep "deep" as alias for "weekly"

```python
# Backward compat
if profile == "deep":
    profile = "weekly"
```

---

## 4. Validation Execution Plan (Sub-agents)

### Worker 1: Rust Axis Parity
- Extract all 144 match arms from `sweep.rs`
- Cross-reference against all 142 `full_144v.yaml` paths
- Verify each axis actually mutates the correct `StrategyConfig` field
- Run existing Rust sweep tests
- Write a new Rust test: apply each 144v axis, assert field changed

### Worker 2: Python ↔ Rust Default Parity
- Extract Python defaults from `mei_alpha_v1.py`
- Extract Rust defaults from `StrategyConfig::default()`
- Diff every field — flag mismatches
- Check type handling (bool/int/float/enum) consistency

### Worker 3: Python Engine Usage Audit
- For each of the 142 axes, grep the engine code to confirm it's actually read
- Flag any "dead" axes (defined in config but never used in decision logic)
- Check that YAML hot-reload picks up all axes

### Worker 4: End-to-End Config Flow Test
- Write a test YAML with known non-default values for all 142 axes
- Load it in Rust backtester → dump effective config
- Load it in Python engine → dump effective config
- Diff the two → must be identical (excluding engine-only keys)

### Worker 5: Regime Gate & Missing Axis Resolution
- Audit the 6 regime gate keys
- Decide: add to Rust or document as engine-only
- Handle `trade.tp_partial_atr_mult` gap
- Update `full_144v.yaml` and docs

---

## 5. Acceptance Criteria

- [ ] **Zero unknown-path warnings** when running 144v sweep spec through Rust
- [ ] **Zero default mismatches** between Rust and Python for all 142 shared axes
- [ ] **All 142 axes have engine usage** (or are documented as sweep-only/deprecated)
- [ ] **Profile defaults updated** in `factory_run.py`
- [ ] **20→3 promotion logic** implemented and tested
- [ ] **All existing tests pass** (179 pass, 0 fail)
- [ ] **New parity tests added** (Rust + Python cross-validation)
- [ ] **Documentation updated**: sweep spec header, SSOT doc

---

## 6. Files to Modify

| File | Changes |
|---|---|
| `factory_run.py` | Profile defaults, promotion logic, weekly profile |
| `backtester/crates/bt-core/src/sweep.rs` | Possibly add regime gate paths |
| `backtester/sweeps/full_144v.yaml` | Add `tp_partial_atr_mult`, document exclusions |
| `config/strategy_overrides.yaml` | No changes (this IS the SSOT) |
| `strategy/mei_alpha_v1.py` | Verify defaults match Rust |
| `tests/test_axis_parity.py` | NEW — cross-layer validation tests |
| `docs/AXIS_SSOT.md` | NEW — axis inventory with layer coverage matrix |

---

## 7. Risk

| Risk | Mitigation |
|---|---|
| Rust default ≠ Python default for some axes | Parity test catches it; fix whichever side drifted |
| Regime gate in Rust changes backtester behavior | Gate behind feature flag; off by default |
| 200K daily trials too slow on current GPU | Benchmark first; fall back to 150K if >75min |
| Weekly 2M trials OOM on GPU | TPE batch size auto-scales; monitor VRAM |
| Dead axes in engine waste sweep compute | Audit flags them; lock dead axes out of sweep |
