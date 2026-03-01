from __future__ import annotations


def _bootstrap(tmp_path, monkeypatch, *, yaml_text: str) -> None:
    cfg = tmp_path / "strategy_overrides.yaml"
    cfg.write_text(yaml_text, encoding="utf-8")
    monkeypatch.setenv("AI_QUANT_STRATEGY_YAML", str(cfg))

    from engine.strategy_manager import StrategyManager

    StrategyManager.bootstrap(
        defaults={"trade": {}, "indicators": {}, "filters": {}, "thresholds": {}},
        yaml_path=str(cfg),
        changelog_path=None,
    )


def test_slippage_guard_triggers_on_median_breach(tmp_path, monkeypatch):
    _bootstrap(
        tmp_path,
        monkeypatch,
        yaml_text=(
            "global:\n"
            "  risk:\n"
            "    slippage_guard:\n"
            "      enabled: true\n"
            "      window_fills: 3\n"
            "      max_median_bps: 5\n"
        ),
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    for _ in range(3):
        risk.note_fill(
            ts_ms=1,
            symbol="BTC",
            action="OPEN",
            pnl_usd=0.0,
            fee_usd=0.0,
            fill_price=100.10,
            side="BUY",
            ref_ask=100.00,
        )

    assert risk.kill_mode == "close_only"
    assert risk.kill_reason == "slippage_guard"


def test_slippage_guard_uses_median_not_outliers(tmp_path, monkeypatch):
    _bootstrap(
        tmp_path,
        monkeypatch,
        yaml_text=(
            "global:\n"
            "  risk:\n"
            "    slippage_guard:\n"
            "      enabled: true\n"
            "      window_fills: 3\n"
            "      max_median_bps: 5\n"
        ),
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    # Window: [0, 20, 0] bps -> median is 0 -> should not kill.
    risk.note_fill(
        ts_ms=1,
        symbol="BTC",
        action="OPEN",
        pnl_usd=0.0,
        fee_usd=0.0,
        fill_price=100.00,
        side="BUY",
        ref_ask=100.00,
    )
    risk.note_fill(
        ts_ms=2,
        symbol="BTC",
        action="OPEN",
        pnl_usd=0.0,
        fee_usd=0.0,
        fill_price=100.20,
        side="BUY",
        ref_ask=100.00,
    )
    risk.note_fill(
        ts_ms=3,
        symbol="BTC",
        action="OPEN",
        pnl_usd=0.0,
        fee_usd=0.0,
        fill_price=100.00,
        side="BUY",
        ref_ask=100.00,
    )

    assert risk.kill_mode == "off"


def test_slippage_guard_ignores_non_entry_actions(tmp_path, monkeypatch):
    _bootstrap(
        tmp_path,
        monkeypatch,
        yaml_text=(
            "global:\n"
            "  risk:\n"
            "    slippage_guard:\n"
            "      enabled: true\n"
            "      window_fills: 3\n"
            "      max_median_bps: 1\n"
        ),
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    for _ in range(3):
        risk.note_fill(
            ts_ms=1,
            symbol="BTC",
            action="CLOSE",
            pnl_usd=0.0,
            fee_usd=0.0,
            fill_price=100.10,
            side="SELL",
            ref_bid=100.00,
        )

    assert risk.kill_mode == "off"

