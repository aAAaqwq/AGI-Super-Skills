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


def test_portfolio_heat_blocks_when_over_limit(tmp_path, monkeypatch) -> None:
    _bootstrap(
        tmp_path,
        monkeypatch,
        yaml_text=(
            "global:\n"
            "  risk:\n"
            "    heat:\n"
            "      enabled: true\n"
            "      max_pct: 5\n"
            "      sl_atr_mult: 2\n"
            "      fallback_atr_pct: 0.005\n"
        ),
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    # Existing heat: (ATR*mult)*size -> (50*2)*1 + (5*2)*10 = 100 + 100 = 200 USD.
    positions = {
        "ETH": {"type": "LONG", "entry_price": 1000.0, "size": 1.0, "entry_atr": 50.0, "trailing_sl": None},
        "SOL": {"type": "LONG", "entry_price": 100.0, "size": 10.0, "entry_atr": 5.0, "trailing_sl": None},
    }

    # Equity: 10,000 USD -> existing heat is 2%.
    # New order heat estimate: (0.05*2) * (5000/1) = 0.1 * 5000 = 500 USD -> 5%.
    # Total estimate: 7% > 5% -> block.
    dec = risk.allow_order(
        symbol="DOGE",
        action="OPEN",
        side="BUY",
        notional_usd=5000.0,
        leverage=1.0,
        equity_usd=10_000.0,
        entry_price=1.0,
        entry_atr=0.05,
        sl_atr_mult=2.0,
        positions=positions,
        reduce_risk=False,
    )
    assert dec.allowed is False
    assert "portfolio_heat" in dec.reason


def test_portfolio_heat_allows_when_under_limit(tmp_path, monkeypatch) -> None:
    _bootstrap(
        tmp_path,
        monkeypatch,
        yaml_text=(
            "global:\n"
            "  risk:\n"
            "    heat:\n"
            "      enabled: true\n"
            "      max_pct: 10\n"
            "      sl_atr_mult: 2\n"
        ),
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    positions = {
        "ETH": {"type": "LONG", "entry_price": 1000.0, "size": 1.0, "entry_atr": 50.0, "trailing_sl": None},
    }

    dec = risk.allow_order(
        symbol="DOGE",
        action="OPEN",
        side="BUY",
        notional_usd=1000.0,
        leverage=1.0,
        equity_usd=10_000.0,
        entry_price=1.0,
        entry_atr=0.05,
        sl_atr_mult=2.0,
        positions=positions,
        reduce_risk=False,
    )
    assert dec.allowed is True

