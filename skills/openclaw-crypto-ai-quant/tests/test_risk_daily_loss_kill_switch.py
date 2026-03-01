from __future__ import annotations

import datetime


def _ts_ms(dt: datetime.datetime) -> int:
    if dt.tzinfo is None:
        raise ValueError("dt must be timezone-aware")
    return int(dt.timestamp() * 1000.0)


def test_daily_loss_kill_switch_resets_at_utc_day_boundary(tmp_path, monkeypatch):
    cfg = tmp_path / "strategy_overrides.yaml"
    cfg.write_text(
        "global:\n"
        "  risk:\n"
        "    max_daily_loss_usd: 100.0\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("AI_QUANT_STRATEGY_YAML", str(cfg))

    from engine.strategy_manager import StrategyManager

    StrategyManager.bootstrap(
        defaults={"trade": {}, "indicators": {}, "filters": {}, "thresholds": {}},
        yaml_path=str(cfg),
        changelog_path=None,
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    day1 = datetime.datetime(2026, 2, 10, 23, 59, tzinfo=datetime.timezone.utc)
    day2 = datetime.datetime(2026, 2, 11, 0, 1, tzinfo=datetime.timezone.utc)

    # Day 1: -60 loss should not kill (threshold -100).
    risk.note_fill(ts_ms=_ts_ms(day1), symbol="BTC", action="CLOSE", pnl_usd=-60.0, fee_usd=0.0)
    assert risk.kill_mode == "off"

    # Day 2: boundary reset means another -60 does not accumulate with day 1.
    risk.note_fill(ts_ms=_ts_ms(day2), symbol="BTC", action="CLOSE", pnl_usd=-60.0, fee_usd=0.0)
    assert risk.kill_mode == "off"

    # Still day 2: breach threshold → kill.
    risk.note_fill(ts_ms=_ts_ms(day2), symbol="BTC", action="REDUCE", pnl_usd=-50.0, fee_usd=0.0)
    assert risk.kill_mode == "close_only"
    assert risk.kill_reason == "daily_loss:2026-02-11"


def test_daily_loss_ignores_entry_actions(tmp_path, monkeypatch):
    cfg = tmp_path / "strategy_overrides.yaml"
    cfg.write_text(
        "global:\n"
        "  risk:\n"
        "    max_daily_loss_usd: 1.0\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("AI_QUANT_STRATEGY_YAML", str(cfg))

    from engine.strategy_manager import StrategyManager

    StrategyManager.bootstrap(
        defaults={"trade": {}, "indicators": {}, "filters": {}, "thresholds": {}},
        yaml_path=str(cfg),
        changelog_path=None,
    )

    from engine.risk import RiskManager

    risk = RiskManager()
    risk.refresh(trader=None)

    t = datetime.datetime(2026, 2, 10, 12, 0, tzinfo=datetime.timezone.utc)
    risk.note_fill(ts_ms=_ts_ms(t), symbol="BTC", action="OPEN", pnl_usd=-100.0, fee_usd=0.0)
    assert risk.kill_mode == "off"

