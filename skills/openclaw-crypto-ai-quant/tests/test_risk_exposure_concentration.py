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


def test_exposure_alts_bucket_blocks_new_longs(tmp_path, monkeypatch) -> None:
    _bootstrap(
        tmp_path,
        monkeypatch,
        yaml_text=(
            "global:\n"
            "  risk:\n"
            "    exposure:\n"
            "      enabled: true\n"
            "      alts_max_longs: 2\n"
            "      alts_max_shorts: 1\n"
            "      exclude_symbols: [BTC]\n"
        ),
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    positions = {
        "ETH": {"type": "LONG"},
        "SOL": {"type": "LONG"},
        "BTC": {"type": "LONG"},  # excluded from alts bucket
        "ARB": {"type": "SHORT"},
    }

    # New alt long should be blocked (ETH+SOL already fill the limit).
    dec = risk.allow_order(
        symbol="DOGE",
        action="OPEN",
        side="BUY",
        notional_usd=100.0,
        leverage=1.0,
        positions=positions,
        reduce_risk=False,
    )
    assert dec.allowed is False
    assert "exposure_alts_longs" in dec.reason

    # New BTC long should not be blocked by the alts limit.
    dec2 = risk.allow_order(
        symbol="BTC",
        action="OPEN",
        side="BUY",
        notional_usd=100.0,
        leverage=1.0,
        positions=positions,
        reduce_risk=False,
    )
    assert dec2.allowed is True

    # Adding to an existing position should not be blocked (does not increase exposure count).
    dec3 = risk.allow_order(
        symbol="ETH",
        action="ADD",
        side="BUY",
        notional_usd=50.0,
        leverage=1.0,
        positions=positions,
        reduce_risk=False,
    )
    assert dec3.allowed is True


def test_exposure_alts_bucket_blocks_new_shorts(tmp_path, monkeypatch) -> None:
    _bootstrap(
        tmp_path,
        monkeypatch,
        yaml_text=(
            "global:\n"
            "  risk:\n"
            "    exposure:\n"
            "      enabled: true\n"
            "      alts_max_longs: 99\n"
            "      alts_max_shorts: 1\n"
            "      exclude_symbols: [BTC]\n"
        ),
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    positions = {
        "ARB": {"type": "SHORT"},
    }

    # New alt short should be blocked (already at limit).
    dec = risk.allow_order(
        symbol="DOGE",
        action="OPEN",
        side="SELL",
        notional_usd=100.0,
        leverage=1.0,
        positions=positions,
        reduce_risk=False,
    )
    assert dec.allowed is False
    assert "exposure_alts_shorts" in dec.reason

