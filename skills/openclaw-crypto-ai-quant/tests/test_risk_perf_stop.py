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


def test_perf_stop_triggers_when_pf_breaches_threshold(tmp_path, monkeypatch) -> None:
    _bootstrap(
        tmp_path,
        monkeypatch,
        yaml_text=(
            "global:\n"
            "  risk:\n"
            "    perf_stop:\n"
            "      enabled: true\n"
            "      window_trades: 5\n"
            "      min_trades: 5\n"
            "      min_pf: 1.0\n"
        ),
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    # Profit factor: profits / losses. Here: +1 / 4 = 0.25 < 1.0 -> stop.
    pnls = [-1.0, -1.0, -1.0, -1.0, 1.0]
    for i, p in enumerate(pnls, start=1):
        risk.note_fill(ts_ms=i, symbol="BTC", action="CLOSE", pnl_usd=float(p), fee_usd=0.0)

    assert risk.kill_mode == "close_only"
    assert risk.kill_reason == "perf_degradation"


def test_perf_stop_ignores_when_below_min_trades(tmp_path, monkeypatch) -> None:
    _bootstrap(
        tmp_path,
        monkeypatch,
        yaml_text=(
            "global:\n"
            "  risk:\n"
            "    perf_stop:\n"
            "      enabled: true\n"
            "      window_trades: 5\n"
            "      min_trades: 10\n"
            "      min_pf: 1.0\n"
        ),
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    for i in range(1, 6):
        risk.note_fill(ts_ms=i, symbol="BTC", action="CLOSE", pnl_usd=-1.0, fee_usd=0.0)

    assert risk.kill_mode == "off"

