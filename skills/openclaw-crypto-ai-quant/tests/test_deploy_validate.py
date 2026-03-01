from tools.deploy_validate import validate_yaml_text


def _valid_yaml(
    *,
    leverage: float = 3.0,
    leverage_low: float = 1.0,
    leverage_medium: float = 3.0,
    leverage_high: float = 5.0,
    max_entry_orders_per_loop: int = 6,
    max_adds_per_symbol: int = 2,
    tp_partial_pct: float = 0.5,
    trailing_start_atr: float = 1.0,
    trailing_distance_atr: float = 0.8,
    entry_min_confidence: str = "high",
    interval: str = "30m",
    entry_interval: str = "3m",
    exit_interval: str = "3m",
    ema_fast_window: int = 20,
    ema_slow_window: int = 50,
) -> str:
    return (
        "global:\n"
        "  trade:\n"
        "    allocation_pct: 0.2\n"
        f"    leverage: {leverage}\n"
        f"    leverage_low: {leverage_low}\n"
        f"    leverage_medium: {leverage_medium}\n"
        f"    leverage_high: {leverage_high}\n"
        "    sl_atr_mult: 2.0\n"
        "    tp_atr_mult: 6.0\n"
        "    slippage_bps: 10.0\n"
        "    max_open_positions: 20\n"
        f"    max_entry_orders_per_loop: {max_entry_orders_per_loop}\n"
        "    max_total_margin_pct: 0.6\n"
        "    min_notional_usd: 10.0\n"
        "    min_atr_pct: 0.003\n"
        f"    tp_partial_pct: {tp_partial_pct}\n"
        f"    max_adds_per_symbol: {max_adds_per_symbol}\n"
        f"    trailing_start_atr: {trailing_start_atr}\n"
        f"    trailing_distance_atr: {trailing_distance_atr}\n"
        f"    entry_min_confidence: {entry_min_confidence}\n"
        "    bump_to_min_notional: true\n"
        "  indicators:\n"
        "    adx_window: 14\n"
        f"    ema_fast_window: {ema_fast_window}\n"
        f"    ema_slow_window: {ema_slow_window}\n"
        "    bb_window: 20\n"
        "    atr_window: 14\n"
        "  thresholds:\n"
        "    entry:\n"
        "      min_adx: 22.0\n"
        "  engine:\n"
        f"    interval: {interval}\n"
        f"    entry_interval: {entry_interval}\n"
        f"    exit_interval: {exit_interval}\n"
    )


def _minimal_valid_yaml_without_optional_fields() -> str:
    return (
        "global:\n"
        "  trade:\n"
        "    allocation_pct: 0.2\n"
        "    leverage: 3.0\n"
        "    leverage_low: 1.0\n"
        "    leverage_medium: 3.0\n"
        "    leverage_high: 5.0\n"
        "    sl_atr_mult: 2.0\n"
        "    tp_atr_mult: 6.0\n"
        "    slippage_bps: 10.0\n"
        "    max_open_positions: 20\n"
        "    max_entry_orders_per_loop: 6\n"
        "    max_total_margin_pct: 0.6\n"
        "    min_notional_usd: 10.0\n"
        "    min_atr_pct: 0.003\n"
        "    bump_to_min_notional: true\n"
        "  indicators:\n"
        "    adx_window: 14\n"
        "    ema_fast_window: 20\n"
        "    ema_slow_window: 50\n"
        "    bb_window: 20\n"
        "    atr_window: 14\n"
        "  thresholds:\n"
        "    entry:\n"
        "      min_adx: 22.0\n"
    )


def test_deploy_validate_rejects_missing_global():
    errs = validate_yaml_text("trade:\n  leverage: 3\n")
    assert errs
    assert any("global" in e for e in errs)


def test_deploy_validate_rejects_invalid_ema_invariant():
    y = _valid_yaml(ema_fast_window=50, ema_slow_window=20)
    errs = validate_yaml_text(y)
    assert any("ema_fast_window" in e for e in errs)


def test_deploy_validate_keeps_backwards_compat_for_optional_fields():
    errs = validate_yaml_text(_minimal_valid_yaml_without_optional_fields())
    assert errs == []


def test_deploy_validate_rejects_leverage_above_safe_cap():
    errs = validate_yaml_text(_valid_yaml(leverage=50.0))
    assert any("global.trade.leverage" in e for e in errs)


def test_deploy_validate_rejects_dynamic_leverage_above_safe_cap():
    errs = validate_yaml_text(_valid_yaml(leverage_high=25.0))
    assert any("global.trade.leverage_high" in e for e in errs)


def test_deploy_validate_rejects_max_entry_orders_per_loop_above_cap():
    errs = validate_yaml_text(_valid_yaml(max_entry_orders_per_loop=999))
    assert any("global.trade.max_entry_orders_per_loop" in e for e in errs)


def test_deploy_validate_rejects_tp_partial_pct_above_one():
    errs = validate_yaml_text(_valid_yaml(tp_partial_pct=1.5))
    assert any("global.trade.tp_partial_pct" in e for e in errs)


def test_deploy_validate_rejects_max_adds_per_symbol_above_cap():
    errs = validate_yaml_text(_valid_yaml(max_adds_per_symbol=99))
    assert any("global.trade.max_adds_per_symbol" in e for e in errs)


def test_deploy_validate_rejects_non_positive_trailing_values():
    errs = validate_yaml_text(_valid_yaml(trailing_start_atr=0.0, trailing_distance_atr=-1.0))
    assert any("global.trade.trailing_start_atr" in e for e in errs)
    assert any("global.trade.trailing_distance_atr" in e for e in errs)


def test_deploy_validate_rejects_invalid_entry_min_confidence():
    errs = validate_yaml_text(_valid_yaml(entry_min_confidence="urgent"))
    assert any("global.trade.entry_min_confidence" in e for e in errs)


def test_deploy_validate_rejects_invalid_engine_intervals():
    errs = validate_yaml_text(_valid_yaml(interval="2h", entry_interval="2x", exit_interval="abc"))
    assert any("global.engine.interval" in e for e in errs)
    assert any("global.engine.entry_interval" in e for e in errs)
    assert any("global.engine.exit_interval" in e for e in errs)
